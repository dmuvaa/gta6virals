"""Burned-in captions: local speech-to-text (whisper.cpp) + short-form style text.

Words are shown 3 at a time, uppercase, white with a thick black outline, and the word
being spoken is highlighted. This ffmpeg build has no text filters, so caption frames are
drawn with Pillow into a transparent PNG sequence that ffmpeg overlays."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.environ.get("WHISPER_MODEL") or os.path.join(ROOT, "models", "ggml-small.en-q5_1.bin")
WHISPER = os.environ.get("WHISPER_BIN") or "whisper-cli"
_FONTS = [os.environ.get("CAPTION_FONT", ""),
          "/System/Library/Fonts/Supplemental/Arial Black.ttf",          # macOS
          "/usr/share/fonts/truetype/archivo/ArchivoBlack-Regular.ttf",  # Docker image
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONT = next((f for f in _FONTS if f and os.path.exists(f)), _FONTS[1])
FPS = 15
HIGHLIGHT = (255, 221, 0, 255)


def available() -> bool:
    return bool(shutil.which(WHISPER)) and os.path.exists(MODEL) and os.path.exists(FONT)


def transcribe(src: str, start: float, dur: float, workdir: str) -> list[tuple[float, float, str]]:
    """Words spoken in [start, start+dur] of `src` as (t0, t1, word), relative to start."""
    wav = os.path.join(workdir, "speech.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{start:.3f}", "-i", src,
                    "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", "16000", wav],
                   check=True, capture_output=True)
    base = os.path.join(workdir, "speech")
    subprocess.run([WHISPER, "-m", MODEL, "-f", wav, "-ojf", "-of", base, "-np",
                    "-t", str(min(8, os.cpu_count() or 4))],
                   check=True, capture_output=True)
    with open(base + ".json") as f:
        data = json.load(f)
    words: list[list] = []
    for seg in data.get("transcription", []):
        # Whole-segment sound tags like "[BLANK_AUDIO]", "(laughs)", "[Music]".
        if re.fullmatch(r"\s*([\[(][^\])]*[\])]\s*)+", seg.get("text", "")):
            continue
        depth = 0  # skip anything inside [...] or (...), which may span several tokens
        for tok in seg.get("tokens", []):
            text = tok.get("text", "")
            if text.startswith("[_") or text.startswith("<|") or not text.strip():
                continue
            opens = text.count("[") + text.count("(")
            closes = text.count("]") + text.count(")")
            if depth or opens:
                depth = max(0, depth + opens - closes)
                continue
            t0, t1 = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
            if text.startswith(" ") or not words:
                words.append([t0, t1, text.strip()])
            else:  # sub-word token: glue onto the current word
                words[-1][1] = t1
                words[-1][2] += text
    out = []
    for t0, t1, w in words:
        w = re.sub(r"[^\w'’!?.,-]", "", w)
        if w and not re.fullmatch(r"[\W_]+", w) and t0 < dur:
            out.append((t0, min(max(t1, t0 + 0.12), dur), w))
    # Whisper hallucinates on music/noise; drop bracketed sound tags and lone repeats.
    return [w for w in out if not re.fullmatch(
        r"(?i)(music|applause|laughter|laughs|inaudible|blank_audio|silence|_+)", w[2])]


def _chunks(words, n=3, max_gap=0.8):
    cur = []
    for w in words:
        if cur and (len(cur) >= n or w[0] - cur[-1][1] > max_gap):
            yield cur
            cur = []
        cur.append(w)
    if cur:
        yield cur


def render_frames(words, dur: float, width: int, out_dir: str) -> str | None:
    """Write caption frames (RGBA PNGs) at FPS for the whole clip. Returns the ffmpeg
    input pattern, or None when there's nothing to show."""
    if not words:
        return None
    os.makedirs(out_dir, exist_ok=True)
    size = int(width * 0.075)
    font = ImageFont.truetype(FONT, size)
    stroke = max(4, size // 9)
    box_w, box_h = width, int(size * 2.8)
    blank = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))

    # One drawn image per (chunk, active word); reuse it across frames.
    cache: dict[tuple[int, int], Image.Image] = {}
    timeline = []  # (t0, t1, chunk_idx, word_idx)
    chunks = list(_chunks(words))
    for ci, ch in enumerate(chunks):
        end = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else ch[-1][1] + 0.4
        end = min(end, ch[-1][1] + 0.8)
        for wi, w in enumerate(ch):
            w_end = ch[wi + 1][0] if wi + 1 < len(ch) else end
            timeline.append((w[0], w_end, ci, wi))

    def draw(ci, wi):
        key = (ci, wi)
        if key in cache:
            return cache[key]
        ch = chunks[ci]
        texts = [w[2].upper().rstrip(".,") or w[2].upper() for w in ch]
        space = font.getlength(" ")
        widths = [font.getlength(t) for t in texts]
        total = sum(widths) + space * (len(texts) - 1)
        scale = min(1.0, (box_w * 0.92) / max(total, 1))
        f = font if scale >= 1 else ImageFont.truetype(FONT, int(size * scale))
        widths = [f.getlength(t) for t in texts]
        space = f.getlength(" ")
        total = sum(widths) + space * (len(texts) - 1)
        img = blank.copy()
        d = ImageDraw.Draw(img)
        x = (box_w - total) / 2
        y = (box_h - f.size) / 2
        for i, t in enumerate(texts):
            d.text((x, y), t, font=f, fill=HIGHLIGHT if i == wi else (255, 255, 255, 255),
                   stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += widths[i] + space
        cache[key] = img
        return img

    n = int(dur * FPS) + 1
    blank_path = os.path.join(out_dir, "blank.png")
    blank.save(blank_path)
    j = 0
    for k in range(n):
        t = k / FPS
        while j < len(timeline) and timeline[j][1] <= t:
            j += 1
        path = os.path.join(out_dir, f"f{k:05d}.png")
        if j < len(timeline) and timeline[j][0] <= t < timeline[j][1]:
            draw(timeline[j][2], timeline[j][3]).save(path, compress_level=1)
        else:
            os.link(blank_path, path) if not os.path.exists(path) else None
    return os.path.join(out_dir, "f%05d.png")
