#!/bin/sh
# Container entrypoint: ./start.sh api | worker
# yt-dlp is updated on every start because YouTube/Twitch change often.
set -e
pip install -q -U yt-dlp >/dev/null 2>&1 || echo "yt-dlp update skipped"
case "${1:-api}" in
  api)
    exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 32 --timeout 120 \
         --access-logfile - 'gta_clipper.api:create_app()' ;;
  worker)
    exec python -m gta_clipper worker ;;
  *)
    echo "usage: ./start.sh api|worker" >&2; exit 64 ;;
esac
