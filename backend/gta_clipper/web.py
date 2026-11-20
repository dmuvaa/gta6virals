"""Pages: marketing site, legal, app shell (dashboard / project / account), SEO files."""
from __future__ import annotations

import time

from flask import Blueprint, Response, abort, g, render_template, request, url_for

from . import auth, config, db, pipeline

bp = Blueprint("pages", __name__)

FAQ = [
    ("What does it do?",
     "Paste a YouTube or Twitch link to a stream or video. We scan the whole thing, even 24-hour "
     "streams, and line up every moment with action: big reactions, chaos, chases, shootouts. "
     "You play through them, keep the good ones, and download them as ready-to-post clips."),
    ("How fast is it?",
     "Scanning works from the audio over many parallel connections, so a 12-hour stream is "
     "usually ready to review in a few minutes. Previews load in under a second, and kept clips "
     "are made in HD in seconds."),
    ("How many clips will I get?",
     "About 13 moments per hour of stream, 15 to 45 seconds each. A 24-hour stream gives "
     "around 300 moments. You decide which ones become clips."),
    ("Which formats can I export?",
     "9:16 with the streamer's webcam on top and gameplay below (the webcam is found "
     "automatically), 9:16 with a blurred background, 9:16 center crop, or the original 16:9. "
     "Paid plans add burned-in captions with word-by-word highlighting."),
    ("Is it only for GTA VI?",
     "It's tuned for GTA VI streams (webcam layouts, gameplay detection), but it works on "
     "any gaming or IRL stream on YouTube or Twitch."),
    ("Can I use it for clipping campaigns?",
     "Yes. Many streamers pay clippers per view through clipping campaigns. Always follow each "
     "campaign's rules, and only clip content you have permission to use."),
    ("Can I cancel anytime?",
     "Yes. Plans are monthly and you can cancel from your account page. You keep your plan "
     "until the end of the billing period."),
    ("Do you store my videos?",
     "Projects and clips are stored temporarily so you can review and download them, then "
     "deleted automatically. You can also delete a project or your whole account at any time."),
]


def _meta(title, description, path=None, **extra):
    return dict(title=title, description=description,
                canonical=config.SITE_URL + (path if path is not None else request.path), **extra)


# ---------------- marketing
@bp.get("/")
def home():
    return render_template("home.html", faq=FAQ, **_meta(
        f"{config.BRAND}: turn long streams into hundreds of clips",
        f"{config.BRAND} scans entire YouTube and Twitch streams in minutes and lines up every "
        "moment with action. Review fast, keep the best, export 9:16 clips with captions.", "/"))


@bp.get("/pricing")
def pricing():
    return render_template("pricing.html", faq=FAQ[4:], **_meta(
        f"Pricing · {config.BRAND}",
        f"Start free. {config.BRAND} Creator and Pro plans for clippers who post every day."))


@bp.get("/faq")
def faq():
    return render_template("faq.html", faq=FAQ, **_meta(
        f"FAQ · {config.BRAND}", f"Answers to common questions about {config.BRAND}."))


@bp.get("/legal/terms")
def terms():
    return render_template("legal/terms.html", **_meta(f"Terms of Service · {config.BRAND}",
                                                      f"Terms of Service for {config.BRAND}."))


@bp.get("/legal/privacy")
def privacy():
    return render_template("legal/privacy.html", **_meta(f"Privacy Policy · {config.BRAND}",
                                                        f"How {config.BRAND} handles your data."))


@bp.get("/legal/copyright")
def copyright_policy():
    return render_template("legal/copyright.html", **_meta(
        f"Copyright & DMCA · {config.BRAND}", f"Copyright policy and takedown requests for {config.BRAND}."))


@bp.get("/robots.txt")
def robots():
    body = (f"User-agent: *\nAllow: /\nDisallow: /app\nDisallow: /api/\nDisallow: /billing/\n"
            f"Disallow: /files/\n\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    pages = [("/", "1.0", "weekly"), ("/pricing", "0.8", "monthly"), ("/faq", "0.6", "monthly"),
             ("/signup", "0.5", "yearly"), ("/legal/terms", "0.2", "yearly"),
             ("/legal/privacy", "0.2", "yearly"), ("/legal/copyright", "0.2", "yearly")]
    today = time.strftime("%Y-%m-%d")
    urls = "".join(f"<url><loc>{config.SITE_URL}{p}</loc><lastmod>{today}</lastmod>"
                   f"<changefreq>{f}</changefreq><priority>{pr}</priority></url>" for p, pr, f in pages)
    return Response('<?xml version="1.0" encoding="UTF-8"?>'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    mimetype="application/xml")


# ---------------- app
def plan_info(user) -> dict:
    plan = config.PLANS.get(user["plan"], config.PLANS["free"])
    use = db.usage(user["id"])
    return {"key": user["plan"] if user["plan"] in config.PLANS else "free", **plan,
            "used_hours": use["seconds"] / 3600, "used_exports": use["exports"]}


def project_summary(job) -> dict:
    kept = [c for c in job.clips if c.get("state") == "kept"]
    return {"id": job.id, "title": job.info.get("title") or job.url, "url": job.url,
            "platform": job.info.get("platform", ""), "uploader": job.info.get("uploader", ""),
            "thumbnail": job.info.get("thumbnail"), "created": job.created, "stage": job.stage,
            "message": job.message, "progress": job.progress,
            "length": (job.window[1] - job.window[0]) if job.window[1] else job.info.get("duration", 0),
            "moments": len(job.clips) if job.mode == "fast" else 0, "kept": len(kept),
            "ready": sum(c.get("status") == "done" for c in kept)}


@bp.get("/app")
@auth.login_required
def dashboard():
    jobs = [pipeline.JOBS[j] for j in db.user_projects(g.user["id"]) if j in pipeline.JOBS]
    return render_template("app/dashboard.html", projects=[project_summary(j) for j in jobs],
                           plan=plan_info(g.user), **_meta(f"Dashboard · {config.BRAND}",
                                                           f"Your {config.BRAND} projects.", noindex=True))


@bp.get("/app/new")
@auth.login_required
def new_project():
    return render_template("app/new.html", plan=plan_info(g.user),
                           **_meta(f"New project · {config.BRAND}", "Start a new project.", noindex=True))


@bp.get("/app/p/<jid>")
@auth.login_required
def project(jid):
    job = pipeline.JOBS.get(jid)
    if not job or not can_access(jid):
        abort(404)
    return render_template("app/project.html", job=project_summary(job), plan=plan_info(g.user),
                           **_meta(f"{job.info.get('title') or 'Project'} · {config.BRAND}",
                                   "Review moments.", noindex=True))


@bp.get("/app/account")
@auth.login_required
def account():
    return render_template("app/account.html", plan=plan_info(g.user),
                           billing=config.billing_enabled(), upgraded=request.args.get("upgraded"),
                           **_meta(f"Account · {config.BRAND}", "Your account.", noindex=True))


def can_access(jid: str) -> bool:
    user = g.get("user")
    if not user:
        return False
    return db.project_owner(jid) == user["id"] or auth.is_admin(user)
