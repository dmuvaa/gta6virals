"""Fast, direct fetching of time ranges from YouTube and Twitch.

yt-dlp's time-range downloads stream through ffmpeg at roughly playback speed. Here we
fetch the bytes ourselves over many parallel HTTP connections instead:

* YouTube: adaptive MP4 files carry a `sidx` index (time -> byte offset per fragment), so
  any time range maps to an exact byte range.
* Twitch: VODs are HLS playlists of ~10 s segments with known durations.

Every result is returned together with `t0`, the source time its first sample has, so
callers can line things up exactly."""
from __future__ import annotations

import os
import re
import struct
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CHUNK = 8 * 2 ** 20
WORKERS = 12


class Cancelled(Exception):
    pass


class Unsupported(Exception):
    """Fast path not possible for this video; caller should fall back to yt-dlp."""


def _get(url: str, headers: dict, rng: tuple[int, int] | None = None, tries: int = 4) -> bytes:
    h = dict(headers)
    if rng:
        h["Range"] = f"bytes={rng[0]}-{rng[1]}"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
                return r.read()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1 + 2 * attempt)


class _Progress:
    def __init__(self, total: int, cb, cancel):
        self.total, self.done, self.cb, self.cancel = max(1, total), 0, cb, cancel
        self.lock = threading.Lock()

    def add(self, n: int):
        if self.cancel and self.cancel():
            raise Cancelled()
        with self.lock:
            self.done += n
            if self.cb:
                self.cb(min(1.0, self.done / self.total))


# ---------------------------------------------------------------- YouTube (MP4 + sidx)
class _Mp4Index:
    def __init__(self, url: str, headers: dict):
        self.url, self.headers = url, headers
        head = _get(url, headers, (0, 256 * 1024 - 1))
        off, sidx_at = 0, None
        while off + 8 <= len(head):
            size, typ = struct.unpack(">I4s", head[off:off + 8])
            if typ == b"sidx":
                sidx_at = off
                if off + size > len(head):  # very long VODs: index is bigger than our probe
                    head += _get(url, headers, (len(head), off + size - 1))
                break
            if size < 8:
                break
            off += size
        if sidx_at is None:
            raise Unsupported("no sidx index")
        self.init = head[:sidx_at]  # ftyp + moov
        self._parse_sidx(head, sidx_at)

    def _parse_sidx(self, b: bytes, at: int):
        size = struct.unpack(">I", b[at:at + 4])[0]
        version = b[at + 8]
        p = at + 12
        _ref_id, timescale = struct.unpack(">II", b[p:p + 8])
        p += 8
        if version == 0:
            earliest, first_off = struct.unpack(">II", b[p:p + 8])
            p += 8
        else:
            earliest, first_off = struct.unpack(">QQ", b[p:p + 16])
            p += 16
        p += 2
        count = struct.unpack(">H", b[p:p + 2])[0]
        p += 2
        byte = at + size + first_off
        t = earliest
        self.frags = []  # (start_sec, end_sec, byte_start, byte_end_inclusive)
        for _ in range(count):
            ref, dur, _sap = struct.unpack(">III", b[p:p + 12])
            p += 12
            n = ref & 0x7FFFFFFF
            self.frags.append((t / timescale, (t + dur) / timescale, byte, byte + n - 1))
            byte += n
            t += dur

    def fetch(self, out: str, start: float, end: float, prog: _Progress | None) -> float:
        sel = [f for f in self.frags if f[1] > start and f[0] < end]
        if not sel:
            raise ValueError("Requested range is outside the video.")
        b0, b1 = sel[0][2], sel[-1][3]
        ranges = [(s, min(b1, s + CHUNK - 1)) for s in range(b0, b1 + 1, CHUNK)]
        with open(out, "wb") as f:
            f.write(self.init)
            f.truncate(len(self.init) + (b1 - b0 + 1))

        def one(r):
            data = _get(self.url, self.headers, r)
            with open(out, "r+b") as f:
                f.seek(len(self.init) + r[0] - b0)
                f.write(data)
            if prog:
                prog.add(len(data))
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(one, ranges))
        return sel[0][0]

    def bytes_for(self, start: float, end: float) -> int:
        sel = [f for f in self.frags if f[1] > start and f[0] < end]
        return (sel[-1][3] - sel[0][2] + 1) if sel else 0


# ---------------------------------------------------------------- Twitch (HLS)
class _HlsIndex:
    def __init__(self, url: str, headers: dict):
        self.headers = headers
        text = _get(url, headers).decode("utf-8", "replace")
        self.init_url = None
        self.segs = []  # (start, end, url)
        t, dur = 0.0, None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#EXT-X-MAP:"):
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    self.init_url = urllib.parse.urljoin(url, m.group(1))
            elif line.startswith("#EXTINF:"):
                dur = float(line[8:].split(",")[0])
            elif line and not line.startswith("#") and dur is not None:
                self.segs.append((t, t + dur, urllib.parse.urljoin(url, line)))
                t += dur
                dur = None
        if not self.segs:
            raise Unsupported("empty playlist")

    def fetch(self, out: str, start: float, end: float, prog: _Progress | None) -> float:
        sel = [s for s in self.segs if s[1] > start and s[0] < end]
        if not sel:
            raise ValueError("Requested range is outside the video.")
        parts = [None] * len(sel)

        def one(i):
            data = _get(sel[i][2], self.headers)
            parts[i] = data
            if prog:
                prog.add(len(data))
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(one, range(len(sel))))
        with open(out, "wb") as f:
            if self.init_url:
                f.write(_get(self.init_url, self.headers))
            for p in parts:
                f.write(p)
        return sel[0][0]

    def bytes_for(self, start: float, end: float) -> int:
        return 0  # unknown up front; progress is by segment count instead


# ---------------------------------------------------------------- public
class FastSource:
    """Built from yt-dlp's (unprocessed-for-download) info dict."""

    def __init__(self, info: dict, max_height: int = 1080):
        fmts = info.get("formats") or []
        ext = (info.get("extractor_key") or "").lower()
        self.kind = "youtube" if "youtube" in ext else "twitch" if "twitch" in ext else None
        if not self.kind:
            raise Unsupported(ext)
        self.max_height = max_height
        if self.kind == "youtube":
            def mp4(f):
                return f.get("protocol") == "https" and f.get("ext") in ("mp4", "m4a") \
                    and "drc" not in str(f.get("format_id"))
            auds = [f for f in fmts if mp4(f) and f.get("vcodec") == "none"
                    and str(f.get("acodec", "")).startswith("mp4a")]
            vids = [f for f in fmts if mp4(f) and f.get("acodec") == "none"
                    and str(f.get("vcodec", "")).startswith("avc1") and (f.get("height") or 0) <= max_height]
            if not auds or not vids:
                raise Unsupported("no mp4 adaptive formats")
            auds.sort(key=lambda f: f.get("abr") or 0)
            self.scan_fmt = auds[0]                     # smallest: for analysis
            self.hd_audio_fmt = auds[-1]                # best: for clips
            vids.sort(key=lambda f: ((f.get("height") or 0), (f.get("fps") or 0)))
            self.hd_video_fmt = vids[-1]
            small = [f for f in vids if (f.get("height") or 0) >= 360] or vids
            self.preview_video_fmt = small[0]
            self.preview_audio_fmt = next((f for f in auds if (f.get("abr") or 0) >= 96), auds[-1])
        else:
            hls = [f for f in fmts if str(f.get("protocol", "")).startswith("m3u8")]
            audio = [f for f in hls if f.get("vcodec") == "none" or "audio" in str(f.get("format_id"))]
            video = [f for f in hls if f not in audio and (f.get("height") or 0) <= max_height]
            if not video:
                raise Unsupported("no HLS formats")
            video.sort(key=lambda f: ((f.get("height") or 0), (f.get("fps") or 0)))
            self.hd_video_fmt = video[-1]
            self.scan_fmt = audio[0] if audio else video[0]  # smallest rendition otherwise
            self.hd_audio_fmt = None  # Twitch video segments already contain audio
            small = [f for f in video if (f.get("height") or 0) >= 360] or video
            self.preview_video_fmt = small[0]
            self.preview_audio_fmt = None
        self._idx: dict[str, object] = {}
        self._lock = threading.Lock()

    def _index(self, f: dict):
        key = f["format_id"]
        with self._lock:
            if key not in self._idx:
                h = f.get("http_headers") or {}
                self._idx[key] = _Mp4Index(f["url"], h) if self.kind == "youtube" else _HlsIndex(f["url"], h)
            return self._idx[key]

    def fetch_scan_audio(self, out_base: str, start: float, end: float,
                         progress=None, cancel=None) -> tuple[str, float]:
        """Low-bitrate audio of [start, end] for analysis. Returns (path, t0)."""
        idx = self._index(self.scan_fmt)
        if self.kind == "youtube":
            out = out_base + ".m4a"
            prog = _Progress(idx.bytes_for(start, end), progress, cancel)
            return out, idx.fetch(out, start, end, prog)
        out = out_base + ".ts"
        n = sum(1 for s in idx.segs if s[1] > start and s[0] < end)
        prog = _SegProgress(n, progress, cancel)
        return out, idx.fetch(out, start, end, prog)

    def fetch_hd(self, out_base: str, start: float, end: float, cancel=None,
                 preview: bool = False) -> tuple[str, float]:
        """Video+audio of [start, end] as one MP4 whose t=0 is source time t0.
        preview=True fetches a small ~360p copy for quick review instead of HD."""
        out = out_base + ".mp4"
        vfmt = self.preview_video_fmt if preview else self.hd_video_fmt
        afmt = self.preview_audio_fmt if preview else self.hd_audio_fmt
        if self.kind == "twitch":
            raw = out_base + ".src.ts"
            t0 = self._index(vfmt).fetch(raw, start, end, _Progress(1, None, cancel))
            _run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", raw, "-map", "0:v:0", "-map", "0:a:0?",
                  "-c", "copy", "-bsf:a", "aac_adtstoasc", "-avoid_negative_ts", "make_zero",
                  "-reset_timestamps", "1", "-movflags", "+faststart", out])
            os.remove(raw)
            return out, t0
        vraw, araw = out_base + ".v.mp4", out_base + ".a.m4a"
        res = {}

        def v():
            res["v"] = self._index(vfmt).fetch(vraw, start, end, _Progress(1, None, cancel))

        def a():
            res["a"] = self._index(afmt).fetch(araw, start, end, _Progress(1, None, cancel))
        with ThreadPoolExecutor(2) as ex:
            for fut in [ex.submit(v), ex.submit(a)]:
                fut.result()
        t0v, t0a = res["v"], res["a"]
        # Fragments of the two streams start at slightly different times; shift audio so
        # both line up with the video's first frame at t=0.
        _run(["ffmpeg", "-v", "error", "-nostdin", "-y",
              "-i", vraw, "-itsoffset", f"{t0a - t0v:.3f}", "-i", araw,
              "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
              "-movflags", "+faststart", out])
        for p in (vraw, araw):
            os.remove(p)
        return out, t0v


class _SegProgress(_Progress):
    """Progress by segment count (HLS sizes aren't known up front)."""

    def __init__(self, n, cb, cancel):
        super().__init__(n, cb, cancel)

    def add(self, _bytes):
        super().add(1)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-300:])
