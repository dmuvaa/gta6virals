"""Highlight detection: turns a video into a per-half-second excitement score
and picks the best non-overlapping clip windows."""
from __future__ import annotations

import subprocess
import threading

import numpy as np

HOP = 0.5          # seconds per analysis bin
AUDIO_SR = 8000    # analysis sample rate (plenty for loudness)
MOTION_FPS = 4
MOTION_W, MOTION_H = 64, 36


def _ffmpeg_pipe(args: list[str]) -> subprocess.Popen:
    return subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", *args],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def audio_envelope(path: str, progress=None, duration: float | None = None) -> np.ndarray:
    """RMS loudness in dBFS per HOP, streamed so multi-hour VODs don't blow up memory."""
    p = _ffmpeg_pipe(["-i", path, "-vn", "-ac", "1", "-ar", str(AUDIO_SR), "-f", "s16le", "-"])
    block = int(AUDIO_SR * HOP) * 2
    out = []
    while True:
        buf = p.stdout.read(block)
        if not buf:
            break
        x = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
        out.append(20 * np.log10(np.sqrt(np.mean(x * x)) + 1e-6))
        if progress and duration and len(out) % 200 == 0:
            progress(min(1.0, len(out) * HOP / duration))
    p.wait()
    return np.array(out, dtype=np.float32)


def clip_motion(path: str, start: float, dur: float) -> float:
    """Average on-screen movement in [start, start+dur] of `path` (0 = frozen frame).
    Gameplay is typically 3+; menus, 'be right back' and end screens sit near 0-1."""
    m = motion_curve(path, start, dur)
    return float(np.mean(m)) if len(m) else 0.0


def motion_curve(path: str, start: float | None = None, dur: float | None = None) -> np.ndarray:
    """Mean absolute frame difference on a tiny grayscale copy, binned per HOP."""
    pre = (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{dur:.3f}"] if dur else [])
    p = _ffmpeg_pipe([*pre[:2], "-i", path, *pre[2:], "-an", "-vf",
                      f"fps={MOTION_FPS},scale={MOTION_W}:{MOTION_H},format=gray",
                      "-f", "rawvideo", "-"])
    fsz = MOTION_W * MOTION_H
    prev, diffs = None, []
    while True:
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        f = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
        diffs.append(0.0 if prev is None else float(np.mean(np.abs(f - prev))))
        prev = f
    p.wait()
    d = np.array(diffs, dtype=np.float32)
    per_bin = int(MOTION_FPS * HOP)
    n = len(d) // per_bin
    return d[: n * per_bin].reshape(n, per_bin).mean(axis=1) if n else d


def _rolling_median(x: np.ndarray, win: int) -> np.ndarray:
    if len(x) == 0:
        return x
    win = max(3, min(win, len(x)) | 1)
    pad = win // 2
    xp = np.pad(x, pad, mode="edge")
    # Median of every window, computed in chunks to bound memory on long VODs.
    out = np.empty_like(x)
    view = np.lib.stride_tricks.sliding_window_view(xp, win)
    for i in range(0, len(x), 20000):
        out[i:i + 20000] = np.median(view[i:i + 20000], axis=1)
    return out


def _robust_z(x: np.ndarray, baseline_win_s: float = 90) -> np.ndarray:
    """How far above its *local* baseline each point is, in robust std units."""
    if len(x) == 0:
        return x
    base = _rolling_median(x, int(baseline_win_s / HOP))
    dev = x - base
    mad = np.median(np.abs(dev - np.median(dev))) * 1.4826 + 1e-6
    return dev / mad


def _smooth(x: np.ndarray, seconds: float) -> np.ndarray:
    k = max(1, int(seconds / HOP))
    if k <= 1 or len(x) < k:
        return x
    return np.convolve(x, np.ones(k) / k, mode="same")


def heatmap_curve(heatmap: list[dict] | None, n: int, offset: float = 0.0) -> np.ndarray | None:
    """YouTube 'Most replayed' data (0..1) resampled onto our bins."""
    if not heatmap:
        return None
    t = offset + np.arange(n) * HOP
    out = np.zeros(n, dtype=np.float32)
    for seg in heatmap:
        m = (t >= seg["start_time"]) & (t < seg["end_time"])
        out[m] = seg.get("value", 0.0)
    return out


def audio_envelope_parallel(path: str, duration: float, workers: int = 8, progress=None) -> np.ndarray:
    """Same as audio_envelope, but decodes `workers` slices of the file at once."""
    if duration < 1200:
        return audio_envelope(path, progress, duration)
    seg = float(np.ceil(duration / workers / HOP) * HOP)
    nb = int(round(seg / HOP))
    done = [0]
    lock = threading.Lock()

    def one(k):
        p = _ffmpeg_pipe(["-ss", f"{k * seg:.3f}", "-t", f"{seg:.3f}", "-i", path, "-vn", "-ac", "1",
                          "-ar", str(AUDIO_SR), "-f", "s16le", "-"])
        raw = p.stdout.read()
        p.wait()
        x = np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
        b = int(AUDIO_SR * HOP)
        m = min(nb, len(x) // b)
        out = 20 * np.log10(np.sqrt(np.mean(x[: m * b].reshape(m, b) ** 2, axis=1)) + 1e-6) if m \
            else np.zeros(0, np.float32)
        with lock:
            done[0] += 1
            if progress:
                progress(done[0] / workers)
        return out.astype(np.float32)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(one, range(workers)))
    return np.concatenate(parts)


def score_video(path: str, duration: float, heatmap=None, offset: float = 0.0, progress=None,
                ignore_head: float = 3.0, ignore_tail: float = 0.0, use_motion: bool = True):
    """Return (score, components, audio) arrays, one value per HOP seconds of `path`.

    use_motion=False scores from audio alone (the fast path: motion is checked later,
    only on the candidate clips)."""
    res = {}
    if use_motion:
        t = threading.Thread(target=lambda: res.__setitem__("motion", motion_curve(path)))
        t.start()
    audio = audio_envelope_parallel(path, duration, progress=progress)
    if use_motion:
        t.join()
    n = len(audio)
    motion = res.get("motion")
    if motion is not None:
        if len(motion) < n:
            motion = np.pad(motion, (0, n - len(motion)), mode="edge") if len(motion) else np.zeros(n)
        motion = motion[:n]

    loud = np.clip(_robust_z(audio), 0, 8)
    # "Sudden" = jump vs. the previous ~4 seconds: catches screams / crashes / gunshots.
    prev = np.convolve(audio, np.ones(8) / 8, mode="full")[:n]
    prev = np.concatenate([[audio[0]] * 8, prev[:-8]]) if n > 8 else prev
    onset = np.clip(_robust_z(audio - prev, 60), 0, 8)
    # Activity: how many distinct sound events per ~8 s. Chases, gunfights and chaos are
    # busy even when no single moment is a big spike.
    events = (onset > 1.5).astype(np.float32)
    activity = _smooth(events, 8)
    act_ref = float(np.percentile(activity, 90)) + 1e-3
    comps = {
        "loudness": _smooth(loud, 2),
        "reaction": _smooth(onset, 1.5),
        "activity": np.clip(activity / act_ref, 0, 2) * 2,
    }
    if motion is not None:
        comps["action"] = _smooth(np.clip(_robust_z(motion, 120), 0, 8), 3)
        score = (0.35 * comps["loudness"] + 0.3 * comps["reaction"] + 0.15 * comps["activity"]
                 + 0.2 * comps["action"])
    else:
        score = 0.4 * comps["loudness"] + 0.35 * comps["reaction"] + 0.25 * comps["activity"]
    hm = heatmap_curve(heatmap, n, offset)
    if hm is not None and hm.max() > 0:
        comps["replayed"] = hm / hm.max() * 4
        score = score + 0.5 * comps["replayed"]
    # Static screens (end cards, menus, "starting soon", AFK) aren't highlights even when
    # music is loud: scale the score down where there's little on-screen movement.
    if motion is not None:
        m_s = _smooth(motion, 4)
        ref = float(np.median(m_s)) if len(m_s) else 0.0
        gate = np.clip(m_s / (0.5 * ref + 1e-3), 0.15, 1.0) if ref > 0 else np.ones(n)
        score = score * gate
    score = _smooth(score, 2.5)
    score[: int(ignore_head / HOP)] = 0
    if ignore_tail > 0:
        score[max(0, n - int(ignore_tail / HOP)):] = 0
    return score.astype(np.float32), comps, audio


REASON_LABELS = {
    "loudness": "Loud moment",
    "reaction": "Sudden reaction",
    "activity": "Non-stop action",
    "action": "High action",
    "replayed": "Most replayed",
}


def pick_clips(score: np.ndarray, comps: dict, audio: np.ndarray, *, count: int = 8,
               clip_len: float = 30.0, min_score: float = 0.6) -> list[dict]:
    """Greedy non-max suppression over the score curve."""
    n = len(score)
    total = n * HOP
    clip_len = min(clip_len, total)
    s = score.copy()
    clips = []
    while len(clips) < count:
        i = int(np.argmax(s))
        if s[i] <= min_score or not np.isfinite(s[i]):
            break
        peak = i * HOP
        # Let the build-up play: 60% before the peak, 40% after.
        start = max(0.0, peak - clip_len * 0.6)
        end = min(total, start + clip_len)
        start = max(0.0, end - clip_len)
        start, end = _snap_to_quiet(audio, start, end)

        lo, hi = int(start / HOP), int(end / HOP) + 1
        window = {k: float(v[lo:hi].mean()) for k, v in comps.items()}
        reason = max(window, key=window.get)
        clips.append({
            "start": round(start, 2), "end": round(end, 2), "peak": round(peak, 2),
            "score": round(float(score[i]), 2), "reason": REASON_LABELS[reason],
        })
        # Suppress overlap (plus a small gap) so clips don't repeat the same moment.
        gap = int(max(5.0, clip_len * 0.5) / HOP)
        # Spread picks across a long stream: soften scores in the surrounding ±5 minutes.
        near = int(300 / HOP)
        s[max(0, lo - near): min(n, hi + near)] *= 0.8
        s[max(0, lo - gap): min(n, hi + gap)] = -np.inf
    clips.sort(key=lambda c: -c["score"])
    return clips


def _snap_to_quiet(audio: np.ndarray, start: float, end: float, search: float = 2.0):
    """Nudge cut points to the quietest nearby half-second so we don't cut mid-word."""
    def best(t, lo_lim, hi_lim):
        lo = max(0, int((t - search) / HOP))
        hi = min(len(audio), int((t + search) / HOP) + 1)
        if hi <= lo:
            return t
        j = lo + int(np.argmin(audio[lo:hi]))
        return float(min(max(j * HOP, lo_lim), hi_lim))
    total = len(audio) * HOP
    return best(start, 0.0, total), best(end, 0.0, total)


def timeline(score: np.ndarray, points: int = 600) -> list[float]:
    """Downsampled (max-pooled) score curve for the UI chart."""
    if len(score) == 0:
        return []
    step = max(1, int(np.ceil(len(score) / points)))
    n = len(score) // step * step
    pooled = score[:n].reshape(-1, step).max(axis=1) if n else score
    return [round(float(v), 3) for v in pooled]


def find_offset(section_path: str, source_path: str, expected_start: float,
                search: float = 15.0) -> float:
    """Return the time on `source_path` that corresponds to t=0 of `section_path`."""
    hop = 0.02

    def env(path, ss=None, dur=None):
        args = []
        if ss is not None:
            args += ["-ss", f"{max(0.0, ss):.3f}"]
        args += ["-i", path]
        if dur is not None:
            args += ["-t", f"{dur:.3f}"]
        p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *args, "-vn", "-ac", "1",
                            "-ar", str(AUDIO_SR), "-f", "s16le", "-"], capture_output=True)
        x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        b = int(AUDIO_SR * hop)
        m = len(x) // b
        if not m:
            return np.zeros(1, dtype=np.float32)
        e = np.log10(np.sqrt(np.mean(x[: m * b].reshape(m, b) ** 2, axis=1)) + 1e-4)
        return (e - e.mean()) / (e.std() + 1e-6)

    probe = env(section_path, 0, 20)                    # first 20 s of the HD section
    ref_start = max(0.0, expected_start - search)
    ref = env(source_path, ref_start, 20 + 2 * search)  # search window on the analysis copy
    if len(probe) < 50 or len(ref) <= len(probe):
        return expected_start
    corr = np.correlate(ref, probe, mode="valid") / len(probe)
    k = int(np.argmax(corr))
    if corr[k] < 0.3:  # no confident match; trust what we asked yt-dlp for
        return expected_start
    return ref_start + k * hop


def auto_count(duration: float) -> int:
    """How many candidates to offer: dense for short edited videos, ~13 per hour for
    long streams (a 24 h stream gives ~300)."""
    minutes = duration / 60
    return int(min(500, max(5, round(max(min(minutes * 1.5, 15), minutes * 0.22)))))


def pick_segments(score: np.ndarray, comps: dict, audio: np.ndarray, *, count: int,
                  min_len: float = 15.0, max_len: float = 45.0, floor: float = 0.25) -> list[dict]:
    """Many variable-length, non-overlapping moments. Each grows from its peak for as
    long as the action keeps going (score stays above 45% of the peak), between
    min_len and max_len seconds, plus a little lead-in so the build-up is visible."""
    n = len(score)
    if n == 0:
        return []
    total = n * HOP
    s = score.astype(np.float64).copy()
    # Judge "is the action still going?" on a smoother curve, so a sequence isn't cut
    # short by the quiet half-second between two gunshots.
    g = _smooth(score.astype(np.float64), 6)
    used = np.zeros(n, bool)
    max_b, min_b = int(max_len / HOP), int(min_len / HOP)
    out = []
    while len(out) < count:
        i = int(np.argmax(s))
        if not np.isfinite(s[i]) or s[i] < floor:
            break
        thr = max(floor, 0.3 * g[i])
        l = r = i
        while r - l < max_b:
            lo = l > 0 and not used[l - 1] and g[l - 1] >= thr
            ro = r < n - 1 and not used[r + 1] and g[r + 1] >= thr
            if not lo and not ro:
                break
            if lo and (not ro or g[l - 1] * 1.1 >= g[r + 1]):  # favour build-up
                l -= 1
            else:
                r += 1
        # Too short: pad around it (60% before) without crossing other moments.
        while r - l < min_b:
            grew = False
            if l > 0 and not used[l - 1] and (r - l) % 5 < 3:
                l -= 1
                grew = True
            elif r < n - 1 and not used[r + 1]:
                r += 1
                grew = True
            elif l > 0 and not used[l - 1]:
                l -= 1
                grew = True
            if not grew:
                break
        # Lead-in / tail so the moment lands, within free space.
        for _ in range(int(2.5 / HOP)):
            if l > 0 and not used[l - 1]:
                l -= 1
        for _ in range(int(1.5 / HOP)):
            if r < n - 1 and not used[r + 1]:
                r += 1
        if (r - l) * HOP < min_len * 0.6:  # squeezed between neighbours: not worth it
            s[l:r + 1] = -np.inf
            continue
        start, end = _snap_to_quiet(audio, l * HOP, (r + 1) * HOP, search=1.0)
        start, end = max(0.0, start), min(total, end)
        lo_b, hi_b = int(start / HOP), min(n, int(end / HOP) + 1)
        if lo_b < len(used) and used[lo_b:hi_b].any():  # snapping nudged into a neighbour
            start, end = l * HOP, (r + 1) * HOP
            lo_b, hi_b = l, r + 1
        window = {k: float(v[lo_b:hi_b].mean()) for k, v in comps.items()}
        out.append({"start": round(start, 2), "end": round(end, 2), "peak": round(i * HOP, 2),
                    "score": round(float(score[i]), 2),
                    "reason": REASON_LABELS[max(window, key=window.get)]})
        used[lo_b:hi_b] = True
        s[lo_b:hi_b] = -np.inf
    out.sort(key=lambda c: -c["score"])
    return out
