#!/usr/bin/env python3
"""Ubuntu SSE overlay enrollment, safely noninteractive when explicitly applied.

A trusted provisioning broker must place a short-lived Tailscale auth key in a
root-only file. No reusable OAuth client secret or node wallet secret is stored
in this module. Dry-run is side-effect free on every host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

NODE = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
ROLE = frozenset({"provider", "consumer", "monitor", "observer"})
TAG = re.compile(r"tag:sse-[a-z0-9-]{1,50}\Z")


class MeshJoinError(ValueError):
    pass


def validate(node_id: str, roles: str, auth_key_file: str,
             tag: str = "tag:sse-node") -> dict:
    if type(node_id) is not str or not NODE.fullmatch(node_id):
        raise MeshJoinError("invalid SSE node ID")
    if type(roles) is not str:
        raise MeshJoinError("roles must be comma-separated")
    selected = tuple(part.strip() for part in roles.split(","))
    if not selected or len(set(selected)) != len(selected) or any(r not in ROLE for r in selected):
        raise MeshJoinError("invalid or duplicate SSE roles")
    if type(tag) is not str or not TAG.fullmatch(tag):
        raise MeshJoinError("invalid overlay ACL tag")
    if type(auth_key_file) is not str:
        raise MeshJoinError("invalid auth key file")
    # Validate the intended *Ubuntu* path as a literal POSIX string, even
    # when reviewing a dry-run from Windows. Never reinterpret it using the
    # local host's pathlib.Path conventions.
    if re.fullmatch(r"/(?:run|etc)/sse/[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}", auth_key_file) is None:
        raise MeshJoinError("auth key file must reside under /run/sse or /etc/sse")
    return {
        "kind": "SSE_UBUNTU_OVERLAY_ENROLLMENT",
        "mode": "DRY_RUN",
        "nodeId": node_id,
        "rolesConfigured": list(selected),
        "aclTag": tag,
        "authFilePath": auth_key_file,
        "requiresRoot": True,
        "requiresInstalledTailscale": True,
        "tailnetJoined": False,
        "ethereumRoleActivated": False,
        "writesOrTransactionsSent": False,
    }


def _require_ubuntu_root() -> None:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise MeshJoinError("overlay --apply requires root on Ubuntu")
    info = Path("/etc/os-release")
    if not info.is_file() or "ID=ubuntu" not in info.read_text().splitlines():
        raise MeshJoinError("overlay --apply requires Ubuntu")


def _check_auth_file(path: Path) -> None:
    # Neither the file nor any ancestor below /etc or /run may be a symlink.
    base = Path("/run") if path.parts[1] == "run" else Path("/etc")
    cursor = path
    while cursor != base:
        if cursor.is_symlink():
            raise MeshJoinError("symlink in enrollment credential path")
        cursor = cursor.parent
    try:
        st = path.stat()
        parent = path.parent.stat()
    except OSError as exc:
        raise MeshJoinError("missing unreadable enrollment credential file") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o600:
        raise MeshJoinError("enrollment credential must be root-owned regular file mode 0600")
    if parent.st_uid != 0 or (parent.st_mode & 0o022):
        raise MeshJoinError("credential directory must be root-owned and not group/world writable")
    if not 0 < st.st_size <= 4096:
        raise MeshJoinError("credential file must be nonempty and bounded")


def _command(args: list[str]) -> str:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, check=True, timeout=45)
    except (OSError, subprocess.SubprocessError) as exc:
        # Never print CLI stdout/stderr: auth key contents could occur there.
        raise MeshJoinError("overlay command failed; inspect secure local service diagnostics") from exc
    return proc.stdout


def apply(plan: dict, command=_command) -> dict:
    if plan.get("kind") != "SSE_UBUNTU_OVERLAY_ENROLLMENT":
        raise MeshJoinError("unrecognized enrollment plan")
    _require_ubuntu_root()
    credential = Path(plan["authFilePath"])
    _check_auth_file(credential)
    if shutil.which("tailscale") is None:
        raise MeshJoinError("tailscale client not installed; install from approved Ubuntu package source")
    # file: prevents leaking the key in argv or shell history. No '--reset'.
    command(["tailscale", "up", "--auth-key=file:" + str(credential),
             "--hostname=" + plan["nodeId"], "--advertise-tags=" + plan["aclTag"],
             "--accept-routes=false", "--accept-dns=true"])
    try:
        status = json.loads(command(["tailscale", "status", "--json"]))
    except (ValueError, json.JSONDecodeError) as exc:
        raise MeshJoinError("invalid overlay status response") from exc
    local = status.get("Self") if type(status) is dict else None
    ips = local.get("TailscaleIPs") if type(local) is dict else None
    if (type(status) is not dict or type(local) is not dict
            or status.get("BackendState") != "Running" or local.get("Online") is not True
            or type(ips) is not list or not ips
            or not all(type(ip) is str and ip for ip in ips)):
        raise MeshJoinError("overlay did not reach online state")
    # One-time key material is not required after successful auth.
    credential.unlink()
    return {
        "kind": plan["kind"],
        "result": "OVERLAY_ONLINE",
        "nodeId": plan["nodeId"],
        "rolesConfigured": plan["rolesConfigured"],
        "overlayAddresses": ips,
        "peerDiscoveryName": local.get("DNSName"),
        "authKeyErased": True,
        "ethereumRoleActivated": False,
        "ethereumTransactionsSent": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SSE Ubuntu overlay enrollment (dry-run by default)")
    p.add_argument("--node-id", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--auth-key-file", required=True,
                   help="root-owned single-use key file under /run/sse or /etc/sse")
    p.add_argument("--tag", default="tag:sse-node")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    try:
        plan = validate(args.node_id, args.roles, args.auth_key_file, args.tag)
        print(json.dumps(apply(plan) if args.apply else plan, indent=2, sort_keys=True))
        return 0
    except (MeshJoinError, OSError, KeyError, ValueError) as exc:
        print("SSE_OVERLAY_ENROLLMENT_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
