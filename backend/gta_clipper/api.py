"""JSON API used by the Next.js front end.

Every request carries the user's Supabase access token (Authorization: Bearer …); we
verify it with Supabase Auth, then read/write with the secret key. Heavy work is queued
as tasks for the worker. Run:  python -m gta_clipper api"""
from __future__ import annotations

import functools
import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import urllib.request
import uuid
import zipfile

from flask import Flask, Response, abort, g, jsonify, request, send_file

from . import config, download, render, storage
from .supa import SupabaseError, client

FORMATS = set(render.FORMATS)
CORNERS = {"auto", "top-left", "top-right", "bottom-left", "bottom-right"}
STATES = {"new", "kept", "discarded"}


def parse_time(v) -> float | None:
    """'1:02:03', '62:03', '3723', '1h2m3s', 3723 -> seconds. Empty -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    v = str(v).strip().lower()
    m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?", v)
    if m and any(m.groups()):
        h, mi, s = (float(x) if x else 0.0 for x in m.groups())
        return h * 3600 + mi * 60 + s
    try:
        parts = [float(p) for p in v.split(":")]
    except ValueError:
        raise ValueError(f"Can't read time '{v}'. Use h:mm:ss, e.g. 1:05:30")
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def period() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def err(message: str, status: int = 400, **extra):
    return jsonify(error=message, **extra), status


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    db = client()
    def norm(o: str) -> str:
        # Forgiving about how WEB_ORIGINS is typed: quotes, spaces, case, trailing slash or path.
        o = o.strip().strip("'\"").strip().lower()
        m = re.match(r"^(https?://[^/\s]+)", o)
        return m.group(1) if m else o.rstrip("/")
    origins = {norm(o) for o in re.split(r"[,\s]+", os.environ.get("WEB_ORIGINS", "http://localhost:3000")) if norm(o)}
    app.logger.warning("CORS allowed origins: %s", sorted(origins))

    # ------------------------------------------------------------ CORS + headers
    @app.after_request
    def headers(resp):
        origin = request.headers.get("Origin", "")
        if origin and norm(origin) in origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            resp.headers["Access-Control-Max-Age"] = "600"
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    @app.before_request
    def preflight():
        if request.method == "OPTIONS":
            return Response(status=204)

    @app.get("/healthz")
    def healthz():
        # Allowed website origins are public anyway (browsers see them); listing them here
        # makes CORS setup easy to check.
        return jsonify(ok=True, cors_origins=sorted(origins))

    # ------------------------------------------------------------ auth helpers
    def login_required(view):
        @functools.wraps(view)
        def wrapped(*a, **kw):
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            user = db.user_from_token(token)
            if not user or not user.get("id"):
                return err("Please log in.", 401)
            g.uid = user["id"]
            g.email = user.get("email", "")
            prof = db.one("profiles", "*", id=f"eq.{g.uid}")
            if not prof:  # created by the signup trigger; recreate if it's missing
                db.insert("profiles", {"id": g.uid, "name": (user.get("user_metadata") or {}).get("name", "")},
                          upsert=True, on_conflict="id")
                prof = db.one("profiles", "*", id=f"eq.{g.uid}")
            g.profile = prof
            g.plan = config.PLANS.get(prof["plan"], config.PLANS["free"])
            return view(*a, **kw)
        return wrapped

    def usage(uid: str) -> dict:
        row = db.one("usage", "*", user_id=f"eq.{uid}", period=f"eq.{period()}")
        return {"seconds": row["seconds_scanned"] if row else 0.0, "exports": row["exports"] if row else 0}

    def own_project(pid: str) -> dict:
        p = db.one("projects", "*", id=f"eq.{pid}", user_id=f"eq.{g.uid}")
        if not p:
            abort(404)
        return p

    def own_moment(pid: str, mid: str) -> dict:
        m = db.one("moments", "*", project_id=f"eq.{pid}", id=f"eq.{mid}")
        if not m:
            abort(404)
        return m

    def enqueue(pid, kind, moment_id=None, priority=100):
        db.insert("tasks", {"project_id": pid, "kind": kind, "moment_id": moment_id, "priority": priority})

    def wait_for(fn, timeout=25.0, step=0.4):
        end = time.time() + timeout
        while time.time() < end:
            v = fn()
            if v:
                return v
            time.sleep(step)
        return None

    # ------------------------------------------------------------ views of data
    def moment_view(m: dict, title: str) -> dict:
        out = {k: m[k] for k in ("id", "rank", "score", "reason", "label", "source_start", "source_end",
                                 "state", "status", "flag", "format", "captioned", "error")}
        out.update(start=m["start_s"], end=m["end_s"], peak=m["peak_s"])
        if m.get("file_key") and m["status"] == "done":
            safe = re.sub(r"[^\w\- ]+", "", title)[:60].strip() or "clip"
            out["file_url"] = storage.url(m["file_key"])
            out["download_url"] = storage.url(m["file_key"], download_name=f"{safe} - {m['id']}.mp4")
            out["thumb_url"] = storage.url(m["thumb_key"])
        return out

    def project_view(p: dict, with_moments: bool = False) -> dict:
        out = {k: p[k] for k in ("id", "url", "title", "platform", "uploader", "thumbnail", "duration",
                                 "stage", "progress", "message", "error", "timeline", "notes", "created_at")}
        s = p["settings"] or {}
        out["window"] = [p["window_start"], p["window_end"]]
        out["settings"] = {k: s.get(k) for k in ("format", "captions", "facecam_corner", "clip_len", "start", "end")}
        out["watermark"] = bool(s.get("watermark"))
        out["facecam"] = p.get("facecam") or {}
        if with_moments:
            moms = db.select("moments", "*", project_id=f"eq.{p['id']}", order="rank.asc")
            out["moments"] = [moment_view(m, p["title"]) for m in moms]
        return out

    # ------------------------------------------------------------ account
    @app.get("/api/me")
    @login_required
    def me():
        u = usage(g.uid)
        plan = g.plan
        return jsonify(
            id=g.uid, email=g.email, name=g.profile["name"], plan=g.profile["plan"],
            plan_status=g.profile["plan_status"], has_billing=bool(g.profile.get("billing_customer")),
            limits={k: plan[k] for k in ("name", "price", "hours", "exports", "captions", "watermark", "max_video_hours")},
            usage={"hours": round(u["seconds"] / 3600, 2), "exports": u["exports"]})

    @app.post("/api/account/delete")
    @login_required
    def delete_account():
        for p in db.select("projects", "id", user_id=f"eq.{g.uid}"):
            db.update("projects", {"cancelled": True}, id=f"eq.{p['id']}")
            storage.delete_prefix(p["id"] + "/")
        db.delete_auth_user(g.uid)  # cascades to profile, usage, projects, moments, tasks
        return jsonify(ok=True)

    # ------------------------------------------------------------ projects
    @app.post("/api/probe")
    @login_required
    def probe():
        url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
        if not re.match(r"https?://", url):
            return err("Paste a full YouTube or Twitch link.")
        try:
            info = download.probe(url)
        except Exception as e:
            from .worker import friendly
            return err(friendly(e))
        info.pop("_raw", None)
        info.pop("heatmap", None)
        return jsonify(info)

    @app.get("/api/projects")
    @login_required
    def list_projects():
        rows = db.select("projects", "*", user_id=f"eq.{g.uid}", order="created_at.desc", limit="100")
        out = []
        counts = {}
        if rows:
            ids = ",".join(r["id"] for r in rows)
            for m in db.select("moments", "project_id,state,status", project_id=f"in.({ids})"):
                c = counts.setdefault(m["project_id"], {"moments": 0, "kept": 0, "ready": 0})
                c["moments"] += 1
                if m["state"] == "kept":
                    c["kept"] += 1
                    c["ready"] += m["status"] == "done"
        for r in rows:
            v = project_view(r)
            v.pop("timeline", None)
            v["counts"] = counts.get(r["id"], {"moments": 0, "kept": 0, "ready": 0})
            out.append(v)
        return jsonify(out)

    @app.post("/api/projects")
    @login_required
    def create_project():
        d = request.get_json(silent=True) or {}
        url = (d.get("url") or "").strip()
        if not re.match(r"https?://", url):
            return err("Paste a full YouTube or Twitch link (starting with https://).")
        busy = db.select("projects", "id", user_id=f"eq.{g.uid}",
                         stage="in.(queued,probing,downloading,analyzing)")
        if len(busy) >= 2:
            return err("You already have 2 projects scanning. Wait for one to finish.", 429)
        plan = g.plan
        try:
            fmt = d.get("format") or "vertical_facecam"
            if fmt not in FORMATS:
                raise ValueError("Unknown layout.")
            corner = d.get("facecam_corner") or "auto"
            if corner not in CORNERS:
                raise ValueError("Unknown webcam setting.")
            start, end = parse_time(d.get("start")), parse_time(d.get("end"))
            clip_len = max(15.0, min(60.0, float(d.get("clip_len") or 45)))
        except (ValueError, TypeError) as e:
            return err(str(e))
        try:
            info = download.probe(url)
        except Exception as e:
            from .worker import friendly
            return err(friendly(e))
        total = info["duration"] or 0
        if not total:
            return err("Live streams can't be clipped yet. Use the VOD once the stream ends.")
        ws = max(0.0, start or 0.0)
        we = min(total, end) if end else total
        if we <= ws:
            return err("The end time must be after the start time.")
        seconds = we - ws
        max_s = plan["max_video_hours"] * 3600
        if seconds > max_s + 1:
            return err(f"Your plan scans up to {plan['max_video_hours']} hours per video, and this is "
                       f"{seconds / 3600:.1f} hours. Set a scan range, or upgrade for full-length streams.",
                       upgrade=True)
        left = plan["hours"] * 3600 - usage(g.uid)["seconds"]
        if seconds > left + 60:
            return err(f"This needs {seconds / 3600:.1f} hours of scanning, but your {plan['name']} plan has "
                       f"{max(0, left) / 3600:.1f} hours left this month. Scan a shorter range or upgrade.",
                       upgrade=True)
        pid = uuid.uuid4().hex[:12]
        settings = {"format": fmt, "captions": bool(d.get("captions")) and plan["captions"],
                    "facecam_corner": corner, "clip_len": clip_len, "start": start, "end": end,
                    "max_height": 1080, "watermark": f"Made with {config.BRAND}" if plan["watermark"] else ""}
        db.insert("projects", {"id": pid, "user_id": g.uid, "url": url, "title": info["title"],
                               "platform": info.get("platform", ""), "uploader": info.get("uploader", ""),
                               "thumbnail": info.get("thumbnail"), "duration": total, "settings": settings,
                               "message": "Waiting for a worker…"})
        db.rpc("add_usage", uid=g.uid, add_seconds=seconds, add_exports=0)
        enqueue(pid, "scan", priority=20)
        return jsonify(id=pid), 201

    @app.get("/api/projects/<pid>")
    @login_required
    def get_project(pid):
        return jsonify(project_view(own_project(pid), with_moments=True))

    @app.post("/api/projects/<pid>/cancel")
    @login_required
    def cancel(pid):
        own_project(pid)
        db.update("projects", {"cancelled": True}, id=f"eq.{pid}")
        return jsonify(ok=True)

    @app.post("/api/projects/<pid>/delete")
    @login_required
    def delete(pid):
        own_project(pid)
        db.update("projects", {"cancelled": True}, id=f"eq.{pid}")
        storage.delete_prefix(pid + "/")
        db.delete("projects", id=f"eq.{pid}")
        return jsonify(ok=True)

    @app.post("/api/projects/<pid>/settings")
    @login_required
    def settings(pid):
        p = own_project(pid)
        d = request.get_json(silent=True) or {}
        s = dict(p["settings"] or {})
        if "format" in d:
            if d["format"] not in FORMATS:
                return err("Unknown layout.")
            s["format"] = d["format"]
        if "captions" in d:
            if d["captions"] and not g.plan["captions"]:
                return err("Captions are included in the Creator and Pro plans.", 402, upgrade=True)
            s["captions"] = bool(d["captions"])
        db.update("projects", {"settings": s, "updated_at": now_iso()}, id=f"eq.{pid}")
        return jsonify(ok=True)

    # ------------------------------------------------------------ moments
    @app.post("/api/projects/<pid>/moments/<mid>/preview")
    @login_required
    def preview(pid, mid):
        own_project(pid)
        m = own_moment(pid, mid)
        if not m["preview_key"]:
            pending = db.select("tasks", "id", project_id=f"eq.{pid}", moment_id=f"eq.{mid}",
                                kind="eq.preview", status="in.(queued,running)")
            if not pending:
                enqueue(pid, "preview", mid, priority=5)
            m = wait_for(lambda: (lambda r: r if r and r["preview_key"] else None)(
                db.one("moments", "*", project_id=f"eq.{pid}", id=f"eq.{mid}")))
            if not m:
                return err("The preview is taking longer than usual. Try again in a moment.", 504)
        return jsonify(url=storage.url(m["preview_key"]), start=m["pv_start"], end=m["pv_end"], flag=m["flag"])

    @app.post("/api/projects/<pid>/moments/<mid>")
    @login_required
    def update_moment(pid, mid):
        p = own_project(pid)
        m = own_moment(pid, mid)
        d = request.get_json(silent=True) or {}
        vals: dict = {}
        try:
            if "start" in d or "end" in d:
                ws = p["window_start"]
                s0, e0 = parse_time(d.get("start")), parse_time(d.get("end"))
                start = m["start_s"] if s0 is None else s0 - ws
                end = m["end_s"] if e0 is None else e0 - ws
                start, end = max(0.0, start), min(p["window_end"] - ws, end)
                if end - start < 1:
                    raise ValueError("A clip has to be at least 1 second long.")
                if end - start > 180:
                    raise ValueError("Keep clips under 3 minutes.")
                from .worker import fmt_time
                vals.update(start_s=round(start, 2), end_s=round(end, 2),
                            peak_s=min(max(m["peak_s"], start), end),
                            source_start=round(ws + start, 2), source_end=round(ws + end, 2),
                            label=f"{fmt_time(ws + start)}–{fmt_time(ws + end)}")
                i = m.get("internal") or {}
                off, plen = i.get("pv_off"), i.get("pv_len")
                if m["preview_key"] and off is not None and plen and off <= start and end <= off + plen:
                    vals.update(pv_start=round(start - off, 2), pv_end=round(end - off, 2))
                elif m["preview_key"]:  # outside what the preview covers: make a new one on play
                    storage.delete(m["preview_key"])
                    vals.update(preview_key=None, pv_start=None, pv_end=None)
            if "format" in d:
                if d["format"] not in FORMATS:
                    raise ValueError("Unknown layout.")
                vals["format"] = d["format"]
            state = d.get("state")
            if state is not None and state not in STATES:
                raise ValueError("Unknown state.")
        except (ValueError, TypeError) as e:
            return err(str(e))

        new_export = state == "kept" and m["state"] != "kept" and m["status"] != "done"
        if new_export:
            if usage(g.uid)["exports"] >= g.plan["exports"]:
                return err(f"You've used all {g.plan['exports']} exports on the {g.plan['name']} plan this "
                           "month. Upgrade for more.", 402, upgrade=True)
        if state is not None:
            vals["state"] = state
            if state == "kept" and (m["state"] != "kept" or m["status"] in ("idle", "error")):
                vals.update(status="queued", error=None)
            elif state == "discarded":
                for k in ("preview_key", "file_key", "thumb_key"):
                    storage.delete(m.get(k))
                vals.update(preview_key=None, pv_start=None, pv_end=None, file_key=None,
                            thumb_key=None, status="idle")
        if vals:
            vals["updated_at"] = now_iso()
            db.update("moments", vals, project_id=f"eq.{pid}", id=f"eq.{mid}")
        if vals.get("status") == "queued":
            enqueue(pid, "render", mid, priority=10)
        if new_export:
            db.rpc("add_usage", uid=g.uid, add_seconds=0, add_exports=1)
        return jsonify(moment_view(own_moment(pid, mid), p["title"]))

    @app.post("/api/projects/<pid>/moments/<mid>/recut")
    @login_required
    def recut(pid, mid):
        """Re-make a kept clip (new trim, layout or webcam box). Doesn't count as an export."""
        p = own_project(pid)
        m = own_moment(pid, mid)
        if m["state"] != "kept":
            return err("Keep the moment first.")
        d = request.get_json(silent=True) or {}
        vals = {"status": "queued", "error": None, "updated_at": now_iso()}
        if d.get("format"):
            if d["format"] not in FORMATS:
                return err("Unknown layout.")
            vals["format"] = d["format"]
        rect = d.get("facecam_rect")
        if rect is not None:
            try:
                rect = {k: float(rect[k]) for k in ("x", "y", "w", "h")}
            except (KeyError, TypeError, ValueError):
                return err("That webcam box isn't valid.")
            if not (0 <= rect["x"] < 1 and 0 <= rect["y"] < 1 and 0.03 <= rect["w"] <= 1
                    and 0.03 <= rect["h"] <= 1 and rect["x"] + rect["w"] <= 1.001 and rect["y"] + rect["h"] <= 1.001):
                return err("That webcam box is outside the frame.")
            db.update("projects", {"facecam": {"rect": rect, "source": "manual"}, "updated_at": now_iso()},
                      id=f"eq.{pid}")
        db.update("moments", vals, project_id=f"eq.{pid}", id=f"eq.{mid}")
        enqueue(pid, "render", mid, priority=10)
        return jsonify(ok=True), 202

    @app.post("/api/projects/<pid>/moments/<mid>/frame")
    @login_required
    def frame(pid, mid):
        own_project(pid)
        before = (own_moment(pid, mid).get("internal") or {}).get("frame_key")
        enqueue(pid, "frame", mid, priority=5)
        key = wait_for(lambda: (lambda k: k if k and k != before else None)(
            ((db.one("moments", "internal", project_id=f"eq.{pid}", id=f"eq.{mid}") or {}).get("internal") or {})
            .get("frame_key")), timeout=40)
        if not key:
            return err("Couldn't grab a frame right now. Try again.", 504)
        return jsonify(url=storage.url(key))

    @app.get("/api/projects/<pid>/kept.zip")
    @login_required
    def kept_zip(pid):
        p = own_project(pid)
        moms = db.select("moments", "*", project_id=f"eq.{pid}", state="eq.kept", status="eq.done",
                         order="start_s.asc")
        if not moms:
            return err("No finished clips yet.", 404)
        title = re.sub(r"[^\w\- ]+", "", p["title"] or "clips")[:50].strip() or "clips"
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
            for i, m in enumerate(moms, 1):
                name = f"{title} - {i:03d} - {m['label'].replace(':', '.').replace('–', ' to ')}.mp4"
                if storage.r2_enabled():
                    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
                        urllib.request.urlretrieve(storage.url(m["file_key"]), f.name)
                        z.write(f.name, name)
                else:
                    path = storage.local_path(m["file_key"])
                    if path:
                        z.write(path, name)
        tmp.close()
        resp = send_file(tmp.name, as_attachment=True, download_name=f"{title} - kept clips.zip",
                         mimetype="application/zip", max_age=0)
        resp.call_on_close(lambda: os.remove(tmp.name))
        return resp

    # ------------------------------------------------------------ local files (dev only)
    @app.get("/files/<path:key>")
    def files(key):
        if storage.r2_enabled() or not storage.verify(key, request.args.get("exp", ""), request.args.get("sig", "")):
            abort(404)
        path = storage.local_path(key)
        if not path:
            abort(404)
        dl = request.args.get("dl")
        return send_file(path, as_attachment=bool(dl), download_name=dl or None, conditional=True, max_age=0)

    # ------------------------------------------------------------ billing (Paddle)
    @app.post("/api/billing/portal")
    @login_required
    def billing_portal():
        cust = g.profile.get("billing_customer")
        if not (config.PADDLE_API_KEY and cust):
            return err("There's no subscription to manage yet.")
        body = {"subscription_ids": [g.profile["billing_subscription"]] if g.profile.get("billing_subscription") else []}
        req = urllib.request.Request(f"{config.PADDLE_API}/customers/{cust}/portal-sessions", method="POST",
                                     data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {config.PADDLE_API_KEY}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)["data"]
        except Exception:
            return err("Couldn't open the billing portal right now. Try again in a minute.", 502)
        return jsonify(url=data["urls"]["general"]["overview"])

    @app.post("/api/billing/webhook")
    def webhook():
        secret = config.PADDLE_WEBHOOK_SECRET
        if not secret:
            abort(404)
        raw = request.get_data()
        parts = dict(x.split("=", 1) for x in request.headers.get("Paddle-Signature", "").split(";") if "=" in x)
        ts, sig = parts.get("ts", ""), parts.get("h1", "")
        try:
            fresh = abs(time.time() - int(ts)) <= 300
        except ValueError:
            fresh = False
        good = hmac.compare_digest(hmac.new(secret.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest(), sig)
        if not (fresh and good):
            return err("bad signature")
        event = json.loads(raw)
        if event.get("event_type", "").startswith("subscription."):
            sub = event.get("data") or {}
            uid = str((sub.get("custom_data") or {}).get("user_id") or "")
            prof = db.one("profiles", "*", id=f"eq.{uid}") if re.fullmatch(r"[0-9a-f-]{36}", uid) else None
            if not prof and sub.get("customer_id"):
                prof = db.one("profiles", "*", billing_customer=f"eq.{sub['customer_id']}")
            if prof:
                items = sub.get("items") or []
                pid = ((items[0].get("price") or {}).get("id")) if items else None
                plan = next((k for k in config.PAID_PLANS if pid and config.price_id(k) == pid), None)
                status = sub.get("status", "")
                vals = {"billing_customer": sub.get("customer_id"), "plan_status": status}
                if status in ("active", "trialing", "past_due") and plan:
                    vals.update(plan=plan, billing_subscription=sub.get("id"))
                else:
                    vals.update(plan="free", billing_subscription=None)
                db.update("profiles", vals, id=f"eq.{prof['id']}")
        return jsonify(ok=True)

    @app.errorhandler(SupabaseError)
    def supa_error(e):
        app.logger.error("supabase: %s", e)
        return err("Something went wrong on our side. Please try again.", 502)

    @app.errorhandler(404)
    def nf(e):
        return err("Not found.", 404)

    return app
