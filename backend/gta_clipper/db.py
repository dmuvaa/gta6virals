"""SQLite storage for users, monthly usage and project ownership.
(Clip/job details stay in each job's folder; this only tracks who owns what.)"""
from __future__ import annotations

import os
import sqlite3
import threading
import time

from . import config

_local = threading.local()
_init_lock = threading.Lock()
_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL DEFAULT '',
    pw_hash TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    plan_status TEXT NOT NULL DEFAULT '',
    billing_customer TEXT,
    billing_subscription TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL,           -- YYYY-MM (UTC)
    seconds_scanned REAL NOT NULL DEFAULT 0,
    exports INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, period)
);
CREATE TABLE IF NOT EXISTS projects (
    job_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS projects_user ON projects(user_id, created);
"""


def conn() -> sqlite3.Connection:
    global _ready
    c = getattr(_local, "c", None)
    if c is None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.c = c
    if not _ready:
        with _init_lock:
            if not _ready:
                c.executescript(SCHEMA)
                _ready = True
    return c


def period(ts: float | None = None) -> str:
    return time.strftime("%Y-%m", time.gmtime(ts or time.time()))


# ---------------- users
def create_user(email: str, name: str, pw_hash: str) -> int:
    cur = conn().execute("INSERT INTO users (email, name, pw_hash, created) VALUES (?, ?, ?, ?)",
                         (email.strip().lower(), name.strip(), pw_hash, time.time()))
    return int(cur.lastrowid)


def user_by_email(email: str):
    return conn().execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()


def user_by_id(uid: int):
    return conn().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def user_by_customer(customer: str):
    return conn().execute("SELECT * FROM users WHERE billing_customer = ?", (customer,)).fetchone()


def update_user(uid: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn().execute(f"UPDATE users SET {cols} WHERE id = ?", (*fields.values(), uid))


def delete_user(uid: int):
    c = conn()
    c.execute("DELETE FROM usage WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM projects WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM users WHERE id = ?", (uid,))


# ---------------- usage
def usage(uid: int) -> dict:
    row = conn().execute("SELECT seconds_scanned, exports FROM usage WHERE user_id = ? AND period = ?",
                         (uid, period())).fetchone()
    return {"seconds": row["seconds_scanned"] if row else 0.0, "exports": row["exports"] if row else 0}


def add_usage(uid: int, seconds: float = 0, exports: int = 0):
    conn().execute(
        "INSERT INTO usage (user_id, period, seconds_scanned, exports) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, period) DO UPDATE SET seconds_scanned = seconds_scanned + excluded.seconds_scanned, "
        "exports = exports + excluded.exports",
        (uid, period(), seconds, exports))


# ---------------- projects
def add_project(job_id: str, uid: int):
    conn().execute("INSERT OR REPLACE INTO projects (job_id, user_id, created) VALUES (?, ?, ?)",
                   (job_id, uid, time.time()))


def project_owner(job_id: str) -> int | None:
    row = conn().execute("SELECT user_id FROM projects WHERE job_id = ?", (job_id,)).fetchone()
    return row["user_id"] if row else None


def user_projects(uid: int) -> list[str]:
    return [r["job_id"] for r in conn().execute(
        "SELECT job_id FROM projects WHERE user_id = ? ORDER BY created DESC", (uid,))]


def delete_project(job_id: str):
    conn().execute("DELETE FROM projects WHERE job_id = ?", (job_id,))
