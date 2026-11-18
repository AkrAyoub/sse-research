#!/usr/bin/env python3
"""WAN-capable, one-time SSE enrollment API. Bind loopback behind a reviewed HTTPS reverse proxy.

This is NOT a public, anonymous RPC, validator admission, or Ethereum signer.
An operator preauthorizes each node ID and role using sse_mesh_broker.py.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import io
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from sse_mesh_broker import EnrollmentError, mint_tailscale_auth_key, redeem_token, role_names

MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 4096


class BrokerHTTPError(ValueError):
    pass


def validate_file(path: Path, *, max_bytes: int) -> Path:
    """Fail closed on missing/misowned/symlinked sensitive files."""
    if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
            or not path.is_file()):
        raise BrokerHTTPError("secure regular file required")
    st = path.stat()
    parent = path.parent.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o600
            or parent.st_uid != os.geteuid()
            or parent.st_mode & 0o022
            or not 0 < st.st_size <= max_bytes):
        raise BrokerHTTPError("private file owner, mode, directory or size invalid")
    return path


def private_file(path: Path, *, max_bytes: int) -> str:
    value = validate_file(path, max_bytes=max_bytes).read_text(encoding="utf-8").strip()
    if not value:
        raise BrokerHTTPError("private file empty")
    return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BrokerHTTPError("duplicate JSON fields")
        result[key] = value
    return result


def _result(start_response, code: str, data: dict):
    body = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    start_response(code, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("Pragma", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
    ])
    return [body]


class EnrollmentApp:
    """One-shot credential redemption. All failures expose generic messages."""

    def __init__(self, database: Path, client_id: str, client_secret: str,
                 tailnet: str = "-", mint=mint_tailscale_auth_key):
        self.database = Path(database)
        self.client_id = client_id
        self.client_secret = client_secret
        self.tailnet = tailnet
        self.mint = mint

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "")
        if path == "/healthz" and method == "GET":
            return _result(start_response, "200 OK", {
                "status": "ready", "ethereumTransactionsSent": False})
        if path != "/v1/mesh/enroll":
            return _result(start_response, "404 Not Found", {"error": "not found"})
        if method != "POST":
            return _result(start_response, "405 Method Not Allowed", {"error": "method not allowed"})
        if environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower() != "application/json":
            return _result(start_response, "415 Unsupported Media Type", {"error": "JSON required"})
        try:
            raw_length = environ.get("CONTENT_LENGTH", "")
            if not raw_length.isdecimal():
                raise BrokerHTTPError("content length required")
            length = int(raw_length)
            if not 1 <= length <= MAX_REQUEST_BYTES:
                raise BrokerHTTPError("invalid body size")
            stream = environ.get("wsgi.input")
            if stream is None:
                raise BrokerHTTPError("missing body")
            raw = stream.read(length)
            if len(raw) != length:
                raise BrokerHTTPError("incomplete body")
            doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
            if type(doc) is not dict or set(doc) != {
                "node_id", "roles", "enrollment_token"}:
                raise BrokerHTTPError("unrecognized payload")
            node = doc["node_id"]
            roles = doc["roles"]
            token = doc["enrollment_token"]
            if (type(node) is not str or type(roles) is not str
                    or type(token) is not str):
                raise BrokerHTTPError("invalid payload types")
            names = role_names(roles)
            if ",".join(names) != roles:
                raise BrokerHTTPError("noncanonical roles")
            # Atomic token burn comes *before* upstream key creation.
            # On a failed/uncertain upstream call, the owner must issue a NEW token.
            with closing(sqlite3.connect(self.database, timeout=8, isolation_level=None)) as db:
                redeem_token(db, node, roles, token)
            key = self.mint(self.client_id, self.client_secret, tailnet=self.tailnet)
            if type(key) is not str or not key.startswith("tskey-auth-") or len(key) > 2048:
                raise BrokerHTTPError("invalid provisioned key")
            response = {
                "nodeId": node,
                "rolesConfigured": list(names),
                "tailnetAuthKey": key,
                "expiresInSeconds": 300,
            }
            if len(json.dumps(response).encode()) > MAX_RESPONSE_BYTES:
                raise BrokerHTTPError("oversized credential")
            return _result(start_response, "200 OK", response)
        except (BrokerHTTPError, EnrollmentError, ValueError, TypeError,
                UnicodeError, sqlite3.Error, OSError):
            # Never echo the token, keys, OAuth credentials or upstream response.
            return _result(start_response, "403 Forbidden", {"error": "enrollment denied"})


class QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Public request data MUST NOT enter HTTP access logs.
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="SSE private one-time mesh enrollment endpoint")
    ap.add_argument("--database", type=Path, required=True)
    ap.add_argument("--client-id-file", type=Path, required=True)
    ap.add_argument("--client-secret-file", type=Path, required=True)
    ap.add_argument("--tailnet", default="-")
    ap.add_argument("--port", type=int, default=18781)
    ns = ap.parse_args(argv)
    try:
        if not 1024 <= ns.port <= 65535:
            raise BrokerHTTPError("port out of range")
        # Read the file, then use its proven metadata; the database is never sent.
        validate_file(ns.database, max_bytes=20_000_000)
        client_id = private_file(ns.client_id_file, max_bytes=512)
        client_secret = private_file(ns.client_secret_file, max_bytes=4096)
        if "/" in ns.tailnet or not ns.tailnet:
            raise BrokerHTTPError("invalid tailnet")
        with make_server(
            "127.0.0.1", ns.port,
            EnrollmentApp(ns.database, client_id, client_secret, ns.tailnet),
            handler_class=QuietRequestHandler,
        ) as server:
            print("SSE_BROKER_LOOPBACK_ONLY 127.0.0.1:" + str(ns.port), flush=True)
            server.serve_forever()
        return 0
    except (BrokerHTTPError, OSError, ValueError) as exc:
        print("SSE_BROKER_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
