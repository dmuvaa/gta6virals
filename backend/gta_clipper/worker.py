"""Background worker: takes tasks from the Supabase queue and does the video work.

Task kinds
  scan      probe the video, scan its audio, find moments, store them
  prefetch  detect the streamer's webcam, then make previews best-first + flag non-gameplay
  preview   one preview a user is waiting for right now (high priority)
  render    make a kept clip in HD (captions, watermark, layout) and upload it
  frame     a full-size still of a moment, for the webcam-box editor

Run:  python -m gta_clipper worker
State lives in Postgres (projects / moments / tasks) and files in storage (R2 or local),
so workers can restart or run in parallel. Local files here are only a cache."""
from __future__ import annotations

import os
import shutil
import socket
import tempfile
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import analyze, captions, download, facecam, fastfetch, render, storage
from .supa import SupabaseError, client

CACHE = os.path.join(storage.DATA_DIR, "cache")
PREVIEW_PAD = 3.0          # seconds of preview fetched around a moment (room to nudge)
HD_PAD = 6.0               # seconds of HD fetched around a kept clip
STATIC_MOTION = 1.0        # below this average movement a clip is a static screen
PREVIEW_PARALLEL = 6
FAST_KINDS = ["preview", "frame", "render"]
SLOW_KINDS = ["scan", "prefetch"]
WORKER = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"


def fmt_time(s: float) -> str:
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def friendly(e: Exception) -> str:
    import re
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
    low = msg.lower()
    if "subscriber" in low:
        return "This VOD is subscriber-only, so it can't be downloaded."
    if "private video" in low:
        return "This video is private."
    if "sign in to confirm your age" in low:
        return "This video is age-restricted, so it can't be downloaded without signing in."
    if "sign in to confirm you" in low and "bot" in low:
        return "YouTube is blocking downloads from our servers right now. Try a Twitch link, or try again later."
    if "unsupported url" in low:
        return "That link isn't supported. Paste a YouTube video or a Twitch VOD or clip URL."
    if "does not exist" in low or "404" in low:
        return "That video doesn't exist (or was deleted)."
    return msg[:400]


class Cancelled(Exception):
    pass


# ====================================================================== project context
class Ctx:
    """Per-project things worth keeping between tasks on this worker: the stream source
    (direct media URLs, valid for a few hours) and locally cached HD sections."""

    def __init__(self, pid: str):
        self.pid = pid
        self.dir = os.path.join(CACHE, pid)
        os.makedirs(self.dir, exist_ok=True)
        self._fast = None
        self._fast_at = 0.0
        self.lock = threading.Lock()
        self.locks: dict[str, threading.Lock] = {}

    def lock_for(self, key: str) -> threading.Lock:
        with self.lock:
            return self.locks.setdefault(key, threading.Lock())

    def fast(self, url: str, max_height: int = 1080):
        with self.lock:
            if self._fast is None or time.time() - self._fast_at > 3 * 3600:
                info = download.probe(url)
                self._fast = fastfetch.FastSource(info["_raw"], max_height)
                self._fast_at = time.time()
            return self._fast


_ctx: dict[str, Ctx] = {}
_ctx_lock = threading.Lock()


def ctx(pid: str) -> Ctx:
    with _ctx_lock:
        if pid not in _ctx:
            _ctx[pid] = Ctx(pid)
        return _ctx[pid]


def drop_ctx(pid: str):
    with _ctx_lock:
        c = _ctx.pop(pid, None)
    shutil.rmtree(os.path.join(CACHE, pid), ignore_errors=True)
    return c


# ====================================================================== db helpers
def db():
    return client()


def project(pid: str) -> dict:
    p = db().one("projects", "*", id=f"eq.{pid}")
    if not p:
        raise Cancelled()  # deleted
    return p


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def set_project(pid: str, **values):
    values["updated_at"] = now_iso()
    db().update("projects", values, id=f"eq.{pid}")


def moment(pid: str, mid: str) -> dict:
    m = db().one("moments", "*", project_id=f"eq.{pid}", id=f"eq.{mid}")
    if not m:
        raise Cancelled()
    return m


def set_moment(pid: str, mid: str, **values):
    values["updated_at"] = now_iso()
    db().update("moments", values, project_id=f"eq.{pid}", id=f"eq.{mid}")


def enqueue(pid: str, kind: str, moment_id: str | None = None, priority: int = 100, payload=None):
    db().insert("tasks", {"project_id": pid, "kind": kind, "moment_id": moment_id,
                          "priority": priority, "payload": payload or {}})


def check_cancel(pid: str):
    p = db().one("projects", "cancelled", id=f"eq.{pid}")
    if not p or p["cancelled"]:
        raise Cancelled()


# ====================================================================== tasks
def task_scan(t: dict):
    pid = t["project_id"]
    p = project(pid)
    s = p["settings"] or {}
    c = ctx(pid)
    last = [0.0]

    def progress(stage, prog, message=None):
        now = time.time()
        if message is None and now - last[0] < 1.0 and prog < 0.999:
            return
        last[0] = now
        vals = {"stage": stage, "progress": round(prog, 3)}
        if message:
            vals["message"] = message
        set_project(pid, **vals)

    progress("probing", 0.02, "Reading video info…")
    info = download.probe(p["url"])
    try:
        fast = fastfetch.FastSource(info["_raw"], int(s.get("max_height", 1080)))
    except fastfetch.Unsupported:
        raise ValueError("Only YouTube and Twitch links are supported right now.")
    c._fast, c._fast_at = fast, time.time()
    total = info["duration"] or 0
    ws = max(0.0, float(s.get("start") or 0))
    we = min(total, float(s["end"])) if s.get("end") else total
    if we <= ws:
        raise ValueError("The end time must be after the start time.")
    set_project(pid, title=info["title"], platform=info.get("platform", ""),
                uploader=info.get("uploader", ""), thumbnail=info.get("thumbnail"),
                duration=total, mode="fast")

    progress("downloading", 0.03, f"Scanning the audio of {fmt_time(we - ws)} of video…")
    cancel_flag = {"v": False, "t": 0.0}

    def cancelled():
        if time.time() - cancel_flag["t"] > 3:
            cancel_flag["t"] = time.time()
            try:
                check_cancel(pid)
            except Cancelled:
                cancel_flag["v"] = True
        return cancel_flag["v"]

    path, t0 = fast.fetch_scan_audio(os.path.join(c.dir, "scan"), ws, we,
                                     progress=lambda x: progress("downloading", 0.03 + 0.67 * x),
                                     cancel=cancelled)
    ws = t0
    check_cancel(pid)
    progress("analyzing", 0.7, "Finding every moment with some action…")
    dur = min(render.duration(path) or (we - ws), we - ws)
    is_yt = fast.kind == "youtube"
    score, comps, audio = analyze.score_video(
        path, dur, heatmap=info.get("heatmap"), offset=ws, use_motion=False,
        progress=lambda x: progress("analyzing", 0.7 + 0.25 * x),
        ignore_tail=20.0 if (is_yt and we >= total - 0.5 and total > 120) else 0.0)
    count = int(s.get("count") or 0) or analyze.auto_count(dur)
    picks = analyze.pick_segments(score, comps, audio, count=count,
                                  max_len=max(15.0, min(60.0, float(s.get("clip_len") or 45))))
    if not picks:
        raise ValueError("Couldn't find any moments with action. Try a different range.")
    rows = []
    for i, m in enumerate(picks, 1):
        rows.append({
            "project_id": pid, "id": f"m{i}", "rank": i,
            "start_s": m["start"], "end_s": m["end"], "peak_s": m["peak"], "score": m["score"],
            "reason": m["reason"], "source_start": round(ws + m["start"], 2),
            "source_end": round(ws + m["end"], 2),
            "label": f"{fmt_time(ws + m['start'])}–{fmt_time(ws + m['end'])}",
            "format": s.get("format", "vertical_facecam")})
    db().delete("moments", project_id=f"eq.{pid}")  # a retried scan starts clean
    for i in range(0, len(rows), 200):
        db().insert("moments", rows[i:i + 200])
    try:
        os.remove(path)  # the scan audio isn't needed again
    except OSError:
        pass
    set_project(pid, stage="review", progress=1, window_start=ws, window_end=we,
                timeline=analyze.timeline(score),
                message=f"{len(rows)} moments ready to review.")
    enqueue(pid, "prefetch", priority=50)


def _hd_source(p: dict, m: dict, c: Ctx) -> tuple[str, float]:
    """Local HD section covering the moment. Returns (path, window-time of its t=0)."""
    ws, we = p["window_start"], p["window_end"]
    with c.lock_for("hd:" + m["id"]):
        cache = (m.get("internal") or {}).get("hd")
        if cache and os.path.exists(cache["path"]):
            length = render.duration(cache["path"])
            if cache["off"] <= m["start_s"] and m["end_s"] <= cache["off"] + length:
                return cache["path"], cache["off"]
        a = max(0.0, m["start_s"] - HD_PAD)
        b = min(we - ws, m["end_s"] + HD_PAD)
        fast = c.fast(p["url"], int((p["settings"] or {}).get("max_height", 1080)))
        path, t0 = fast.fetch_hd(os.path.join(c.dir, f"hd_{m['id']}_{int(a * 10)}"), ws + a, ws + b)
        internal = dict(m.get("internal") or {}, hd={"path": path, "off": t0 - ws})
        m["internal"] = internal
        set_moment(p["id"], m["id"], internal=internal)
        return path, t0 - ws


def _find_overlay(p: dict, c: Ctx) -> dict:
    """HD of ~10 strong moments spread across the stream → the webcam box, if any."""
    moms = db().select("moments", "*", project_id=f"eq.{p['id']}")
    span = max(1.0, p["window_end"] - p["window_start"])
    buckets: dict[int, dict] = {}
    for m in moms:
        b = int(m["start_s"] / span * 10)
        if b not in buckets or m["score"] > buckets[b]["score"]:
            buckets[b] = m

    def fetch(m):
        try:
            return _hd_source(p, m, c)[0], m["source_start"]
        except Exception:
            traceback.print_exc()
            return None
    with ThreadPoolExecutor(6) as ex:
        got = [g for g in ex.map(fetch, buckets.values()) if g]
    rect = facecam.detect([g[0] for g in got], times=[g[1] for g in got]) if len(got) >= 2 else None
    overlay = rect or {}
    s = p["settings"] or {}
    vals = {"overlay": overlay}
    if rect and s.get("facecam_corner", "auto") == "auto" and (p.get("facecam") or {}).get("source") != "manual":
        vals["facecam"] = {"rect": rect, "source": "auto"}
    set_project(p["id"], **vals)
    p.update(vals)
    return overlay


def _make_preview(p: dict, m: dict, c: Ctx, overlay: dict | None):
    ws, we = p["window_start"], p["window_end"]
    a = max(0.0, m["start_s"] - PREVIEW_PAD)
    b = min(we - ws, m["end_s"] + PREVIEW_PAD)
    fast = c.fast(p["url"])
    with tempfile.TemporaryDirectory(dir=c.dir) as tmp:
        path, t0 = fast.fetch_hd(os.path.join(tmp, "pv"), ws + a, ws + b, preview=True)
        off = t0 - ws
        pv_start, pv_end = round(m["start_s"] - off, 2), round(m["end_s"] - off, 2)
        d = m["end_s"] - m["start_s"]
        frames = facecam.sample_frames(path, pv_start, d, 8)
        scores = {"motion": analyze.clip_motion(path, pv_start, d),
                  "bigface": facecam.camera_ratio_frames(frames)}
        if overlay:
            scores["overlay"] = facecam.overlay_strength_frames(frames, overlay)
        key = f"{p['id']}/previews/{m['id']}_{int(a * 10)}.mp4"
        storage.put(path, key)
    old = m.get("preview_key")
    internal = dict(m.get("internal") or {}, pv_off=off, pv_len=round(b - off, 2), **scores)
    set_moment(p["id"], m["id"], preview_key=key, pv_start=pv_start, pv_end=pv_end, internal=internal)
    if old and old != key:
        storage.delete(old)
    m.update(preview_key=key, pv_start=pv_start, pv_end=pv_end, internal=internal)


def _update_flags(pid: str):
    """Mark likely non-gameplay moments: static screens, and full-screen camera scenes
    (big face, or the streamer's webcam overlay border missing)."""
    moms = db().select("moments", "id,flag,internal", project_id=f"eq.{pid}")
    seen = [m for m in moms if "motion" in (m["internal"] or {})]
    ov = sorted(m["internal"]["overlay"] for m in seen if "overlay" in m["internal"])
    thr = max(1.6, 0.4 * ov[int(0.8 * (len(ov) - 1))]) if len(ov) >= 10 else None
    changes: dict[str | None, list[str]] = {}
    for m in seen:
        i = m["internal"]
        if i["motion"] < STATIC_MOTION:
            f = "static"
        elif i.get("bigface", 0) >= 0.5 or (thr and i.get("overlay", thr) < thr):
            f = "camera"
        else:
            f = None
        if f != m["flag"]:
            changes.setdefault(f, []).append(m["id"])
    for f, ids in changes.items():
        for i in range(0, len(ids), 100):
            db().update("moments", {"flag": f}, project_id=f"eq.{pid}",
                        id=f"in.({','.join(ids[i:i + 100])})")


def task_prefetch(t: dict):
    pid = t["project_id"]
    p = project(pid)
    c = ctx(pid)
    overlay = p.get("overlay")
    if overlay is None:
        overlay = _find_overlay(p, c)
    todo = db().select("moments", "*", project_id=f"eq.{pid}", state="eq.new",
                       preview_key="is.null", order="rank.asc")
    done = [0]

    def one(m):
        if done[0] % 20 == 0:
            check_cancel(pid)
        try:
            with c.lock_for("pv:" + m["id"]):
                cur = moment(pid, m["id"])
                if cur["preview_key"] or cur["state"] != "new":
                    return
                _make_preview(p, cur, c, overlay)
        except Cancelled:
            raise
        except Exception:
            traceback.print_exc()
        finally:
            done[0] += 1
            if done[0] % 10 == 0:
                _update_flags(pid)
    with ThreadPoolExecutor(PREVIEW_PARALLEL) as ex:
        list(ex.map(one, todo))
    _update_flags(pid)


def task_preview(t: dict):
    pid, mid = t["project_id"], t["moment_id"]
    p = project(pid)
    c = ctx(pid)
    with c.lock_for("pv:" + mid):
        m = moment(pid, mid)
        if not m["preview_key"]:
            _make_preview(p, m, c, p.get("overlay"))
    _update_flags(pid)


def _cam_rect(p: dict, c: Ctx) -> dict:
    cam = (p.get("facecam") or {}).get("rect")
    if cam:
        return cam
    s = p["settings"] or {}
    corner = s.get("facecam_corner", "auto")
    if corner != "auto":
        return facecam.corner_rect(corner)
    if p.get("overlay") is None:
        overlay = _find_overlay(p, c)
        if overlay:
            return overlay
    return facecam.corner_rect("bottom-right")


def task_render(t: dict):
    pid, mid = t["project_id"], t["moment_id"]
    p = project(pid)
    s = p["settings"] or {}
    c = ctx(pid)
    m = moment(pid, mid)
    if m["state"] != "kept":
        set_moment(pid, mid, status="idle")
        return
    fmt = m.get("format") or s.get("format", "vertical_facecam")
    set_moment(pid, mid, status="downloading", error=None)
    src, off = _hd_source(p, m, c)
    cam = _cam_rect(p, c) if fmt == "vertical_facecam" else None
    a, dur = m["start_s"] - off, m["end_s"] - m["start_s"]
    with tempfile.TemporaryDirectory(dir=c.dir) as tmp:
        pattern = None
        if s.get("captions") and captions.available():
            set_moment(pid, mid, status="captioning")
            words = captions.transcribe(src, a, dur, tmp)
            pattern = captions.render_frames(words, dur, render.output_width(src, fmt),
                                             os.path.join(tmp, "frames"))
        set_moment(pid, mid, status="rendering")
        wm = render.watermark_png(s["watermark"], render.output_width(src, fmt),
                                  os.path.join(CACHE, ".assets")) if s.get("watermark") else None
        out = os.path.join(tmp, "clip.mp4")
        render.cut(src, out, a, a + dur, fmt, cam, captions=pattern, caption_fps=captions.FPS, watermark=wm)
        thumb = os.path.join(tmp, "clip.jpg")
        render.thumbnail(out, thumb, min(m["peak_s"] - m["start_s"], dur / 2))
        stamp = f"{int(m['start_s'] * 10)}_{int(m['end_s'] * 10)}_{uuid.uuid4().hex[:6]}"
        file_key = storage.put(out, f"{pid}/clips/{mid}_{fmt}_{stamp}.mp4")
        thumb_key = storage.put(thumb, f"{pid}/clips/{mid}_{fmt}_{stamp}.jpg")
    old_file, old_thumb = m.get("file_key"), m.get("thumb_key")
    cur = moment(pid, mid)
    if cur["state"] != "kept":  # discarded while rendering
        storage.delete(file_key), storage.delete(thumb_key)
        set_moment(pid, mid, status="idle")
        return
    set_moment(pid, mid, status="done", file_key=file_key, thumb_key=thumb_key, format=fmt,
               captioned=bool(pattern), error=None)
    storage.delete(old_file), storage.delete(old_thumb)


def task_frame(t: dict):
    pid, mid = t["project_id"], t["moment_id"]
    p = project(pid)
    c = ctx(pid)
    m = moment(pid, mid)
    src, off = _hd_source(p, m, c)
    with tempfile.TemporaryDirectory(dir=c.dir) as tmp:
        out = os.path.join(tmp, "frame.jpg")
        render.thumbnail(src, out, m["peak_s"] - off, width=1280)
        key = storage.put(out, f"{pid}/frames/{mid}_{uuid.uuid4().hex[:6]}.jpg")
    old = (m.get("internal") or {}).get("frame_key")
    internal = dict(moment(pid, mid).get("internal") or {}, frame_key=key)
    set_moment(pid, mid, internal=internal)
    storage.delete(old)


HANDLERS = {"scan": task_scan, "prefetch": task_prefetch, "preview": task_preview,
            "render": task_render, "frame": task_frame}


def run_task(t: dict):
    kind, pid = t["kind"], t["project_id"]
    try:
        HANDLERS[kind](t)
        db().update("tasks", {"status": "done", "finished_at": now_iso()}, id=f"eq.{t['id']}")
    except Cancelled:
        db().update("tasks", {"status": "done", "finished_at": now_iso(), "error": "cancelled"}, id=f"eq.{t['id']}")
        if kind == "scan":
            try:
                set_project(pid, stage="cancelled", message="Cancelled.")
            except Exception:
                pass
    except Exception as e:
        traceback.print_exc()
        msg = friendly(e)
        try:
            db().update("tasks", {"status": "failed", "finished_at": now_iso(), "error": msg[:500]},
                        id=f"eq.{t['id']}")
            if kind == "scan":
                set_project(pid, stage="error", error=msg, message=msg)
            elif kind == "render" and t.get("moment_id"):
                set_moment(pid, t["moment_id"], status="error", error=msg)
        except Exception:
            traceback.print_exc()


# ====================================================================== loop
def _claim(kinds: list[str]) -> dict | None:
    try:
        rows = db().rpc("claim_task", worker_name=WORKER, kinds=kinds)
        return rows[0] if rows else None
    except (SupabaseError, OSError) as e:
        print("claim failed:", e)
        time.sleep(3)
        return None


def _requeue_stale():
    """Tasks left 'running' by a worker that died get another go (up to 3 attempts)."""
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30 * 60))
    try:
        db().update("tasks", {"status": "queued", "worker": None}, status="eq.running",
                    started_at=f"lt.{cutoff}", attempts="lt.3")
        db().update("tasks", {"status": "failed", "error": "Took too long"}, status="eq.running",
                    started_at=f"lt.{cutoff}")
    except Exception:
        traceback.print_exc()


def _janitor():
    """Delete projects older than JOB_TTL_HOURS (rows + files) and idle local caches."""
    ttl = float(os.environ.get("JOB_TTL_HOURS", "48") or 0)
    while True:
        try:
            _requeue_stale()
            if ttl > 0:
                cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ttl * 3600))
                for p in db().select("projects", "id", created_at=f"lt.{cutoff}", limit="50"):
                    storage.delete_prefix(p["id"] + "/")
                    db().delete("projects", id=f"eq.{p['id']}")
                    drop_ctx(p["id"])
            # local caches of projects nobody touched for 6 hours
            if os.path.isdir(CACHE):
                for name in os.listdir(CACHE):
                    d = os.path.join(CACHE, name)
                    if name.startswith(".") or not os.path.isdir(d):
                        continue
                    if time.time() - os.path.getmtime(d) > 6 * 3600:
                        drop_ctx(name)
        except Exception:
            traceback.print_exc()
        time.sleep(600)


def _loop(kinds: list[str], slots: int, idle: float):
    pool = ThreadPoolExecutor(slots)
    sem = threading.Semaphore(slots)
    while True:
        sem.acquire()
        t = _claim(kinds)
        if not t:
            sem.release()
            time.sleep(idle)
            continue

        def go(task=t):
            try:
                run_task(task)
            finally:
                sem.release()
        pool.submit(go)


def main():
    os.makedirs(CACHE, exist_ok=True)
    print(f"worker {WORKER} started · storage: {'R2' if storage.r2_enabled() else 'local disk'}"
          f" · captions: {'on' if captions.available() else 'off'}", flush=True)
    threading.Thread(target=_janitor, daemon=True).start()
    threading.Thread(target=_loop, args=(SLOW_KINDS, 2, 1.0), daemon=True).start()
    _loop(FAST_KINDS, 4, 0.3)  # previews and renders a user is waiting on
