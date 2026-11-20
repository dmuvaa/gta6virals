"""Web app: pages, accounts, billing and the JSON API used by the review workspace."""
from __future__ import annotations

import datetime
import os
import re
import threading

from flask import Flask, abort, g, jsonify, render_template, request, send_from_directory

from . import auth, billing, config, db, download, pipeline, render, web

HERE = os.path.dirname(os.path.abspath(__file__))


def create_app() -> Flask:
    app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static",
                template_folder=os.path.join(HERE, "templates"))
    app.config.update(
        SECRET_KEY=config.secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SITE_URL.startswith("https://"),
        PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SEND_FILE_MAX_AGE_DEFAULT=3600,
    )
    db.conn()
    pipeline.load_jobs()
    pipeline.start_janitor()
    app.register_blueprint(web.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(billing.bp)

    @app.before_request
    def before():
        auth.load_user()
        # JSON API: reject non-JSON POSTs, so other sites can't submit forms against it.
        if request.method == "POST" and request.path.startswith("/api/") and not request.is_json:
            return jsonify(error="Expected JSON."), 415

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.path.startswith(("/app", "/api/", "/files/", "/login", "/signup")):
            resp.headers.setdefault("X-Robots-Tag", "noindex")
        return resp

    @app.context_processor
    def inject():
        return {"brand": config.BRAND, "tagline": config.TAGLINE, "site_url": config.SITE_URL,
                "support_email": config.SUPPORT_EMAIL, "company": config.COMPANY,
                "plans": config.PLANS, "user": g.get("user"), "csrf_token": auth.csrf_token,
                "year": datetime.date.today().year, "billing_enabled": config.billing_enabled()}

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith(("/api/", "/files/")):
            return jsonify(error="Not found."), 404
        return render_template("404.html", title=f"Page not found · {config.BRAND}",
                               description="This page doesn't exist.", canonical=None, noindex=True), 404

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True)

    # ------------------------------------------------------------------ API helpers
    def _job(jid):
        job = pipeline.JOBS.get(jid)
        if not job or not web.can_access(jid):
            abort(404)
        return job

    def _moment(job, cid):
        try:
            return job._moment(cid)
        except KeyError:
            abort(404)

    def _plan():
        return config.PLANS.get(g.user["plan"], config.PLANS["free"])

    def _quota_hook(uid: int):
        """Called by the job once the video's length is known: checks hours left this month."""
        def check(seconds: float):
            user = db.user_by_id(uid)
            plan = config.PLANS.get(user["plan"], config.PLANS["free"]) if user else config.PLANS["free"]
            used = db.usage(uid)["seconds"]
            left = plan["hours"] * 3600 - used
            if seconds > left + 60:
                raise ValueError(
                    f"This needs {seconds / 3600:.1f} hours of scanning, but your {plan['name']} plan has "
                    f"{max(0, left) / 3600:.1f} hours left this month. Scan a shorter range or upgrade.")
            db.add_usage(uid, seconds=seconds)
        return check

    # ------------------------------------------------------------------ API
    @app.post("/api/probe")
    @auth.login_required
    def probe():
        url = (request.json or {}).get("url", "").strip()
        if not url:
            return jsonify(error="Paste a YouTube or Twitch link."), 400
        try:
            info = download.probe(url)
        except Exception as e:
            return jsonify(error=pipeline._friendly(e)), 400
        info.pop("heatmap", None)
        info.pop("_raw", None)
        return jsonify(info)

    @app.post("/api/jobs")
    @auth.login_required
    def create_job():
        d = request.json or {}
        url = (d.get("url") or "").strip()
        if not re.match(r"https?://", url):
            return jsonify(error="Paste a full YouTube or Twitch link (starting with https://)."), 400
        if pipeline.disk_free_gb() < pipeline.MIN_FREE_GB:
            return jsonify(error="We're at capacity right now. Please try again in a little while."), 503
        busy = sum(1 for j in db.user_projects(g.user["id"])
                   if j in pipeline.JOBS and pipeline.JOBS[j].stage in ("queued", "probing", "downloading", "analyzing"))
        if busy >= 2:
            return jsonify(error="You already have 2 projects scanning. Wait for one to finish."), 429
        plan = _plan()
        try:
            fmt = d.get("format", "vertical_facecam")
            if fmt not in render.FORMATS:
                raise ValueError("Unknown output format.")
            corner = d.get("facecam_corner", "auto")
            if corner not in render.FACECAM_CORNERS:
                raise ValueError("Unknown webcam setting.")
            job = pipeline.start_job(
                quota=_quota_hook(g.user["id"]),
                url=url, owner=g.user["id"],
                count=max(0, min(500, int(d.get("count") or 0))),
                clip_len=max(15.0, min(60.0, float(d.get("clip_len") or 45))),
                fmt=fmt, facecam_corner=corner,
                captions=bool(d.get("captions")) and plan["captions"],
                watermark=f"Made with {config.BRAND}" if plan["watermark"] else "",
                max_seconds=plan["max_video_hours"] * 3600,
                start=pipeline.parse_time(d.get("start")),
                end=pipeline.parse_time(d.get("end")),
            )
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        db.add_project(job.id, g.user["id"])
        return jsonify(job.to_dict()), 201

    @app.get("/api/jobs")
    @auth.login_required
    def list_jobs():
        jobs = [pipeline.JOBS[j] for j in db.user_projects(g.user["id"]) if j in pipeline.JOBS]
        return jsonify([web.project_summary(j) for j in jobs])

    @app.get("/api/jobs/<jid>")
    @auth.login_required
    def get_job(jid):
        job = _job(jid)
        if job.stage == "review":
            job.start_prefetch()  # resumes background previews after a restart
        return jsonify(job.to_dict())

    @app.post("/api/jobs/<jid>/delete")
    @auth.login_required
    def delete_job(jid):
        _job(jid)
        pipeline.delete_job(jid)
        db.delete_project(jid)
        return jsonify(ok=True)

    @app.post("/api/jobs/<jid>/moments/<cid>/preview")
    @auth.login_required
    def preview(jid, cid):
        job = _job(jid)
        _moment(job, cid)
        try:
            c = job.ensure_preview(cid)
        except Exception as e:
            return jsonify(error=pipeline._friendly(e)), 500
        return jsonify(url=f"/files/{jid}/{c['preview']}", start=c["pv_start"], end=c["pv_end"],
                       flag=c.get("flag"))

    @app.post("/api/jobs/<jid>/moments/<cid>")
    @auth.login_required
    def update_moment(jid, cid):
        job = _job(jid)
        c = _moment(job, cid)
        d = request.json or {}
        try:
            if "start" in d or "end" in d:
                ws = job.window[0]
                s0 = pipeline.parse_time(d.get("start"))
                e0 = pipeline.parse_time(d.get("end"))
                job.set_bounds(cid, c["start"] if s0 is None else s0 - ws,
                               c["end"] if e0 is None else e0 - ws)
            if "format" in d:
                if d["format"] not in render.FORMATS:
                    raise ValueError("Unknown output format.")
                c["format"] = d["format"]
            if "state" in d:
                new_export = d["state"] == "kept" and c.get("state") != "kept" and c.get("status") != "done"
                if new_export:
                    plan = _plan()
                    used = db.usage(g.user["id"])["exports"]
                    if used >= plan["exports"]:
                        return jsonify(error=f"You've used all {plan['exports']} exports on the "
                                             f"{plan['name']} plan this month. Upgrade for more.",
                                       upgrade=True), 402
                job.set_state(cid, d["state"])
                if new_export:
                    db.add_usage(g.user["id"], exports=1)
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        return jsonify({k: v for k, v in c.items() if not k.startswith("_")})

    @app.post("/api/jobs/<jid>/settings")
    @auth.login_required
    def settings(jid):
        job = _job(jid)
        d = request.json or {}
        if "format" in d:
            if d["format"] not in render.FORMATS:
                return jsonify(error="Unknown output format."), 400
            job.fmt = d["format"]
        if "captions" in d:
            if d["captions"] and not _plan()["captions"]:
                return jsonify(error="Captions are included in the Creator and Pro plans.", upgrade=True), 402
            job.captions = bool(d["captions"])
        job.save()
        return jsonify(ok=True)

    @app.get("/api/jobs/<jid>/kept.zip")
    @auth.login_required
    def kept_zip(jid):
        job = _job(jid)
        path = job.kept_zip()
        title = re.sub(r"[^\w\- ]+", "", job.info.get("title", "clips"))[:50].strip() or "clips"
        return send_from_directory(job.dir, os.path.basename(path), as_attachment=True,
                                   download_name=f"{title} - kept clips.zip", max_age=0)

    @app.post("/api/jobs/<jid>/cancel")
    @auth.login_required
    def cancel(jid):
        _job(jid).cancelled = True
        return jsonify(ok=True)

    @app.post("/api/jobs/<jid>/clips/<cid>/recut")
    @auth.login_required
    def recut(jid, cid):
        job = _job(jid)
        if job.stage not in ("done", "review"):
            return jsonify(error="Wait for the scan to finish first."), 409
        d = request.json or {}
        c = _moment(job, cid)
        try:
            ws = job.window[0]
            # The UI speaks source-video time; the pipeline works in window time.
            start = pipeline.parse_time(d.get("start"))
            end = pipeline.parse_time(d.get("end"))
            start = c["start"] if start is None else start - ws
            end = c["end"] if end is None else end - ws
            fmt = d.get("format") or c.get("format")
            if fmt not in render.FORMATS:
                raise ValueError("Unknown output format.")
            rect = d.get("facecam_rect")
            if rect is not None:
                rect = {k: float(rect[k]) for k in ("x", "y", "w", "h")}
                if not (0 <= rect["x"] < 1 and 0 <= rect["y"] < 1 and 0.03 <= rect["w"] <= 1
                        and 0.03 <= rect["h"] <= 1 and rect["x"] + rect["w"] <= 1.001
                        and rect["y"] + rect["h"] <= 1.001):
                    raise ValueError("That webcam box is outside the frame.")
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        c["status"], c["error"] = "rendering", None

        def work():
            try:
                job.recut(cid, start, end, fmt, rect)
            except Exception:
                pass  # error is stored on the clip
        threading.Thread(target=work, daemon=True).start()
        return jsonify(ok=True), 202

    @app.get("/api/jobs/<jid>/clips/<cid>/frame")
    @auth.login_required
    def frame(jid, cid):
        job = _job(jid)
        _moment(job, cid)
        try:
            path = job.source_frame(cid)
        except Exception as e:
            return jsonify(error=pipeline._friendly(e)), 500
        return send_from_directory(os.path.dirname(path), os.path.basename(path), max_age=0)

    @app.get("/files/<jid>/<path:rel>")
    @auth.login_required
    def files(jid, rel):
        job = _job(jid)
        if not rel.startswith(("clips/", "previews/")):
            abort(404)
        as_dl = request.args.get("download") == "1"
        name = None
        if as_dl:
            title = re.sub(r"[^\w\- ]+", "", job.info.get("title", "clip"))[:60].strip() or "clip"
            cid = os.path.basename(rel).split("_")[0]
            name = f"{title} - {cid}.mp4"
        return send_from_directory(job.dir, rel, as_attachment=as_dl, download_name=name,
                                   conditional=True, max_age=0)

    return app
