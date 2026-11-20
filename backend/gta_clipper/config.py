"""Site-wide settings. Brand and plans live here so they're easy to change."""
from __future__ import annotations

import os

BRAND = os.environ.get("BRAND_NAME", "Hypecut")
TAGLINE = "Turn 12-hour streams into hundreds of clips, in minutes."
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8765").rstrip("/")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@example.com")
COMPANY = os.environ.get("COMPANY_NAME", BRAND)

# Monthly limits per plan. "hours" = hours of video scanned; "exports" = clips made in HD.
PLANS = {
    "free": {
        "name": "Free", "price": 0, "hours": 3, "exports": 10,
        "captions": False, "watermark": True, "max_video_hours": 4,
        "blurb": "Try the full review workflow on a few streams.",
        "features": ["3 hours of video per month", "10 HD clip exports", "All 9:16 and 16:9 layouts",
                     "Webcam auto-detect", "Small watermark on exports"],
    },
    "creator": {
        "name": "Creator", "price": 19, "hours": 60, "exports": 300,
        "captions": True, "watermark": False, "max_video_hours": 24,
        "blurb": "For clippers posting every day.",
        "features": ["60 hours of video per month", "300 HD clip exports", "Burned-in captions",
                     "No watermark", "Streams up to 24 hours", "Download all as .zip"],
        "price_env": "PADDLE_PRICE_CREATOR",
    },
    "pro": {
        "name": "Pro", "price": 49, "hours": 300, "exports": 2000,
        "captions": True, "watermark": False, "max_video_hours": 24,
        "blurb": "For full-time clippers and small teams.",
        "features": ["300 hours of video per month", "2,000 HD clip exports", "Everything in Creator",
                     "Priority processing", "Email support"],
        "price_env": "PADDLE_PRICE_PRO",
    },
}
PAID_PLANS = [k for k in PLANS if PLANS[k]["price"] > 0]


# Paddle Billing (merchant of record: handles checkout, tax/VAT and payouts).
PADDLE_ENV = os.environ.get("PADDLE_ENV", "sandbox")          # "sandbox" or "production"
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")  # public, used by Paddle.js
PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")            # secret, server-side only
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_API = "https://api.paddle.com" if PADDLE_ENV == "production" else "https://sandbox-api.paddle.com"


def price_id(plan: str) -> str | None:
    env = PLANS.get(plan, {}).get("price_env")
    return os.environ.get(env) if env else None


def billing_enabled() -> bool:
    return bool(PADDLE_CLIENT_TOKEN and PADDLE_WEBHOOK_SECRET) and all(price_id(p) for p in PAID_PLANS)


ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
