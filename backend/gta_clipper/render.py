"""Cutting clips with ffmpeg: horizontal, or vertical 9:16 for Shorts/TikTok/Reels."""
from __future__ import annotations

import subprocess

FORMATS = {
    "horizontal": "Original 16:9",
    "vertical_blur": "9:16, blurred fill (whole frame visible)",
    "vertical_crop": "9:16, center crop",
    "vertical_facecam": "9:16, facecam on top + gameplay below",
}

FACECAM_CORNERS = ("auto", "top-left", "top-right", "bottom-left", "bottom-right")


def _filter(fmt: str, cam: dict | None = None) -> str:
    if fmt == "horizontal":
        return "[0:v]scale='min(1920,iw)':-2,setsar=1[v]"
    if fmt == "vertical_crop":
        return "[0:v]scale=-2:1920,crop=1080:1920,setsar=1[v]"
    if fmt == "vertical_blur":
        return ("[0:v]split[a][b];"
                # Blur a small copy and scale it up: same look, ~10x cheaper.
                "[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
                "boxblur=8:2,eq=brightness=-0.08,scale=1080:1920:flags=bilinear[bg];"
                "[b]scale=1080:-2[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
    if fmt == "vertical_facecam":
        cam = cam or {"x": 0.72, "y": 0.72, "w": 0.28, "h": 0.28}
        # Top band: facecam 1080x608. Bottom: gameplay center crop 1080x1312.
        return (f"[0:v]split[a][b];"
                f"[a]crop=iw*{cam['w']:.4f}:ih*{cam['h']:.4f}:iw*{cam['x']:.4f}:ih*{cam['y']:.4f},"
                f"scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608[cam];"
                f"[b]scale=-2:1312,crop=1080:1312[game];"
                f"[cam][game]vstack,setsar=1[v]")
    raise ValueError(f"Unknown format {fmt}")


def output_width(src: str, fmt: str) -> int:
    if fmt != "horizontal":
        return 1080
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width", "-of", "default=nw=1:nk=1", src], capture_output=True, text=True)
    try:
        w = int(r.stdout.strip())
    except ValueError:
        w = 1920
    return min(1920, w) // 2 * 2


def cut(src: str, out: str, start: float, end: float, fmt: str = "horizontal",
        cam: dict | None = None, captions: str | None = None, caption_fps: int = 15,
        watermark: str | None = None) -> str:
    """Frame-accurate cut (re-encodes) of [start, end] seconds of `src`.
    `captions`: optional ffmpeg image-sequence pattern of transparent caption frames
    (drawn at the output width) to overlay."""
    dur = max(0.5, end - start)
    graph = _filter(fmt, cam)
    inputs = ["-ss", f"{max(0.0, start):.3f}", "-i", src]
    vmap = "[v]"
    if captions:
        inputs += ["-framerate", str(caption_fps), "-i", captions]
        # Vertical: lower-middle (clear of the app buttons at the bottom). 16:9: near the bottom.
        y = "H*0.66-h/2" if fmt != "horizontal" else "H-h-H*0.04"
        graph += f";[v][1:v]overlay=x=(W-w)/2:y={y}:eof_action=pass:format=yuv420[vc]"
        vmap = "[vc]"
    if watermark:
        idx = 2 if captions else 1
        inputs += ["-loop", "1", "-i", watermark]
        # 9:16: centred low, clear of captions; 16:9: bottom-right corner.
        pos = "x=(W-w)/2:y=H*0.86" if fmt != "horizontal" else "x=W-w-W*0.02:y=H-h-H*0.03"
        graph += f";{vmap}[{idx}:v]overlay={pos}:shortest=1:format=yuv420[vw]"
        vmap = "[vw]"
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", *inputs, "-t", f"{dur:.3f}",
           "-filter_complex", graph,
           "-map", vmap, "-map", "0:a?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-r", _target_fps(src, 60 if fmt == "horizontal" else 30),
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()[-400:]}")
    return out


def thumbnail(src: str, out: str, at: float, width: int = 480) -> str:
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0.0, at):.3f}",
                    "-i", src, "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", out],
                   capture_output=True)
    return out


def duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _target_fps(src: str, cap: int) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=avg_frame_rate", "-of",
                        "default=nw=1:nk=1", src], capture_output=True, text=True)
    try:
        num, den = r.stdout.strip().split("/")
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    return f"{min(cap, round(fps)) or 30}"


def watermark_png(text: str, width: int, out_dir: str) -> str:
    """Small semi-transparent 'Made with …' badge sized for the output width."""
    import os
    from PIL import Image, ImageDraw, ImageFont
    from . import captions as cap
    path = os.path.join(out_dir, f"wm_{width}.png")
    if os.path.exists(path):
        return path
    size = max(18, int(width * (0.032 if width <= 1080 else 0.018)))
    font = ImageFont.truetype(cap.FONT, size)
    tw = int(font.getlength(text))
    pad = size // 2
    img = Image.new("RGBA", (tw + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=pad, fill=(0, 0, 0, 110))
    d.text((pad, pad * 0.8), text, font=font, fill=(255, 255, 255, 200))
    os.makedirs(out_dir, exist_ok=True)
    img.save(path)
    return path
