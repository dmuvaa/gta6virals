"""Accounts: sign up, log in, log out, session handling, CSRF for forms."""
from __future__ import annotations

import functools
import hmac
import re
import secrets
import time
from collections import defaultdict, deque

from flask import (Blueprint, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_attempts: dict[str, deque] = defaultdict(deque)   # ip -> recent failed login times


# ---------------- session / current user
def load_user():
    uid = session.get("uid")
    g.user = db.user_by_id(uid) if uid else None
    if uid and g.user is None:
        session.clear()


def is_admin(user) -> bool:
    return bool(user) and user["email"].lower() in config.ADMIN_EMAILS


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if g.get("user") is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in."), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*a, **kw)
    return wrapped


def _login(user):
    session.clear()
    session["uid"] = user["id"]
    session.permanent = True


def _safe_next(target: str | None) -> str:
    # Only allow redirects within this site.
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("pages.dashboard")


# ---------------- CSRF (forms only; the JSON API relies on SameSite cookies + JSON bodies)
def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    sent = request.form.get("csrf_token", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400, "Your session expired. Please reload the page and try again.")


def _too_many(ip: str) -> bool:
    q = _attempts[ip]
    now = time.time()
    while q and q[0] < now - 900:
        q.popleft()
    return len(q) >= 10


# ---------------- routes
@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("pages.dashboard"))
    form = {"email": "", "name": ""}
    if request.method == "POST":
        check_csrf()
        email = request.form.get("email", "").strip()
        name = request.form.get("name", "").strip()[:80]
        pw = request.form.get("password", "")
        form = {"email": email, "name": name}
        if not EMAIL_RE.match(email):
            flash("Enter a valid email address.", "error")
        elif len(pw) < 8:
            flash("Use a password with at least 8 characters.", "error")
        elif not request.form.get("agree"):
            flash("Please accept the Terms and Privacy Policy.", "error")
        elif db.user_by_email(email):
            flash("An account with that email already exists. Log in instead.", "error")
        else:
            uid = db.create_user(email, name, generate_password_hash(pw))
            _login(db.user_by_id(uid))
            return redirect(_safe_next(request.args.get("next")))
    return render_template("auth/signup.html", form=form,
                           title=f"Create your account · {config.BRAND}",
                           description=f"Sign up for {config.BRAND} for free.")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("pages.dashboard"))
    email = ""
    if request.method == "POST":
        check_csrf()
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        email = request.form.get("email", "").strip()
        if _too_many(ip):
            flash("Too many attempts. Wait a few minutes and try again.", "error")
        else:
            user = db.user_by_email(email)
            if user and check_password_hash(user["pw_hash"], request.form.get("password", "")):
                _attempts.pop(ip, None)
                _login(user)
                return redirect(_safe_next(request.args.get("next")))
            _attempts[ip].append(time.time())
            flash("That email and password don't match.", "error")
    return render_template("auth/login.html", email=email, title=f"Log in · {config.BRAND}",
                           description=f"Log in to {config.BRAND}.")


@bp.post("/logout")
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("pages.home"))


@bp.post("/account/password")
@login_required
def change_password():
    check_csrf()
    if not check_password_hash(g.user["pw_hash"], request.form.get("current", "")):
        flash("Your current password is wrong.", "error")
    elif len(request.form.get("new", "")) < 8:
        flash("Use a new password with at least 8 characters.", "error")
    else:
        db.update_user(g.user["id"], pw_hash=generate_password_hash(request.form["new"]))
        flash("Password updated.", "ok")
    return redirect(url_for("pages.account"))


@bp.post("/account/delete")
@login_required
def delete_account():
    check_csrf()
    if request.form.get("confirm", "").strip().lower() != g.user["email"].lower():
        flash("Type your email to confirm deleting your account.", "error")
        return redirect(url_for("pages.account"))
    from . import pipeline
    for jid in db.user_projects(g.user["id"]):
        pipeline.delete_job(jid)
    db.delete_user(g.user["id"])
    session.clear()
    flash("Your account and all your projects were deleted.", "ok")
    return redirect(url_for("pages.home"))
