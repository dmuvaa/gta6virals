"""Tiny Supabase client for the backend: PostgREST (tables + RPC) and Auth, over HTTPS.

Uses the project's *secret* key, which bypasses row-level security, so this module must
only ever run on our servers (API + worker), never in the browser."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} is not set (see .env.example)")
    return v


class SupabaseError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Supabase {status}: {body[:300]}")
        self.status, self.body = status, body


class Supabase:
    def __init__(self, url: str | None = None, secret: str | None = None):
        self.url = (url or _env("SUPABASE_URL")).rstrip("/")
        self.secret = secret or _env("SUPABASE_SECRET_KEY")
        self._users: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- HTTP
    def _req(self, method: str, path: str, body=None, headers: dict | None = None,
             params: dict | None = None, tries: int = 3):
        url = self.url + path
        if params:
            url += "?" + urllib.parse.urlencode(params, safe=",.()*:")
        h = {"apikey": self.secret, "Authorization": f"Bearer {self.secret}",
             "Content-Type": "application/json", "Accept": "application/json"}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(tries):
            req = urllib.request.Request(url, data=data, method=method, headers=h)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")
                if e.code >= 500 and attempt < tries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise SupabaseError(e.code, text) from None
            except urllib.error.URLError:
                if attempt == tries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))

    # ---------------------------------------------------------------- tables
    def select(self, table: str, columns: str = "*", **filters) -> list[dict]:
        """select("projects", "id,title", user_id="eq.<uuid>", order="created_at.desc")"""
        params = {"select": columns, **filters}
        return self._req("GET", f"/rest/v1/{table}", params=params) or []

    def one(self, table: str, columns: str = "*", **filters) -> dict | None:
        rows = self.select(table, columns, limit="1", **filters)
        return rows[0] if rows else None

    def insert(self, table: str, rows, upsert: bool = False, on_conflict: str | None = None,
               returning: bool = False):
        prefer = ["return=representation" if returning else "return=minimal"]
        if upsert:
            prefer.append("resolution=merge-duplicates")
        params = {"on_conflict": on_conflict} if on_conflict else None
        return self._req("POST", f"/rest/v1/{table}", rows, {"Prefer": ",".join(prefer)}, params)

    def update(self, table: str, values: dict, returning: bool = False, **filters):
        prefer = "return=representation" if returning else "return=minimal"
        return self._req("PATCH", f"/rest/v1/{table}", values, {"Prefer": prefer}, filters)

    def delete(self, table: str, **filters):
        return self._req("DELETE", f"/rest/v1/{table}", None, {"Prefer": "return=minimal"}, filters)

    def rpc(self, fn: str, **args):
        return self._req("POST", f"/rest/v1/rpc/{fn}", args)

    # ---------------------------------------------------------------- auth
    def user_from_token(self, token: str) -> dict | None:
        """Validate a user's access token with Supabase Auth (cached for 60 s)."""
        if not token:
            return None
        now = time.time()
        with self._lock:
            hit = self._users.get(token)
            if hit and hit[0] > now:
                return hit[1]
        req = urllib.request.Request(self.url + "/auth/v1/user", headers={
            "apikey": self.secret, "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                user = json.load(r)
        except urllib.error.HTTPError:
            return None
        with self._lock:
            if len(self._users) > 5000:
                self._users.clear()
            self._users[token] = (now + 60, user)
        return user

    def delete_auth_user(self, uid: str):
        self._req("DELETE", f"/auth/v1/admin/users/{uid}")


_client: Supabase | None = None


def client() -> Supabase:
    global _client
    if _client is None:
        _client = Supabase()
    return _client
