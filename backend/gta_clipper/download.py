"""YouTube / Twitch fetching via yt-dlp."""
from __future__ import annotations

import glob
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

# Prefer H.264 + AAC: decodes several times faster than AV1/VP9 and plays everywhere.
# Analysis only needs a thumbnail-sized picture (motion) and the audio: 144p/160p
# is ~3x smaller than 360p, which matters a lot on multi-hour Twitch VODs.
ANALYSIS_FORMAT = ("bv*[height<=160][height>=144][vcodec^=avc1]+ba[acodec^=mp4a]"
                   "/b[height<=160][height>=144]/bv*[height<=160]+ba"
                   "/bv*[height<=360][vcodec^=avc1]+ba[acodec^=mp4a]/b[height<=360]/wv*+ba/w")


def _hd_format(max_h: int) -> str:
    return (f"bv*[height<={max_h}][vcodec^=avc1]+ba[acodec^=mp4a]/bv*[height<={max_h}][vcodec^=avc]+ba"
            f"/bv*[height<={max_h}]+ba/b[height<={max_h}]/bv*+ba/b")


class Cancelled(Exception):
    pass


def probe(url: str) -> dict:
    """Metadata only: title, duration, platform, YouTube 'most replayed' heatmap."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                           "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist":
        raise ValueError("That's a playlist/channel link. Paste a single video, VOD or clip URL.")
    if info.get("is_live") or info.get("live_status") == "is_live":
        raise ValueError("That stream is live right now. Use the VOD once the stream ends.")
    return {
        "title": info.get("title") or "Untitled",
        "duration": float(info.get("duration") or 0),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "platform": info.get("extractor_key", ""),
        "thumbnail": info.get("thumbnail"),
        "heatmap": info.get("heatmap"),
        "webpage_url": info.get("webpage_url") or url,
        "_raw": info,  # full yt-dlp info (stream URLs); kept in memory only
    }


def _expected_bytes(url: str, fmt: str, seconds: float | None) -> float | None:
    """Rough final size from the selected formats' bitrate, for progress reporting."""
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True,
                               "format": fmt}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    fmts = info.get("requested_formats") or [info]
    tbr = sum((f.get("tbr") or 0) for f in fmts)
    seconds = seconds or info.get("duration")
    if not tbr or not seconds:
        return None
    return tbr * 1000 / 8 * seconds


PERMANENT = ("private", "subscriber", "unavailable", "sign in", "members", "copyright",
             "does not exist", "unsupported url", "requested format")


def _download(*args, retries: int = 3, **kw) -> str:
    """Retry transient failures (dropped connections, expired stream URLs)."""
    for attempt in range(retries + 1):
        try:
            return _download_once(*args, **kw)
        except Cancelled:
            raise
        except RuntimeError as e:
            if attempt == retries or any(w in str(e).lower() for w in PERMANENT):
                raise
            time.sleep(2 + 3 * attempt)


def _download_once(url: str, out_base: str, fmt: str, section: tuple[float, float] | None,
                   progress=None, cancel=None, exact_cuts: bool = False,
                   expected: float | None = None) -> str:
    """Run yt-dlp in its own process so it can be cancelled at any point (time-range
    downloads go through ffmpeg, which yt-dlp can't interrupt or report progress for)."""
    if progress and expected is None:
        expected = _expected_bytes(url, fmt, (section[1] - section[0]) if section else None)
    cmd = [sys.executable, "-m", "yt_dlp", "--quiet", "--no-warnings", "--no-playlist",
           "--no-progress", "-f", fmt, "-o", out_base + ".%(ext)s",
           "--merge-output-format", "mp4", "-N", "8", "--force-overwrites"]
    if section:
        cmd += ["--download-sections", f"*{section[0]:.2f}-{section[1]:.2f}"]
        if exact_cuts:
            cmd += ["--force-keyframes-at-cuts"]
    cmd += ["--", url]
    log_path = out_base + ".log"
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            while proc.poll() is None:
                if cancel and cancel():
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(10)
                    raise Cancelled()
                if progress and expected:
                    size = sum(os.path.getsize(f) for f in glob.glob(glob.escape(out_base) + ".*")
                               if not f.endswith(".log") and os.path.exists(f))
                    progress(min(0.99, size / expected))
                time.sleep(1)
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            raise
    if proc.returncode != 0:
        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        err = next((l for l in reversed(lines) if "ERROR" in l), lines[-1] if lines else "")
        raise RuntimeError(err or f"yt-dlp exited with code {proc.returncode}")
    os.remove(log_path)
    if progress:
        progress(1.0)
    # Skip partials and yt-dlp's per-stream intermediates (name.f137.mp4).
    files = [f for f in glob.glob(glob.escape(out_base) + ".*")
             if not f.endswith((".part", ".ytdl", ".log"))
             and not re.search(r"\.f\d+\.\w+$", f[len(out_base):])]
    if not files:
        raise RuntimeError("Download finished but no file was produced.")
    return max(files, key=os.path.getsize)


CHUNK = 600.0        # seconds per parallel piece of a long analysis download
PARALLEL_CHUNKS = 8


def download_analysis(url, out_base, section=None, progress=None, cancel=None,
                      duration: float | None = None) -> str:
    """Low-res copy used for scoring.

    Time-range downloads are throttled per connection (YouTube serves them at ~1.5x real
    time), so long ranges are split into 10-minute pieces fetched 8 at a time, cut exactly
    (cheap at 144p) and joined, which keeps the timeline accurate."""
    start, end = section if section else (0.0, duration or 0.0)
    if not end or end - start <= CHUNK * 1.5:
        return _download(url, out_base, ANALYSIS_FORMAT, section, progress, cancel)

    bounds, t = [], start
    while t < end - 1:
        bounds.append((t, min(end, t + CHUNK)))
        t += CHUNK
    per_chunk = _expected_bytes(url, ANALYSIS_FORMAT, CHUNK) if progress else None
    fracs = [0.0] * len(bounds)
    lock = threading.Lock()

    def one(i):
        def prog(p):
            with lock:
                fracs[i] = p
                progress(sum(fracs) / len(fracs))
        return _download(url, f"{out_base}.part{i:03d}", ANALYSIS_FORMAT, bounds[i],
                         prog if progress else None, cancel, exact_cuts=True, expected=per_chunk)

    with ThreadPoolExecutor(PARALLEL_CHUNKS) as ex:
        parts = list(ex.map(one, range(len(bounds))))
    lst = out_base + ".concat.txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '" + p.replace("'", "'\\''") + "'\n")
    out = out_base + ".mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c", "copy", out], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Couldn't join the downloaded pieces: " + r.stderr.strip()[-300:])
    for p in parts + [lst]:
        try:
            os.remove(p)
        except OSError:
            pass
    return out


def download_hd(url, out_base, section=None, max_height=1080, progress=None, cancel=None) -> str:
    return _download(url, out_base, _hd_format(max_height), section, progress, cancel)
