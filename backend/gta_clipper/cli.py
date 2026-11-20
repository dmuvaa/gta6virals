"""One-off local run without a database: python -m gta_clipper URL [--format …]"""
import argparse
import sys
import time

from . import pipeline, render


def main():
    ap = argparse.ArgumentParser(prog="gta_clipper")
    ap.add_argument("url")
    ap.add_argument("--count", type=int, default=0, help="0 = automatic")
    ap.add_argument("--len", type=float, default=45, dest="clip_len", help="longest moment (s)")
    ap.add_argument("--format", default="horizontal", choices=list(render.FORMATS))
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--facecam", default="auto", choices=render.FACECAM_CORNERS)
    a = ap.parse_args()
    job = pipeline.Job(url=a.url, count=a.count, clip_len=a.clip_len, fmt=a.format,
                       facecam_corner=a.facecam, start=pipeline.parse_time(a.start),
                       end=pipeline.parse_time(a.end))
    pipeline.JOBS[job.id] = job
    import threading
    t = threading.Thread(target=job.run, daemon=True)
    t.start()
    last = None
    while t.is_alive():
        line = f"[{job.stage:11}] {job.progress*100:5.1f}%  {job.message}"
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(0.5)
    print(f"[{job.stage}] {job.message}")
    for n in job.notes:
        print("note:", n)
    for c in job.clips:
        where = f"{job.dir}/{c['file']}" if c.get("file") else c.get("error")
        print(f"  #{c['rank']} {c['label']}  score {c['score']:.2f}  {c['reason']:16} -> {where}")
    sys.exit(0 if job.stage == "done" else 1)


