#!/usr/bin/env bash
# Starts the Highlight Clipper web app at http://localhost:8765
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required: brew install ffmpeg"; exit 1; }
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
# yt-dlp needs frequent updates to keep up with YouTube/Twitch changes.
.venv/bin/pip install -q -U yt-dlp >/dev/null 2>&1 || true
exec .venv/bin/python -m gta_clipper serve --port "${PORT:-8765}"
