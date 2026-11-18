#!/usr/bin/env python3
"""VM-local R9 validator readiness and one-time identity bootstrap.

This script NEVER joins Tailscale for you, changes sudo rules, launches Docker,
writes Ethereum wallets, accesses chain31337, or grants validator voting rights.
'doctor' is read-only. 'init-identity --apply' is the sole state-changing action:
it makes a new private key and public record on this very Ubuntu machine,
after an operator has approved its Tailscale membership. If identity already
exists, it refuses regeneration; inspect is read-only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from sse_qbft_validator_identity import (
    IdentityError, init_local, inspect_local
)

REVISION = re.compile(r"[0-9a-f]{40}\Z")
NODE_IDS = frozenset(f"validator-{n}" for n in range(1, 5))
MAX_STDOUT = 65536
SOURCE_ROOT = Path(__file__).resolve().parents[1]


class HostSetupError(ValueError):
    pass


def run_readonly(argv, *, timeout=10):
    if type(argv) is not list or not argv:
        raise HostSetupError("invalid inspection command")
    # No shell, no sudo, no mutable network operations.
    allowed = {
        ("git", "rev-parse", "HEAD"),
        ("git", "status", "--porcelain", "--untracked-files=no"),
        ("tailscale", "status", "--json"),
        ("docker", "info", "--format", "{{.ServerVersion}}"),
        ("docker", "compose", "version", "--short"),
    }
    if tuple(argv) not in allowed:
        raise HostSetupError("inspection operation not permitted")
    try:
        completed = subprocess.run(
            argv, cwd=SOURCE_ROOT, capture_output=True, text=True,
            timeout=timeout, check=True)
    except (OSError, subprocess.SubprocessError):
        raise HostSetupError("inspection command unavailable: " + argv[0]) from None
    if len(completed.stdout) > MAX_STDOUT:
        raise HostSetupError("oversized local diagnostics")
    return completed.stdout.strip()


def parse_tailnet(raw):
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError):
        return {"state": "invalid", "online": False, "ip": None, "stableId": None}
    if type(obj) is not dict:
        return {"state": "invalid", "online": False, "ip": None, "stableId": None}
    state = obj.get("BackendState", "Unknown")
    node = obj.get("Self")
    if (state != "Running" or type(node) is not dict
            or node.get("Online") is not True):
        return {"state": str(state)[:48], "online": False,
                "ip": None, "stableId": None}
    import ipaddress
    values = node.get("TailscaleIPs", [])
    if type(values) is not list:
        values = []
    ips = []
    for value in values:
        try:
            address = ipaddress.IPv4Address(value)
            if address in ipaddress.IPv4Network("100.64.0.0/10"):
                ips.append(str(address))
        except (ValueError, ipaddress.AddressValueError):
            pass
    stable_id = node.get("StableID") or node.get("ID")
    if (len(ips) != 1 or type(stable_id) is not str
            or not 2 <= len(stable_id) <= 128):
        return {"state": "invalid-device-identity", "online": False,
                "ip": None, "stableId": None}
    return {"state": "Running", "online": True, "ip": ips[0],
            "stableId": stable_id}


def base_check(*, expected_commit, observed_commit, status, linux,
               tracked_dirty, tailscale_installed=True, docker_installed=True,
               docker_access=False):
    if (type(expected_commit) is not str or
            not REVISION.fullmatch(expected_commit)):
        raise HostSetupError("requires exact approved 40-character revision")
    if type(observed_commit) is not str or observed_commit != expected_commit:
        raise HostSetupError("local checkout does not match approved Git SHA")
    if tracked_dirty:
        raise HostSetupError("tracked source is modified; preserve it before any update")
    if not linux:
        raise HostSetupError("R9 validators require native Ubuntu Linux, not Windows/WSL")
    tail = parse_tailnet(status)
    blockers = []
    if not tailscale_installed:
        blockers.append("INSTALL_TAILSCALE_FROM_APPROVED_PACKAGE")
    elif not tail["online"]:
        blockers.append("AUTHORIZE_TAILSCALE_TAILNET_INTERACTIVELY_OR_WITH_ONE_TIME_BROKER")
    if not docker_installed:
        blockers.append("INSTALL_DOCKER_AND_COMPOSE_FROM_APPROVED_PACKAGE")
    elif not docker_access:
        blockers.append("DOCKER_SOCKET_REQUIRES_REVIEWED_OPERATOR_ACCESS")
    return {
        "kind": "SSE_R9_HOST_SETUP_DOCTOR_V1",
        "sourceGitSha": observed_commit,
        "tailnet": tail,
        "dockerCliAvailable": docker_installed,
        "dockerSocketAccessibleToThisUser": docker_access,
        "blockers": blockers,
        "readyForValidatorIdentity": bool(tail["online"]),
        "readyForContainerCanary": not blockers,
        "permissionlessNetworkAdmission": False,
        "ethereumTransactionsSent": False,
        "dockerContainersStarted": False,
    }


def local_ubuntu():
    if platform.system() != "Linux" or "microsoft" in platform.release().lower():
        return False
    try:
        return any(x in ("ID=ubuntu", 'ID="ubuntu"')
                   for x in Path("/etc/os-release").read_text("utf-8").splitlines())
    except OSError:
        return False


def doctor(expected_commit, *, read=run_readonly):
    commit = read(["git", "rev-parse", "HEAD"])
    dirty = read(["git", "status", "--porcelain", "--untracked-files=no"])
    if shutil.which("tailscale"):
        try:
            tail = read(["tailscale", "status", "--json"])
        except HostSetupError:
            tail = '{"BackendState":"NeedsLogin"}'
    else:
        tail = '{"BackendState":"NotInstalled"}'
    docker_exists = bool(shutil.which("docker"))
    docker_access = False
    if docker_exists:
        try:
            read(["docker", "info", "--format", "{{.ServerVersion}}"])
            read(["docker", "compose", "version", "--short"])
            docker_access = True
        except HostSetupError:
            pass
    return base_check(
        expected_commit=expected_commit, observed_commit=commit,
        tracked_dirty=dirty, status=tail, linux=local_ubuntu(),
        tailscale_installed=bool(shutil.which("tailscale")),
        docker_installed=docker_exists, docker_access=docker_access,
    )


def prepare_identity(*, node_id, private_dir, public_file,
                     approved_revision, read=run_readonly, apply=False):
    if node_id not in NODE_IDS:
        raise HostSetupError("initial R9 genesis permits validator-1 through validator-4")
    if os.name != "posix" or not local_ubuntu() or os.geteuid() == 0:
        raise HostSetupError("run as NONROOT Ubuntu checkout owner")
    source = read(["git", "rev-parse", "HEAD"])
    dirty = read(["git", "status", "--porcelain", "--untracked-files=no"])
    if source != approved_revision or not REVISION.fullmatch(source) or dirty:
        raise HostSetupError("validator identity requires exact clean approved source")
    if not private_dir.is_absolute() or private_dir.is_symlink():
        raise HostSetupError("private dir must be absolute non-symlink path")
    if public_file != private_dir / (node_id + ".public.json"):
        raise HostSetupError("public record path must be inside private directory")
    status = parse_tailnet(read(["tailscale", "status", "--json"]))
    if not status["online"]:
        raise HostSetupError("authorize Tailscale device before creating Besu key")
    if not apply:
        return {
            "kind": "SSE_R9_IDENTITY_PLAN_V1", "mode": "DRY_RUN",
            "nodeId": node_id, "overlayIPv4": status["ip"],
            "privateDirectory": str(private_dir),
            "privateKeyWillBeCreated": False,
            "walletTransactionsSent": False,
        }
    if not private_dir.exists():
        private_dir.mkdir(mode=0o700, parents=False)
    if (private_dir / "node.key").exists() or public_file.exists():
        raise HostSetupError("identity already exists; use inspect, never regenerate")
    try:
        record = init_local(private_dir, public_file=public_file,
                            node_id=node_id, overlay_ipv4=status["ip"])
    except (IdentityError, OSError) as exc:
        raise HostSetupError("local identity initialization refused: " + str(exc)) from None
    return {
        "kind": "SSE_R9_IDENTITY_CREATED_ON_THIS_HOST",
        "sourceGitSha": source, "nodeId": node_id,
        "publicRecord": record, "privateKeyPath": str(private_dir / "node.key"),
        "privateKeyMaterialPrinted": False, "networkStarted": False,
        "ethereumTransactionsSent": False,
    }


def inspect_identity(*, private_dir, public_file):
    if os.name != "posix" or not local_ubuntu():
        raise HostSetupError("inspect on original Ubuntu key-owning host")
    rec = inspect_local(private_dir, public_file=public_file)
    state = parse_tailnet(run_readonly(["tailscale", "status", "--json"]))
    if not state["online"] or state["ip"] != rec["overlayIPv4"]:
        raise HostSetupError(
            "Tailscale IP changed: don't regenerate key; renew signed peer locator via reviewed recovery")
    return {
        "kind": "SSE_R9_IDENTITY_VERIFIED", "nodeId": rec["nodeId"],
        "validatorPublic": rec, "tailscaleStableId": state["stableId"],
        "privateKeyMaterialPrinted": False,
        "ethereumTransactionsSent": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(
        description="R9 new Ubuntu validator host doctor and safe local identity ceremony")
    sp = p.add_subparsers(dest="action", required=True)
    d = sp.add_parser("doctor")
    d.add_argument("--expected-commit", required=True)
    i = sp.add_parser("init-identity")
    i.add_argument("--expected-commit", required=True)
    i.add_argument("--node-id", required=True)
    i.add_argument("--private-dir", type=Path, required=True)
    i.add_argument("--apply", action="store_true")
    v = sp.add_parser("inspect-identity")
    v.add_argument("--node-id", required=True)
    v.add_argument("--private-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.action == "doctor":
            result = doctor(a.expected_commit)
        elif a.action == "init-identity":
            result = prepare_identity(
                node_id=a.node_id, private_dir=a.private_dir,
                public_file=a.private_dir / (a.node_id + ".public.json"),
                approved_revision=a.expected_commit, apply=a.apply)
        else:
            result = inspect_identity(
                private_dir=a.private_dir,
                public_file=a.private_dir / (a.node_id + ".public.json"))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (HostSetupError, IdentityError, OSError, ValueError, KeyError) as exc:
        print("SSE_R9_HOST_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
