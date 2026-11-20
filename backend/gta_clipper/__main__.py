"""Entry points.

  python -m gta_clipper api [--port 8765]   JSON API for the Next.js site
  python -m gta_clipper worker              background worker (scans, previews, renders)
  python -m gta_clipper URL [...]           one-off local run (no database)
"""
import os
import sys


def load_env():
    """Read KEY=VALUE lines from the repo's .env (development only; production sets real env vars)."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", "..", ".env"), os.path.join(here, "..", ".env")):
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "api":
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(os.environ.get("PORT", 8765))
        from .api import create_app
        print(f"API running at http://localhost:{port}", flush=True)
        create_app().run(host="0.0.0.0", port=port, threaded=True)
    elif cmd == "worker":
        from .worker import main as worker_main
        worker_main()
    else:
        from .cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
