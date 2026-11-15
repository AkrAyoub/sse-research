#!/usr/bin/env python3
"""SSE Ubuntu one-command mesh enrollment client (broker -> one-time key -> overlay).

Explicit --apply requires Ubuntu root and a previously provisioned one-time
enrollment credential. All network calls are outbound HTTPS; no static public
IP or manual Tailscale browser login is required. No Ethereum key handling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sse_vm_overlay import MeshJoinError, _check_auth_file, _require_ubuntu_root, apply as mesh_apply, validate


class EnrollmentClientError(ValueError):
    pass


def safe_broker_url(url: str) -> str:
    if type(url) is not str:
        raise EnrollmentClientError("broker URL invalid")
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username or u.password or
            u.query or u.fragment or u.path not in ("", "/") or
            any(x.isspace() for x in url)):
        raise EnrollmentClientError("broker requires HTTPS origin with no credentials or query")
    try:
        port = u.port
    except ValueError:
        raise EnrollmentClientError("broker port invalid") from None
    if port is not None and not 1 <= port <= 65535:
        raise EnrollmentClientError("broker port invalid")
    return url.rstrip("/")


def dry_run(node_id: str, roles: str, broker_url: str, token_file: str) -> dict:
    endpoint = safe_broker_url(broker_url)
    if type(token_file) is not str or token_file != "/run/sse/enrollment.token":
        raise EnrollmentClientError("enrollment token must use /run/sse/enrollment.token")
    mesh = validate(node_id, roles, "/run/sse/one-time.key")
    return {
        "kind": "SSE_UBUNTU_BROKER_MESH_ENROLLMENT_PLAN",
        "mode": "DRY_RUN",
        "nodeId": node_id,
        "rolesConfigured": mesh["rolesConfigured"],
        "brokerOrigin": endpoint,
        "requiresExistingTailscale": True,
        "credentialFile": token_file,
        "ethereumTransactionsSent": False,
        "writesOrTransactionsSent": False,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EnrollmentClientError("broker redirect forbidden")


def request_key(origin: str, node_id: str, roles: str, credential: str) -> str:
    body = json.dumps({"node_id": node_id, "roles": roles,
                       "enrollment_token": credential}, separators=(",", ":")).encode()
    req = Request(origin + "/v1/mesh/enroll", data=body, method="POST",
                  headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=10) as response:
            if response.status != 200:
                raise EnrollmentClientError("broker rejected enrollment")
            raw = response.read(16385)
    except (OSError, TimeoutError) as exc:
        raise EnrollmentClientError("broker enrollment failed; obtain a new token if consumed") from None
    if len(raw) > 16384:
        raise EnrollmentClientError("broker response too large")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise EnrollmentClientError("malformed broker response") from None
    if (type(data) is not dict or data.get("nodeId") != node_id or
            data.get("rolesConfigured") != roles.split(",") or
            type(data.get("tailnetAuthKey")) is not str or
            not data["tailnetAuthKey"].startswith("tskey-auth-") or
            data.get("expiresInSeconds") != 300):
        raise EnrollmentClientError("broker identity/scope mismatch")
    return data["tailnetAuthKey"]


def enroll(plan: dict, fetch=request_key, join=mesh_apply) -> dict:
    if plan.get("kind") != "SSE_UBUNTU_BROKER_MESH_ENROLLMENT_PLAN":
        raise EnrollmentClientError("unknown enrollment plan")
    _require_ubuntu_root()
    token_path = Path(plan["credentialFile"])
    _check_auth_file(token_path)
    # Restrict /run/sse directory to root, fail closed if previous attempt left a key.
    private_dir = Path("/run/sse")
    if private_dir.is_symlink():
        raise EnrollmentClientError("unsafe credential directory")
    key_path = private_dir / "one-time.key"
    if key_path.exists() or key_path.is_symlink():
        raise EnrollmentClientError("stale one-time auth key file; investigate before retry")
    raw_token = token_path.read_text(encoding="ascii").strip()
    if not 30 <= len(raw_token) <= 256:
        raise EnrollmentClientError("invalid enrollment token")
    key = fetch(plan["brokerOrigin"], plan["nodeId"],
                ",".join(plan["rolesConfigured"]), raw_token)
    if not key.startswith("tskey-auth-") or len(key) > 4096:
        raise EnrollmentClientError("unexpected broker key")
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(key + "\n")
        mesh = validate(plan["nodeId"], ",".join(plan["rolesConfigured"]), str(key_path))
        result = join(mesh)
    finally:
        # Even an unsuccessful join must not leave a usable auth key behind.
        key_path.unlink(missing_ok=True)
    token_path.unlink(missing_ok=True)
    return {"kind": plan["kind"], "result": "SSE_OVERLAY_ENROLLED",
            "nodeId": plan["nodeId"], "overlay": result,
            "ethereumRoleActivated": False, "ethereumTransactionsSent": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Ubuntu SSE broker mesh enrollment")
    p.add_argument("--node-id", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--broker-url", required=True)
    p.add_argument("--token-file", default="/run/sse/enrollment.token")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    try:
        plan = dry_run(args.node_id, args.roles, args.broker_url, args.token_file)
        print(json.dumps(enroll(plan) if args.apply else plan, indent=2, sort_keys=True))
        return 0
    except (EnrollmentClientError, MeshJoinError, OSError, ValueError) as exc:
        print("SSE_MESH_ENROLL_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
