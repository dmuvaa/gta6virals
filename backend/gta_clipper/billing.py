"""Paddle Billing: checkout (Paddle.js overlay), customer portal, webhook.

Paddle is the merchant of record: it runs checkout, charges customers, handles sales tax /
VAT, and pays you out. Turned on by setting PADDLE_CLIENT_TOKEN, PADDLE_API_KEY,
PADDLE_WEBHOOK_SECRET, PADDLE_PRICE_CREATOR and PADDLE_PRICE_PRO (and PADDLE_ENV=production
when you go live). Until then the pricing page explains that paid plans open soon."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request

from flask import Blueprint, abort, flash, g, jsonify, redirect, request, url_for

from . import auth, config, db

bp = Blueprint("billing", __name__, url_prefix="/billing")


def _plan_for_price(pid: str | None) -> str | None:
    return next((p for p in config.PAID_PLANS if pid and config.price_id(p) == pid), None)


def _paddle_api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        config.PADDLE_API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {config.PADDLE_API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


@bp.get("/checkout-config")
@auth.login_required
def checkout_config():
    """What the browser needs to open Paddle's checkout for the logged-in user."""
    if not config.billing_enabled():
        return jsonify(error="Paid plans aren't open yet. You'll be able to upgrade here soon."), 503
    return jsonify(
        environment=config.PADDLE_ENV, token=config.PADDLE_CLIENT_TOKEN,
        prices={p: config.price_id(p) for p in config.PAID_PLANS},
        email=g.user["email"], user_id=str(g.user["id"]),
        success_url=config.SITE_URL + url_for("pages.account") + "?upgraded=1")


@bp.post("/portal")
@auth.login_required
def portal():
    auth.check_csrf()
    customer = g.user["billing_customer"]
    if not (config.billing_enabled() and config.PADDLE_API_KEY and customer):
        flash("There's no subscription to manage yet.", "error")
        return redirect(url_for("pages.account"))
    try:
        subs = [g.user["billing_subscription"]] if g.user["billing_subscription"] else []
        data = _paddle_api("POST", f"/customers/{customer}/portal-sessions",
                           {"subscription_ids": subs})["data"]
        return redirect(data["urls"]["general"]["overview"], code=303)
    except Exception:
        flash("Couldn't open the billing portal right now. Please try again in a minute.", "error")
        return redirect(url_for("pages.account"))


def _valid_signature(raw: bytes, header: str) -> bool:
    """Paddle-Signature: ts=<unix>;h1=<hex hmac-sha256 of "<ts>:<raw body>">."""
    parts = dict(p.split("=", 1) for p in header.split(";") if "=" in p)
    ts, sig = parts.get("ts", ""), parts.get("h1", "")
    if not ts or not sig or abs(time.time() - int(ts)) > 300:   # reject stale / replayed events
        return False
    expected = hmac.new(config.PADDLE_WEBHOOK_SECRET.encode(), f"{ts}:".encode() + raw,
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@bp.post("/webhook")
def webhook():
    if not config.PADDLE_WEBHOOK_SECRET:
        abort(404)
    raw = request.get_data()
    try:
        ok = _valid_signature(raw, request.headers.get("Paddle-Signature", ""))
    except (ValueError, TypeError):
        ok = False
    if not ok:
        return jsonify(error="bad signature"), 400
    event = json.loads(raw)
    kind, data = event.get("event_type", ""), event.get("data") or {}
    if kind.startswith("subscription."):
        _apply_subscription(data)
    return jsonify(ok=True)


def _apply_subscription(sub: dict):
    """Keep a user's plan in step with their Paddle subscription."""
    custom = sub.get("custom_data") or {}
    user = None
    if str(custom.get("user_id", "")).isdigit():
        user = db.user_by_id(int(custom["user_id"]))
    if user is None and sub.get("customer_id"):
        user = db.user_by_customer(sub["customer_id"])
    if user is None:
        return
    items = sub.get("items") or []
    plan = _plan_for_price(((items[0].get("price") or {}).get("id")) if items else None)
    status = sub.get("status", "")
    fields = {"billing_customer": sub.get("customer_id"), "plan_status": status}
    if status in ("active", "trialing", "past_due") and plan:
        fields.update(plan=plan, billing_subscription=sub.get("id"))
    else:   # canceled / paused
        fields.update(plan="free", billing_subscription=None)
    db.update_user(user["id"], **fields)
