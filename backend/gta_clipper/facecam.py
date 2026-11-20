"""Find a streamer's webcam overlay: a face that stays in the same place across the
stream. In-game faces move around; the webcam doesn't."""
from __future__ import annotations

import subprocess

import cv2
import numpy as np

W, H = 960, 540
_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Fallback rectangles (fractions of the frame) for the manual corner presets.
def corner_rect(corner: str, size: float = 0.28) -> dict:
    s = max(0.1, min(0.6, size))
    x = 0.0 if "left" in corner else 1 - s
    y = 0.0 if "top" in corner else 1 - s
    return {"x": x, "y": y, "w": s, "h": s}


DW, DH = 1280, 720  # detection resolution: webcam faces are small, so look closer


def _frames(path: str, n: int, w: int = W, h: int = H):
    """Yield ~n grayscale frames spread across the file (keyframes only: fast)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        return
    if dur <= 0:
        return
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-skip_frame", "nokey", "-i", path,
                          "-an", "-vf", f"fps={max(n / dur, 0.01):.5f},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, dtype=np.uint8).reshape(h, w)
    p.wait()


def detect(paths: list[str], samples: int = 48, times: list[float] | None = None) -> dict | None:
    """Return the webcam area as {x, y, w, h} fractions of the frame, or None.

    Frames are grouped into time segments (each HD section is one; a single long file is
    split into 6). A webcam face shows up in most segments at the same spot; an in-game
    face can sit still for one scene but not across the whole stream."""
    boxes, seg_of = [], []
    jobs = [(p, i) for i, p in enumerate(paths)]
    single = len(paths) == 1
    nseg = 6 if single else len(paths)
    per = max(10, samples // max(1, len(paths)))
    sx = W / DW
    frames = 0
    gx_sum = np.zeros((H, W), np.float32)
    gy_sum = np.zeros((H, W), np.float32)
    for path, idx in jobs:
        fl = list(_frames(path, per, DW, DH))
        for k, f in enumerate(fl):
            frames += 1
            small = cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA)
            ff = small.astype(np.float32)
            gx_sum += np.abs(cv2.Sobel(ff, cv2.CV_32F, 1, 0, ksize=3))
            gy_sum += np.abs(cv2.Sobel(ff, cv2.CV_32F, 0, 1, ksize=3))
            seg = int(k * nseg / max(1, len(fl))) if single else idx
            f = cv2.equalizeHist(f)
            for (x, y, w, h) in _cascade.detectMultiScale(f, 1.1, 5, minSize=(30, 30)):
                x, y, w, h = x * sx, y * sx, w * sx, h * sx
                if w <= 0.12 * W:  # webcam faces are small; skip close-ups / full-screen camera
                    boxes.append((x + w / 2, y + h / 2, w, h))
                    seg_of.append(seg)
    if frames < 4 or not boxes:
        return None
    b, segs = np.array(boxes, dtype=np.float32), np.array(seg_of)
    best, best_score = None, 0.0
    for cx, cy, w, h in b:
        near = (np.abs(b[:, 0] - cx) < 0.5 * w) & (np.abs(b[:, 1] - cy) < 0.5 * h) & \
               (np.abs(b[:, 2] - w) < 0.35 * w)
        hit_segs = set(segs[near].tolist())
        hit = len(hit_segs)
        coverage = hit / nseg
        if times:
            # A webcam overlay stays on the same pixels for hours; a person sitting still in
            # a camera scene (or an in-game face) doesn't. Require sightings 20+ min apart.
            ts = [times[i] for i in hit_segs]
            if hit < 2 or max(ts) - min(ts) < 1200:
                continue
        elif hit < 3 or coverage < (0.5 if single else 0.25):
            continue
        # Webcams live near edges/corners; in-game characters tend to be centered.
        edge = max(abs(cx / W - 0.5), abs(cy / H - 0.5)) * 2  # 0 center .. 1 edge
        score = coverage + 0.5 * edge + 0.01 * near.sum()
        if score > best_score:
            best_score, best = score, b[near]
    if best is None:
        return None
    cx, cy, fw, fh = (float(v) for v in np.median(best, axis=0))
    snapped = _snap_to_overlay(gx_sum / frames, gy_sum / frames, cx, cy, fw, fh)
    if snapped:
        x0, y0, x1, y1 = snapped
        return {"x": round(x0 / W, 4), "y": round(y0 / H, 4),
                "w": round((x1 - x0) / W, 4), "h": round((y1 - y0) / H, 4)}
    # No clear overlay border: estimate a head-and-shoulders crop.
    # Webcam crop: head + shoulders, 16:9 to match the top band of the vertical layout.
    cw = 3.4 * fw
    ch = cw * 9 / 16
    if ch < 2.4 * fh:
        ch = 2.4 * fh
        cw = ch * 16 / 9
    cw, ch = min(cw, W), min(ch, H)
    x = min(max(0.0, cx - cw / 2), W - cw)
    y = min(max(0.0, cy + 0.2 * fh - ch / 2), H - ch)
    if cw > 0.45 * W:
        return None
    return {"x": round(x / W, 4), "y": round(y / H, 4), "w": round(cw / W, 4), "h": round(ch / H, 4)}


def _snap_to_overlay(gx, gy, cx, cy, fw, fh):
    """Webcam overlays have hard borders that stay put while the game moves underneath,
    so they survive averaging edges over many frames. Look for one on each side of the face."""
    def line(profile, lo, hi, prefer_far):
        lo, hi = int(max(0, lo)), int(min(len(profile), hi))
        if hi - lo < 3:
            return None
        seg = profile[lo:hi]
        base = np.median(profile) + 1e-3
        k = int(np.argmax(seg))
        return lo + k if seg[k] > 3.0 * base else None

    rows = slice(int(max(0, cy - 1.2 * fh)), int(min(H, cy + 1.2 * fh)))
    cols = slice(int(max(0, cx - 1.2 * fw)), int(min(W, cx + 1.2 * fw)))
    vprof = gx[rows].mean(axis=0)      # strength of vertical lines per column
    hprof = gy[:, cols].mean(axis=1)   # strength of horizontal lines per row

    left = 0 if cx - 4.5 * fw <= 0 else line(vprof, cx - 4.5 * fw, cx - 0.9 * fw, True)
    right = line(vprof, cx + 0.9 * fw, cx + 4.5 * fw, True)
    top = line(hprof, cy - 3.0 * fh, cy - 0.8 * fh, True)
    bottom = line(hprof, cy + 0.9 * fh, cy + 3.5 * fh, True)
    # Overlays flush against a frame edge have no drawn border on that side.
    if left is None and cx - 4.5 * fw <= 2 * fw:
        left = 0
    if right is None and cx + 4.5 * fw >= W - 2 * fw:
        right = W
    if top is None and cy - 3.0 * fh <= 2 * fh:
        top = 0
    if bottom is None and cy + 3.5 * fh >= H - 2 * fh:
        bottom = H
    if None in (left, right, top, bottom):
        return None
    if (right - left) > 0.45 * W or (bottom - top) > 0.6 * H:
        return None
    w, h = right - left, bottom - top
    if w < 1.8 * fw or h < 1.6 * fh or w > 0.6 * W or h > 0.6 * H:
        return None
    pad = 2  # stay inside the border line
    return left + pad, top + pad, right - pad, bottom - pad


def sample_frames(path: str, start: float, dur: float, n: int = 8) -> list[np.ndarray]:
    """n grayscale W x H frames spread over [start, start+dur], in one ffmpeg pass."""
    fps = max(n / max(dur, 0.5), 0.05)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(0.0, start):.3f}",
                          "-i", path, "-t", f"{dur:.3f}", "-an",
                          "-vf", f"fps={fps:.4f},scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = []
    while len(out) < n + 1:
        buf = p.stdout.read(W * H)
        if len(buf) < W * H:
            break
        out.append(np.frombuffer(buf, np.uint8).reshape(H, W))
    p.stdout.close()
    p.wait()
    return out[:n]


def camera_ratio_frames(frames: list[np.ndarray]) -> float:
    """Share of frames where a big face fills the screen ('just chatting' camera scene)."""
    if not frames:
        return 0.0
    hits = 0
    for f in frames:
        faces = _cascade.detectMultiScale(cv2.equalizeHist(f), 1.1, 6,
                                          minSize=(int(0.12 * W), int(0.12 * W)))
        hits += len(faces) > 0
    return hits / len(frames)


def overlay_strength_frames(frames: list[np.ndarray], rect: dict) -> float:
    """How clearly the webcam overlay's border shows up in these frames. In gameplay the
    webcam is a box pasted over the game, so its border is a hard, fixed edge; in a
    full-screen camera scene the ratio drops to ~1."""
    if not frames:
        return 0.0
    gx = np.zeros((H, W), np.float32)
    gy = np.zeros((H, W), np.float32)
    for f in frames:
        ff = f.astype(np.float32)
        gx += np.abs(cv2.Sobel(ff, cv2.CV_32F, 1, 0, ksize=3))
        gy += np.abs(cv2.Sobel(ff, cv2.CV_32F, 0, 1, ksize=3))
    gx, gy = gx / len(frames), gy / len(frames)
    x0, y0 = int(rect["x"] * W), int(rect["y"] * H)
    x1, y1 = int((rect["x"] + rect["w"]) * W), int((rect["y"] + rect["h"]) * H)
    ratios = []
    if y1 - y0 > 4 and x1 - x0 > 4:
        for x in (x0, x1):
            if 6 <= x <= W - 7:
                line = gx[y0:y1, x - 2:x + 3].max(axis=1).mean()
                ref = (gx[y0:y1, x - 6].mean() + gx[y0:y1, x + 6].mean()) / 2 + 1e-3
                ratios.append(line / ref)
        for y in (y0, y1):
            if 6 <= y <= H - 7:
                line = gy[y - 2:y + 3, x0:x1].max(axis=0).mean()
                ref = (gy[y - 6, x0:x1].mean() + gy[y + 6, x0:x1].mean()) / 2 + 1e-3
                ratios.append(line / ref)
    return float(np.median(ratios)) if ratios else 0.0


def camera_scene_ratio(path: str, start: float, dur: float, samples: int = 6) -> float:
    return camera_ratio_frames(sample_frames(path, start, dur, samples))


def overlay_strength(path: str, start: float, dur: float, rect: dict, samples: int = 8) -> float:
    return overlay_strength_frames(sample_frames(path, start, dur, samples), rect)
