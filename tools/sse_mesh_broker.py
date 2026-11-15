#!/usr/bin/env python3
"""SSE one-time Ubuntu mesh enrollment broker and scoped Tailscale OAuth client.

Run only on a dedicated protected enrollment server behind HTTPS. Tokens
authorize overlay networking, NOT blockchain wallet access or SLA truth.
The OAuth client secret never leaves the server. No requests are made at import.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

NODE_RE = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
ROLES = frozenset(("provider", "consumer", "monitor", "observer"))
TAG = "tag:sse-node"
API = "https://api.tailscale.com/api/v2"


class EnrollmentError(ValueError):
    pass


def role_names(raw: str) -> tuple[str, ...]:
    if type(raw) is not str:
        raise EnrollmentError("invalid role list")
    names = tuple(x.strip() for x in raw.split(","))
    if (not names or len(set(names)) != len(names)
            or any(n not in ROLES for n in names)):
        raise EnrollmentError("invalid/duplicate role names")
    return names


def init_db(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS enrollment (
      digest TEXT PRIMARY KEY, node_id TEXT NOT NULL,
      roles TEXT NOT NULL, expires INTEGER NOT NULL,
      used INTEGER NOT NULL DEFAULT 0
    )""")


def issue_token(connection, node_id: str, roles: str,
                now: int | None = None, ttl_seconds: int = 600) -> str:
    if type(node_id) is not str or not NODE_RE.fullmatch(node_id):
        raise EnrollmentError("invalid node ID")
    parsed = role_names(roles)
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 3600:
        raise EnrollmentError("token lifetime must be bounded")
    now = int(time.time()) if now is None else now
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    init_db(connection)
    with connection:
        connection.execute("INSERT INTO enrollment(digest,node_id,roles,expires,used) VALUES (?,?,?,?,0)",
                           (digest, node_id, ",".join(parsed), now + ttl_seconds))
    return token


def redeem_token(connection, node_id: str, roles: str, token: str,
                 now: int | None = None) -> None:
    """Atomically burn a one-time token. Fail closed on all mismatches.

    Broker only calls Tailscale after redemption; transient upstream failure
    requires a new token from the owner, not replay of the original credential.
    """
    if (type(node_id) is not str or not NODE_RE.fullmatch(node_id)
            or type(token) is not str or len(token) > 256):
        raise EnrollmentError("invalid enrollment authorization")
    parsed = role_names(roles)
    now = int(time.time()) if now is None else now
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    init_db(connection)
    connection.execute("BEGIN IMMEDIATE")
    try:
        record = connection.execute(
            "SELECT node_id,roles,expires,used FROM enrollment WHERE digest=?",
            (digest,)).fetchone()
        if (record is None or record[0] != node_id or record[1] != ",".join(parsed)
                or record[2] <= now or record[3] != 0):
            raise EnrollmentError("invalid or expired enrollment authorization")
        cursor = connection.execute(
            "UPDATE enrollment SET used=1 WHERE digest=? AND used=0", (digest,))
        if cursor.rowcount != 1:
            raise EnrollmentError("credential was consumed")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EnrollmentError("upstream redirect forbidden")


def _post(url: str, body: bytes, headers: dict) -> dict:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            if response.status != 200:
                raise EnrollmentError("unexpected provisioning response")
            raw = response.read(65537)
    except (OSError, TimeoutError) as exc:
        # Never include exception strings or HTTP response bodies in API errors:
        # they may contain credentials.
        raise EnrollmentError("upstream provisioning unavailable") from None
    if len(raw) > 65536:
        raise EnrollmentError("provisioning response too large")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise EnrollmentError("invalid provisioning response") from None
    if type(data) is not dict:
        raise EnrollmentError("invalid provisioning response")
    return data


def mint_tailscale_auth_key(client_id: str, client_secret: str,
                            tailnet: str = "-", tag: str = TAG,
                            post=_post) -> str:
    """Mint one-off non-ephemeral tagged key, 300s validity. No persistent OAuth token."""
    if (not client_id or not client_secret or not tailnet
            or "/" in tailnet or tag != TAG):
        raise EnrollmentError("broker OAuth config invalid")
    basic = base64.b64encode((client_id + ":" + client_secret).encode()).decode("ascii")
    auth = post(API + "/oauth/token",
                urlencode({"grant_type": "client_credentials", "scope": "auth_keys"}).encode(),
                {"Authorization": "Basic " + basic,
                 "Content-Type": "application/x-www-form-urlencoded"})
    access_token = auth.get("access_token")
    if type(access_token) is not str or not access_token:
        raise EnrollmentError("broker OAuth grant unavailable")
    data = {
        "capabilities": {"devices": {"create": {
            "reusable": False, "ephemeral": False, "preauthorized": True,
            "tags": [tag]}}},
        "expirySeconds": 300,
        "description": "SSE short-lived Ubuntu VM enrollment",
    }
    response = post(API + "/tailnet/" + quote(tailnet, safe="") + "/keys",
                    json.dumps(data, separators=(",", ":")).encode("utf-8"),
                    {"Authorization": "Bearer " + access_token,
                     "Content-Type": "application/json"})
    key = response.get("key")
    if type(key) is not str or not key.startswith("tskey-auth-"):
        raise EnrollmentError("upstream returned no node auth key")
    return key


def issue_cli(argv=None):
    p = argparse.ArgumentParser(description="Owner-only enrollment token issuing (prints token ONCE)")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--node-id", required=True)
    p.add_argument("--roles", required=True)
    args = p.parse_args(argv)
    if not args.db.parent.is_dir():
        p.error("database directory must already exist and be secured")
    if args.db.is_symlink():
        p.error("symlink database forbidden")
    with sqlite3.connect(args.db, timeout=8, isolation_level=None) as conn:
        credential = issue_token(conn, args.node_id, args.roles)
    os.chmod(args.db, 0o600)
    print(credential)
    return 0


if __name__ == "__main__":
    raise SystemExit(issue_cli())
