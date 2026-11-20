"""Job orchestration: probe -> download -> score -> pick -> fetch HD -> render."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import shutil
import tempfile
import zipfile

from . import analyze, captions, download, facecam, fastfetch, render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("DATA_DIR") or os.path.join(ROOT, "work")
JOB_TTL_HOURS = float(os.environ.get("JOB_TTL_HOURS", "0") or 0)   # 0 = keep forever
MIN_FREE_GB = float(os.environ.get("MIN_FREE_GB", "3"))

DIRECT_MAX = 25 * 60          # windows up to this long are downloaded once, in HD
MAX_WINDOW = 4 * 3600         # longest stretch we'll analyze in one job
PAD = 20.0                    # extra seconds fetched around each clip (room to re-trim)
FAST_PAD = 6.0                # fast path: re-fetching is quick, so keep sections small
HD_PARALLEL = 3               # concurrent HD section downloads (slow path)
FAST_HD_PARALLEL = 6          # concurrent HD section downloads (fast path)
RENDER_PARALLEL = 3           # concurrent ffmpeg renders
STATIC_MOTION = 1.0           # below this average movement a clip is a static screen
PREVIEW_PARALLEL = 6          # background preview downloads
PREVIEW_PAD = 3.0             # seconds of preview fetched around a moment (room to nudge)
KEEP_PARALLEL = 2             # concurrent HD renders of kept moments

_slots = threading.Semaphore(2)  # concurrent jobs


def parse_time(v) -> float | None:
    """'1:02:03', '62:03', '3723', '1h2m3s', 3723 -> seconds. Empty -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    v = v.strip().lower()
    m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?", v)
    if m and any(m.groups()):
        h, mi, s = (float(x) if x else 0.0 for x in m.groups())
        return h * 3600 + mi * 60 + s
    try:
        nums = [float(p) for p in v.split(":")]
    except ValueError:
        raise ValueError(f"Can't read time '{v}'. Use h:mm:ss, e.g. 1:05:30")
    total = 0.0
    for p in nums:
        total = total * 60 + p
    return total


def fmt_time(s: float) -> str:
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


@dataclass
class Job:
    url: str
    count: int = 0                  # 0 = automatic (fast path: ~13 per hour of stream)
    clip_len: float = 45.0          # fast path: longest moment; slow path: clip length
    fmt: str = "horizontal"
    facecam_corner: str = "auto"
    facecam_size: float = 0.28
    max_height: int = 1080
    start: float | None = None
    end: float | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created: float = field(default_factory=time.time)
    stage: str = "queued"
    progress: float = 0.0
    message: str = "Waiting to start…"
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    window: tuple[float, float] = (0.0, 0.0)
    mode: str = ""
    clips: list[dict] = field(default_factory=list)
    timeline: list[float] = field(default_factory=list)
    cancelled: bool = False
    facecam_rect: dict | None = None
    facecam_source: str = ""        # "auto" | "manual" | "corner" | "fallback"
    captions: bool = False
    overlay: dict | None = None     # streamer's webcam box, used to tell gameplay apart
    owner: int = 0                  # user id (0 = no accounts / CLI)
    watermark: str = ""             # badge text burned into exports (free plan)
    max_seconds: float = 0          # longest stretch this plan may scan in one project
    _quota: object = None           # callable(seconds) -> raises ValueError when over plan
    # internal
    _analysis: str | None = None
    _hd: str | None = None
    _fast: object = None
    _render_pool: object = None
    _locks: dict = field(default_factory=dict)
    _prefetching: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _cam_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def dir(self):
        return os.path.join(WORK, self.id)

    # ---------- public view ----------
    def to_dict(self):
        return {
            "id": self.id, "url": self.url, "created": self.created, "stage": self.stage,
            "progress": round(self.progress, 3), "message": self.message, "error": self.error,
            "notes": self.notes, "mode": self.mode,
            "info": {k: v for k, v in self.info.items() if k not in ("heatmap", "_raw")},
            "window": list(self.window), "timeline": self.timeline,
            "owner": self.owner, "watermark": bool(self.watermark),
            "facecam": {"rect": self.facecam_rect, "source": self.facecam_source},
            "captions": self.captions, "captions_available": captions.available(),
            "overlay": self.overlay,
            "settings": {"count": self.count, "clip_len": self.clip_len, "format": self.fmt,
                         "facecam_corner": self.facecam_corner, "facecam_size": self.facecam_size,
                         "max_height": self.max_height},
            "clips": [{k: v for k, v in c.items() if not k.startswith("_")} for c in self.clips],
        }

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        for _ in range(5):  # worker threads may be mid-update; just try again
            try:
                d = self.to_dict()
                break
            except RuntimeError:
                time.sleep(0.01)
        else:
            return
        d["_internal"] = {"analysis": self._analysis, "hd": self._hd, "watermark": self.watermark,
                          "max_seconds": self.max_seconds,
                          "clip_src": {c["id"]: [c.get("_src"), c.get("_src_off")] for c in self.clips
                                       if c.get("_src")},
                          "pv_off": {c["id"]: c["_pv_off"] for c in self.clips if "_pv_off" in c}}
        tmp = os.path.join(self.dir, f"job.json.{threading.get_ident()}.tmp")
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, os.path.join(self.dir, "job.json"))

    def _set(self, stage=None, progress=None, message=None):
        if stage is not None:
            self.stage = stage
        if progress is not None:
            self.progress = progress
        if message is not None:
            self.message = message
        self.save()

    def _check_cancel(self):
        if self.cancelled:
            raise download.Cancelled()

    # ---------- main run ----------
    def run(self):
        with _slots:
            try:
                self._run()
            except download.Cancelled:
                self._set("cancelled", message="Cancelled.")
            except Exception as e:  # surface a readable error to the UI
                traceback.print_exc()
                self.error = _friendly(e)
                self._set("error", message=self.error)

    def _run(self):
        os.makedirs(os.path.join(self.dir, "clips"), exist_ok=True)
        self._set("probing", 0.02, "Reading video info…")
        self.info = download.probe(self.url)
        raw = self.info.pop("_raw", None)
        self._check_plan()
        try:
            self._fast = fastfetch.FastSource(raw, self.max_height) if raw and self.info["duration"] else None
        except fastfetch.Unsupported:
            self._fast = None
        if self._fast:
            return self._run_fast()
        total = self.info["duration"]

        ws = max(0.0, self.start or 0.0)
        we = self.end if self.end else (total or ws + MAX_WINDOW)
        if total:
            we = min(we, total)
        if we <= ws:
            raise ValueError("The end time must be after the start time.")
        if we - ws > MAX_WINDOW:
            we = ws + MAX_WINDOW
            self.notes.append(f"This VOD is long, so only {fmt_time(ws)}–{fmt_time(we)} was scanned. "
                              "Set a start/end time to scan a different part.")
        self.window = (ws, we)
        full = ws <= 0.5 and (not total or we >= total - 0.5)
        section = None if full else (ws, we)
        self._check_cancel()

        cancel = lambda: self.cancelled
        if we - ws <= DIRECT_MAX:
            # Short: one HD download serves both analysis and cutting.
            self.mode = "direct"
            self._set("downloading", 0.05, "Downloading video…")
            self._hd = download.download_hd(
                self.url, os.path.join(self.dir, "source"), section, self.max_height,
                progress=lambda p: self._set(progress=0.05 + 0.35 * p), cancel=cancel)
            self._analysis = self._hd
        else:
            self.mode = "long"
            self._set("downloading", 0.05,
                      f"Downloading a low-res copy of {fmt_time(we - ws)} for analysis…")
            self._analysis = download.download_analysis(
                self.url, os.path.join(self.dir, "analysis"), section, duration=total,
                progress=lambda p: self._set(progress=0.05 + 0.3 * p), cancel=cancel)
        self._check_cancel()

        self._set("analyzing", 0.4, "Finding the best moments…")
        dur = render.duration(self._analysis) or (we - ws)
        # Edited YouTube uploads usually end on a 5–20 s end screen; skip it.
        is_yt = "youtube" in self.info.get("platform", "").lower()
        reaches_end = not total or we >= total - 0.5
        score, comps, audio = analyze.score_video(
            self._analysis, dur, heatmap=self.info.get("heatmap"), offset=ws,
            progress=lambda p: self._set(progress=0.4 + 0.15 * p),
            ignore_tail=20.0 if (is_yt and reaches_end and total > 120) else 0.0)
        self.timeline = analyze.timeline(score)
        picks = analyze.pick_clips(score, comps, audio, count=self.count or 8,
                                   clip_len=min(self.clip_len, 30.0))
        if not picks:
            raise ValueError("Couldn't find any standout moments. Try a longer range or shorter clips.")
        for i, c in enumerate(picks, 1):
            c.update({"id": f"c{i}", "rank": i, "status": "pending", "format": self.fmt,
                      "state": "kept"})
            self._relabel(c)
        self.clips = picks

        if self.mode == "long":
            self._set("fetching", 0.55, f"Found {len(picks)} moments. Fetching them in HD…")
            done = [0]

            def fetch(c):
                try:
                    self._ensure_source(c, c["start"], c["end"])
                except download.Cancelled:
                    raise
                except Exception as e:
                    traceback.print_exc()
                    c["status"], c["error"] = "error", _friendly(e)
                finally:
                    done[0] += 1
                    self._set(progress=0.55 + 0.25 * done[0] / len(picks))
            with ThreadPoolExecutor(HD_PARALLEL) as ex:
                list(ex.map(fetch, self.clips))
            self._check_cancel()

        base = 0.8 if self.mode == "long" else 0.55
        todo = [c for c in self.clips if c["status"] != "error"]
        self._set("clipping", base, f"Cutting {len(todo)} clips…")
        for i, c in enumerate(todo):
            self._check_cancel()
            self._set(message=f"Cutting clip {i + 1} of {len(todo)}…")
            try:
                self._render_clip(c)
            except download.Cancelled:
                raise
            except Exception as e:
                traceback.print_exc()
                c["status"], c["error"] = "error", _friendly(e)
            self._set(progress=base + (1 - base) * (i + 1) / len(todo))

        ok = sum(c["status"] == "done" for c in self.clips)
        self._set("done", 1.0, f"{ok} clip{'s' if ok != 1 else ''} ready.")

    def _check_plan(self):
        """Enforce plan limits once we know how long the video is."""
        total = self.info.get("duration") or 0
        ws = max(0.0, self.start or 0.0)
        we = min(total, self.end) if (self.end and total) else (self.end or total)
        seconds = max(0.0, (we or 0) - ws)
        if self.max_seconds and seconds > self.max_seconds + 1:
            hrs = self.max_seconds / 3600
            raise ValueError(f"Your plan scans up to {hrs:g} hours per video, and this one is "
                             f"{fmt_time(seconds)}. Set “Scan from / to” to a {hrs:g}-hour range, "
                             "or upgrade for full-length streams.")
        if self._quota and seconds:
            self._quota(seconds)

    # ---------- fast path (YouTube / Twitch) ----------
    def _run_fast(self):
        """Scan the audio of the whole VOD (or the chosen range) over direct parallel HTTP,
        then offer every moment with some action for review. Nothing is rendered in HD
        until the user keeps it."""
        self.mode = "fast"
        total = self.info["duration"]
        ws = max(0.0, self.start or 0.0)
        we = min(total, self.end) if self.end else total
        if we <= ws:
            raise ValueError("The end time must be after the start time.")
        cancel = lambda: self.cancelled
        self._set("downloading", 0.03, f"Scanning the audio of {fmt_time(we - ws)} of video…")
        path, t0 = self._fast.fetch_scan_audio(
            os.path.join(self.dir, "scan"), ws, we,
            progress=lambda p: self._set(progress=0.03 + 0.67 * p), cancel=cancel)
        self._analysis = path
        ws = t0  # the scan starts at a fragment boundary at or just before the request
        self.window = (ws, we)
        self._check_cancel()

        self._set("analyzing", 0.7, "Finding every moment with some action…")
        # A partial download still reports the full stream's length, so cap it at the range.
        dur = min(render.duration(path) or (we - ws), we - ws)
        is_yt = self._fast.kind == "youtube"
        score, comps, audio = analyze.score_video(
            path, dur, heatmap=self.info.get("heatmap"), offset=ws, use_motion=False,
            progress=lambda p: self._set(progress=0.7 + 0.25 * p),
            ignore_tail=20.0 if (is_yt and we >= total - 0.5 and total > 120) else 0.0)
        self.timeline = analyze.timeline(score)
        n = self.count or analyze.auto_count(dur)
        moments = analyze.pick_segments(score, comps, audio, count=n,
                                        max_len=max(15.0, min(60.0, self.clip_len)))
        if not moments:
            raise ValueError("Couldn't find any moments with action. Try a different range.")
        for i, c in enumerate(moments, 1):
            c.update({"id": f"m{i}", "rank": i, "state": "new", "status": "idle",
                      "format": self.fmt, "flag": None})
            self._relabel(c)
        self.clips = moments
        self._set("review", 1.0, f"{len(moments)} moments ready to review.")
        self.start_prefetch()

    # ---------- review: previews, gameplay flags, keep/discard ----------
    def _lock_for(self, cid):
        with self._lock:
            return self._locks.setdefault(cid, threading.Lock())

    def _moment(self, cid):
        c = next((x for x in self.clips if x["id"] == cid), None)
        if c is None:
            raise KeyError(cid)
        return c

    def start_prefetch(self):
        if self.mode != "fast" or self._prefetching:
            return
        self._prefetching = True
        threading.Thread(target=self._prefetch, daemon=True).start()

    def _prefetch(self):
        try:
            if self.overlay is None:
                self._find_overlay()
            order = sorted((c for c in self.clips if c["state"] == "new"), key=lambda c: c["rank"])
            with ThreadPoolExecutor(PREVIEW_PARALLEL) as ex:
                for _ in ex.map(self._safe_preview, order):
                    if self.cancelled:
                        break
        finally:
            self._prefetching = False
            self.save()

    def _safe_preview(self, c):
        if self.cancelled or c["state"] == "discarded":
            return
        try:
            self.ensure_preview(c["id"])
        except Exception:
            traceback.print_exc()

    def _find_overlay(self):
        """Fetch HD for ~10 strong moments spread across the stream and look for a webcam
        box that stays put. Used for the facecam layout and to flag non-gameplay."""
        if not self.clips:
            return
        span = self.window[1] - self.window[0]
        buckets: dict[int, dict] = {}
        for c in self.clips:
            b = int(c["start"] / max(span, 1) * 10)
            if b not in buckets or c["score"] > buckets[b]["score"]:
                buckets[b] = c
        picks = list(buckets.values())

        def fetch(c):
            try:
                with self._lock_for(c["id"] + ":hd"):
                    self._ensure_source(c, c["start"], c["end"])
                c["status"] = "idle"
                return c
            except Exception:
                traceback.print_exc()
                return None
        with ThreadPoolExecutor(FAST_HD_PARALLEL) as ex:
            got = [c for c in ex.map(fetch, picks) if c]
        if len(got) >= 2:
            rect = facecam.detect([c["_src"] for c in got], times=[c["source_start"] for c in got])
            self.overlay = rect or {}
            if rect and self.facecam_corner == "auto" and self.facecam_source != "manual":
                self.facecam_rect, self.facecam_source = rect, "auto"
        else:
            self.overlay = {}
        self.save()

    def ensure_preview(self, cid) -> dict:
        """Small 360p copy of the moment (+ a few seconds either side) for review."""
        c = self._moment(cid)
        with self._lock_for(cid):
            if c.get("preview") and os.path.exists(os.path.join(self.dir, c["preview"])):
                return c
            fast = self._get_fast()
            ws = self.window[0]
            a = max(0.0, c["start"] - PREVIEW_PAD)
            b = min(self.window[1] - ws, c["end"] + PREVIEW_PAD)
            os.makedirs(os.path.join(self.dir, "previews"), exist_ok=True)
            base = os.path.join(self.dir, "previews", f"{cid}_{int(a * 10)}")
            path, t0 = fast.fetch_hd(base, ws + a, ws + b, preview=True,
                                     cancel=lambda: self.cancelled)
            off = t0 - ws
            c["preview"] = os.path.relpath(path, self.dir)
            c["_pv_off"] = off
            c["pv_start"] = round(c["start"] - off, 2)
            c["pv_end"] = round(c["end"] - off, 2)
            d = c["end"] - c["start"]
            frames = facecam.sample_frames(path, c["pv_start"], d, 8)
            c["_motion"] = analyze.clip_motion(path, c["pv_start"], d)
            c["_bigface"] = facecam.camera_ratio_frames(frames)
            if self.overlay:
                c["_overlay"] = facecam.overlay_strength_frames(frames, self.overlay)
            self._update_flags()
            self.save()
            return c

    def _update_flags(self):
        seen = [c for c in self.clips if "_motion" in c]
        ov = sorted(c["_overlay"] for c in seen if "_overlay" in c)
        thr = max(1.6, 0.4 * ov[int(0.8 * (len(ov) - 1))]) if len(ov) >= 10 else None
        for c in seen:
            if c["_motion"] < STATIC_MOTION:
                c["flag"] = "static"
            elif c.get("_bigface", 0) >= 0.5 or (thr and c.get("_overlay", thr) < thr):
                c["flag"] = "camera"
            else:
                c["flag"] = None

    def set_bounds(self, cid, start: float, end: float):
        """Adjust a moment's in/out points (window time) during review."""
        c = self._moment(cid)
        limit = self.window[1] - self.window[0]
        start, end = max(0.0, start), min(limit, end)
        if end - start < 1:
            raise ValueError("A clip has to be at least 1 second long.")
        if end - start > 180:
            raise ValueError("Keep clips under 3 minutes.")
        with self._lock_for(cid):
            c["start"], c["end"] = round(start, 2), round(end, 2)
            c["peak"] = min(max(c["peak"], start), end)
            self._relabel(c)
            off = c.get("_pv_off")
            if c.get("preview") and off is not None:
                plen = render.duration(os.path.join(self.dir, c["preview"]))
                if off <= start and end <= off + plen:
                    c["pv_start"], c["pv_end"] = round(start - off, 2), round(end - off, 2)
                else:  # outside what we fetched: get a new preview next time it's played
                    self._drop_file(c.pop("preview", None))
                    c.pop("pv_start", None), c.pop("pv_end", None)
        self.save()

    def set_state(self, cid, state: str):
        c = self._moment(cid)
        if state not in ("new", "kept", "discarded"):
            raise ValueError("Unknown state.")
        prev, c["state"] = c["state"], state
        if state == "kept" and (prev != "kept" or c.get("status") in ("idle", "error")):
            c["status"], c["error"] = "queued", None
            if self._render_pool is None:
                self._render_pool = ThreadPoolExecutor(KEEP_PARALLEL)
            self._render_pool.submit(self._render_kept, cid)
        elif state == "discarded":
            self._drop_file(c.pop("preview", None))
            c.pop("pv_start", None), c.pop("pv_end", None)
            if c.get("status") == "done":
                self._drop_file(c.pop("file", None))
                self._drop_file(c.pop("thumb", None))
                c["status"] = "idle"
            self._discard_source(c)
        self.save()

    def _render_kept(self, cid):
        c = self._moment(cid)
        if c["state"] != "kept":
            c["status"] = "idle"
            return
        try:
            self._render_clip(c, self.fmt if c.get("format") is None else c["format"])
        except Exception as e:
            traceback.print_exc()
            c["status"], c["error"] = "error", _friendly(e)
            self.save()

    def _drop_file(self, rel):
        if rel:
            try:
                os.remove(os.path.join(self.dir, rel))
            except OSError:
                pass

    def kept_zip(self) -> str:
        out = os.path.join(self.dir, "kept.zip")
        title = re.sub(r"[^\w\- ]+", "", self.info.get("title", "clips"))[:50].strip() or "clips"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for i, c in enumerate(sorted((c for c in self.clips if c["state"] == "kept"
                                          and c.get("status") == "done"), key=lambda c: c["start"]), 1):
                z.write(os.path.join(self.dir, c["file"]),
                        f"{title} - {i:03d} - {c['label'].replace(':', '.').replace('–', ' to ')}.mp4")
        return out

    def _discard_source(self, c):
        for p in (c.pop("_src", None),):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass

    def _get_fast(self):
        """Stream URLs expire after a few hours (and aren't saved), so re-probe when needed."""
        if self._fast is None:
            info = download.probe(self.url)
            self._fast = fastfetch.FastSource(info["_raw"], self.max_height)
        return self._fast

    def _relabel(self, c):
        ws = self.window[0]
        c.update({"source_start": round(ws + c["start"], 2), "source_end": round(ws + c["end"], 2),
                  "label": f"{fmt_time(ws + c['start'])}–{fmt_time(ws + c['end'])}"})

    # ---------- facecam ----------
    def _cam(self) -> dict:
        with self._cam_lock:
            if self.facecam_rect:
                return self.facecam_rect
            if self.facecam_corner != "auto":
                self.facecam_rect = facecam.corner_rect(self.facecam_corner, self.facecam_size)
                self.facecam_source = "corner"
                return self.facecam_rect
            if self.mode == "direct":
                sources = [self._hd]
            else:
                sources = [c["_src"] for c in self.clips if c.get("_src") and os.path.exists(c["_src"])][:8]
            self._set(message="Looking for the streamer's webcam…")
            rect = facecam.detect(sources) if sources else None
            if rect:
                self.facecam_rect, self.facecam_source = rect, "auto"
            else:
                self.facecam_rect = facecam.corner_rect("bottom-right", self.facecam_size)
                self.facecam_source = "fallback"
                self.notes.append("Couldn't find a webcam automatically, so the bottom-right corner "
                                  "was used. Open Adjust on a clip and choose “Set webcam box” to fix it.")
            self.save()
            return self.facecam_rect

    # ---------- per-clip ----------
    def _ensure_source(self, c: dict, start: float, end: float):
        """Return (path, offset) where offset = analysis-time of path's t=0, covering [start, end]."""
        if self.mode == "direct":
            return self._hd, 0.0
        src, off = c.get("_src"), c.get("_src_off")
        if src and os.path.exists(src):
            length = render.duration(src)
            if off <= start and end <= off + length:
                return src, off
        ws = self.window[0]
        if self.mode == "fast":
            want_s = max(0.0, start - FAST_PAD)
            want_e = min(self.window[1] - ws, end + FAST_PAD)
            c["status"] = "downloading"
            self.save()
            base = os.path.join(self.dir, f"hd_{c['id']}_{int(want_s)}")
            try:
                path, t0 = self._get_fast().fetch_hd(base, ws + want_s, ws + want_e,
                                                     cancel=lambda: self.cancelled)
            except fastfetch.Cancelled:
                raise download.Cancelled()
            c["_src"], c["_src_off"] = path, t0 - ws
            c["status"] = "pending"
            return path, c["_src_off"]
        # Fetch an HD section around the clip, then align it to the analysis copy by audio.
        want_s = max(0.0, start - PAD)
        want_e = min(self.window[1] - ws, end + PAD)
        c["status"] = "downloading"
        self.save()
        base = os.path.join(self.dir, f"hd_{c['id']}_{int(want_s)}")
        path = download.download_hd(self.url, base, (ws + want_s, ws + want_e), self.max_height,
                                    cancel=lambda: self.cancelled)
        off = analyze.find_offset(path, self._analysis, want_s)
        c["_src"], c["_src_off"] = path, off
        c["status"] = "pending"
        return path, off

    def _render_clip(self, c: dict, fmt: str | None = None):
        fmt = fmt or c.get("format") or self.fmt
        with self._lock_for(c["id"] + ":hd"):
            src, off = self._ensure_source(c, c["start"], c["end"])
        cam = self._cam() if fmt == "vertical_facecam" else None
        a, dur = c["start"] - off, c["end"] - c["start"]
        tmp = None
        pattern = None
        try:
            if self.captions and captions.available():
                c["status"] = "captioning"
                self.save()
                tmp = tempfile.mkdtemp(dir=self.dir, prefix="cap_")
                words = captions.transcribe(src, a, dur, tmp)
                pattern = captions.render_frames(words, dur, render.output_width(src, fmt),
                                                 os.path.join(tmp, "frames"))
                c["words"] = len(words)
            c["status"] = "rendering"
            self.save()
            name = (f"{c['id']}_{fmt}{'_cc' if pattern else ''}_{int(c['start'] * 10)}_"
                    f"{int(c['end'] * 10)}_{int(time.time()) % 100000}.mp4")
            out = os.path.join(self.dir, "clips", name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            wm = render.watermark_png(self.watermark, render.output_width(src, fmt),
                                      os.path.join(WORK, ".assets")) if self.watermark else None
            render.cut(src, out, a, a + dur, fmt, cam, captions=pattern, caption_fps=captions.FPS,
                       watermark=wm)
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
        thumb = out[:-4] + ".jpg"
        render.thumbnail(out, thumb, min(c["peak"] - c["start"], dur / 2))
        old = c.get("file")
        c.update({"status": "done", "format": fmt, "error": None, "captioned": bool(pattern),
                  "file": f"clips/{name}", "thumb": f"clips/{os.path.basename(thumb)}",
                  "duration": round(dur, 1)})
        self.save()
        if old and old != c["file"]:  # drop the superseded render
            self._drop_file(old)
            self._drop_file(old[:-4] + ".jpg")

    def source_frame(self, cid: str) -> str:
        """A full-size still of the clip's source (for drawing the webcam box)."""
        c = self._moment(cid)
        with self._lock_for(c["id"] + ":hd"):
            src, off = self._ensure_source(c, c["start"], c["end"])
        out = os.path.join(self.dir, "clips", f"frame_{cid}.jpg")
        render.thumbnail(src, out, c["peak"] - off, width=1280)
        return out

    def recut(self, cid: str, start: float, end: float, fmt: str | None = None,
              facecam_rect: dict | None = None):
        c = next((x for x in self.clips if x["id"] == cid), None)
        if not c:
            raise KeyError(cid)
        limit = self.window[1] - self.window[0]
        start, end = max(0.0, start), min(limit, end)
        if end - start < 1:
            raise ValueError("A clip has to be at least 1 second long.")
        if end - start > 180:
            raise ValueError("Keep clips under 3 minutes.")
        if facecam_rect:
            self.facecam_rect, self.facecam_source = facecam_rect, "manual"
        c.update({"start": round(start, 2), "end": round(end, 2),
                  "peak": min(max(c["peak"], start), end)})
        self._relabel(c)
        try:
            self._render_clip(c, fmt)
        except Exception as e:
            c["status"], c["error"] = "error", _friendly(e)
            self.save()
            raise


def _friendly(e: Exception) -> str:
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
    low = msg.lower()
    if "subscriber" in low:
        return "This VOD is subscriber-only, so it can't be downloaded."
    if "private video" in low:
        return "This video is private."
    if "sign in to confirm your age" in low:
        return "This video is age-restricted, so it can't be downloaded without signing in."
    if "unsupported url" in low:
        return "That link isn't supported. Paste a YouTube video or a Twitch VOD or clip URL."
    if "sign in to confirm you" in low and "bot" in low:
        return "YouTube is rate-limiting this machine. Wait a bit and try again."
    if "does not exist" in low or "404" in low:
        return "That video doesn't exist (or was deleted)."
    return msg[:400]


# ---------- registry ----------
JOBS: dict[str, Job] = {}


def delete_job(jid: str):
    job = JOBS.pop(jid, None)
    if job:
        job.cancelled = True
    shutil.rmtree(os.path.join(WORK, jid), ignore_errors=True)


def start_job(quota=None, **kw) -> Job:
    job = Job(**kw)
    job._quota = quota
    JOBS[job.id] = job
    job.save()
    threading.Thread(target=job.run, daemon=True).start()
    return job


def load_jobs():
    """Reload past jobs from disk so clips survive a server restart."""
    if not os.path.isdir(WORK):
        return
    for jid in os.listdir(WORK):
        p = os.path.join(WORK, jid, "job.json")
        if jid in JOBS or not os.path.exists(p):
            continue
        try:
            with open(p) as f:
                d = json.load(f)
            s = d["settings"]
            job = Job(url=d["url"], count=s["count"], clip_len=s["clip_len"], fmt=s["format"],
                      facecam_corner=s["facecam_corner"], facecam_size=s["facecam_size"],
                      max_height=s["max_height"], id=d["id"], created=d["created"])
            job.stage, job.progress, job.message, job.error = d["stage"], d["progress"], d["message"], d["error"]
            if job.stage not in ("done", "error", "cancelled", "review"):
                job.stage = "error"
                job.error = job.message = "Interrupted by a server restart."
            job.notes, job.info, job.mode = d["notes"], d["info"], d["mode"]
            job.window, job.timeline, job.clips = tuple(d["window"]), d["timeline"], d["clips"]
            cam = d.get("facecam") or {}
            job.facecam_rect, job.facecam_source = cam.get("rect"), cam.get("source", "")
            job.captions, job.overlay = d.get("captions", False), d.get("overlay")
            job.owner = d.get("owner", 0)
            internal = d.get("_internal", {})
            job._analysis, job._hd = internal.get("analysis"), internal.get("hd")
            job.watermark = internal.get("watermark", "")
            job.max_seconds = internal.get("max_seconds", 0)
            for c in job.clips:
                c.setdefault("state", "kept")
                if c.get("status") in ("pending", "queued", "downloading", "captioning", "rendering"):
                    c["status"], c["error"] = "error", "Interrupted by a server restart. Keep it again to retry."
                src = internal.get("clip_src", {}).get(c["id"])
                if src and src[0]:
                    c["_src"], c["_src_off"] = src
                if c["id"] in internal.get("pv_off", {}):
                    c["_pv_off"] = internal["pv_off"][c["id"]]
        except (OSError, ValueError, KeyError):
            continue
        JOBS[job.id] = job


def disk_free_gb() -> float:
    os.makedirs(WORK, exist_ok=True)
    return shutil.disk_usage(WORK).free / 1e9


def cleanup_old_jobs():
    """Delete jobs older than JOB_TTL_HOURS (servers have limited disk)."""
    if JOB_TTL_HOURS <= 0:
        return
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    for jid, job in list(JOBS.items()):
        busy = job.stage not in ("done", "error", "cancelled", "review")
        if job.created < cutoff and not busy:
            job.cancelled = True
            JOBS.pop(jid, None)
            shutil.rmtree(job.dir, ignore_errors=True)


def start_janitor():
    def loop():
        while True:
            try:
                cleanup_old_jobs()
            except Exception:
                traceback.print_exc()
            time.sleep(600)
    threading.Thread(target=loop, daemon=True).start()
