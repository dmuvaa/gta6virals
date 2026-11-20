"""Where previews and finished clips live.

* Cloudflare R2 / any S3-compatible storage (production): set S3_ENDPOINT (or R2_ACCOUNT_ID),
  R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET (or put the bucket at the end of
  S3_ENDPOINT). Files are served straight from storage with short-lived presigned URLs.
* Local disk (development): used when R2 isn't configured. Files are served by the API at
  /files/<key> with an HMAC-signed, expiring link.

Either way the browser only ever gets time-limited links, never a guessable path."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import shutil
import time
import urllib.parse

DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work")
LOCAL_ROOT = os.path.join(DATA_DIR, "files")
API_URL = os.environ.get("API_URL", "http://localhost:8765").rstrip("/")


def _secret() -> bytes:
    s = os.environ.get("FILES_SIGNING_KEY") or os.environ.get("SUPABASE_SECRET_KEY", "dev-only")
    return hashlib.sha256(("files:" + s).encode()).digest()


def _endpoint_and_bucket() -> tuple[str | None, str | None]:
    """S3_ENDPOINT may be pasted straight from Cloudflare, bucket included
    (https://<account>[.eu|.us].r2.cloudflarestorage.com/<bucket>). Split it into
    the endpoint and, if R2_BUCKET isn't set, the bucket name."""
    raw = os.environ.get("S3_ENDPOINT", "").strip().strip("'\"")
    bucket = os.environ.get("R2_BUCKET", "").strip() or None
    if raw:
        m = re.match(r"^(https?://[^/]+)/*([^/?#]*)", raw)
        if m:
            return m.group(1), bucket or (m.group(2) or None)
    acct = os.environ.get("R2_ACCOUNT_ID", "").strip()
    return (f"https://{acct}.r2.cloudflarestorage.com" if acct else None), bucket


def bucket() -> str:
    return _endpoint_and_bucket()[1] or ""


def r2_enabled() -> bool:
    """True when S3-compatible storage (Cloudflare R2, Backblaze B2, …) is configured."""
    endpoint, b = _endpoint_and_bucket()
    return bool(endpoint and b and os.environ.get("R2_ACCESS_KEY_ID") and os.environ.get("R2_SECRET_ACCESS_KEY"))


_s3 = None


def _r2():
    global _s3
    if _s3 is None:
        import boto3
        from botocore.config import Config
        _s3 = boto3.client(
            "s3", region_name="auto",
            endpoint_url=_endpoint_and_bucket()[0],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4", retries={"max_attempts": 4}))
    return _s3


def _ctype(key: str) -> str:
    return {"mp4": "video/mp4", "jpg": "image/jpeg", "png": "image/png", "zip": "application/zip"}.get(
        key.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def put(local_path: str, key: str) -> str:
    """Store a file under `key` (e.g. "<project>/clips/m3_….mp4"). Returns the key."""
    if r2_enabled():
        _r2().upload_file(local_path, bucket(), key,
                          ExtraArgs={"ContentType": _ctype(key), "CacheControl": "private, max-age=3600"})
    else:
        dest = os.path.join(LOCAL_ROOT, key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.abspath(local_path) != os.path.abspath(dest):
            shutil.copyfile(local_path, dest)
    return key


def delete(key: str | None):
    if not key:
        return
    try:
        if r2_enabled():
            _r2().delete_object(Bucket=bucket(), Key=key)
        else:
            os.remove(os.path.join(LOCAL_ROOT, key))
    except Exception:
        pass


def delete_prefix(prefix: str):
    """Delete everything for a project (prefix = "<project id>/")."""
    if r2_enabled():
        s3, bucket = _r2(), bucket()
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})
    else:
        shutil.rmtree(os.path.join(LOCAL_ROOT, prefix.rstrip("/")), ignore_errors=True)


def url(key: str | None, download_name: str | None = None, expires: int = 3600) -> str | None:
    """A time-limited link the browser can use to play or download the file."""
    if not key:
        return None
    if r2_enabled():
        params = {"Bucket": bucket(), "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        return _r2().generate_presigned_url("get_object", Params=params, ExpiresIn=expires)
    exp = int(time.time()) + expires
    q = {"exp": exp, "sig": sign(key, exp)}
    if download_name:
        q["dl"] = download_name
    return f"{API_URL}/files/{urllib.parse.quote(key)}?{urllib.parse.urlencode(q)}"


def sign(key: str, exp: int) -> str:
    return hmac.new(_secret(), f"{key}|{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def verify(key: str, exp: str, sig: str) -> bool:
    try:
        if int(exp) < time.time():
            return False
    except ValueError:
        return False
    return hmac.compare_digest(sign(key, int(exp)), sig or "")


def local_path(key: str) -> str | None:
    """Filesystem path for a locally stored key (dev mode), refusing path tricks."""
    root = os.path.abspath(LOCAL_ROOT)
    p = os.path.abspath(os.path.join(root, key))
    return p if p.startswith(root + os.sep) and os.path.isfile(p) else None
