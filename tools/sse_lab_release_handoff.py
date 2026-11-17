#!/usr/bin/env python3
"""Send an approved, shallow SSE Git checkout to a NEW Ubuntu VM over pinned SSH.

Lab bootstrap only. No GitHub access is needed on the receiving VM. The operator
must independently approve the source commit, SSH host key and SSH credentials.
Never transmits wallet secrets, never installs a signer, and never sends ETH.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile

SHA = re.compile(r"[0-9a-f]{40}\Z")
NAME = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z")
ROLES = frozenset(("consumer", "provider", "monitor", "observer"))
MAX_BYTES = 80 * 1024 * 1024


class RelayError(ValueError):
    """Unsafe bootstrap input or release package."""


# Self-contained receiver: the destination needs only Python, git, and
# python3-venv; it does not need any SSE source or an SSH/GitHub deploy key.
RECEIVER_SCRIPT = r"""
import hashlib, io, json, os, pathlib, re, subprocess, sys, tarfile, tempfile

def receive_release(payload, expected_digest, revision, home, install=True):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("invalid expected release digest")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("invalid immutable source revision")
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise ValueError("release digest mismatch")
    home = pathlib.Path(home)
    target = home / "sse-research"
    if target.exists() or target.is_symlink():
        raise ValueError("existing SSE checkout; refusing overwrite")
    with tempfile.TemporaryDirectory(prefix=".sse-stage-", dir=home) as work:
        staging = pathlib.Path(work)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > 20000:
                raise ValueError("release contains too many entries")
            for member in members:
                name = pathlib.PurePosixPath(member.name)
                if (name.is_absolute() or not name.parts or
                        name.parts[0] != "sse-research" or
                        any(part in (".", "..") for part in name.parts) or
                        not (member.isfile() or member.isdir())):
                    raise ValueError("unsafe path or file type in release")
                if member.size > 20 * 1024 * 1024:
                    raise ValueError("oversized release member")
            archive.extractall(staging, filter="data")
        repo = staging / "sse-research"
        git_dir = repo / ".git"
        if not git_dir.is_dir() or git_dir.is_symlink():
            raise ValueError("release lacks real Git checkout metadata")
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, text=True, capture_output=True, timeout=10
        ).stdout.strip().lower()
        if head != revision:
            raise ValueError("release Git revision mismatch")
        if subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                          check=True, capture_output=True, timeout=10).stdout.strip():
            raise ValueError("release checkout is dirty")
        repo.rename(target)
    if install:
        # Source installation is complete; dependency errors leave a verified
        # checkout for explicit repair, never silently replace it.
        subprocess.run(["python3", "-m", "venv", str(target / ".venv")],
                       check=True, timeout=90)
        subprocess.run([str(target / ".venv" / "bin" / "python"),
                        "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-input", "-r", str(target / "requirements.txt")],
                       check=True, timeout=200, stdout=subprocess.DEVNULL)
    return {"kind": "SSE_PRIVATE_VM_RELEASE_HANDOFF",
            "revision": revision, "sha256": expected_digest,
            "source": str(target), "pythonEnvironmentInstalled": bool(install),
            "githubCredentialsInstalled": False, "walletKeysInstalled": False,
            "roleActivated": False, "ethereumTransactionsSent": False}

if __name__ == "__main__":
    digest, rev = sys.argv[1:3]
    blob = sys.stdin.buffer.read(80 * 1024 * 1024 + 1)
    if len(blob) > 80 * 1024 * 1024:
        raise ValueError("release archive too large")
    print(json.dumps(receive_release(blob, digest, rev, pathlib.Path.home())))
"""


def _run(command: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, text=True)
    return result.stdout.strip()


def package_release(source: Path, approved_revision: str) -> bytes:
    if type(approved_revision) is not str or not SHA.fullmatch(approved_revision):
        raise RelayError("approved revision must be a full lowercase Git SHA")
    source = source.resolve(strict=True)
    if _run(["git", "-C", str(source), "rev-parse", "HEAD"]).lower() != approved_revision:
        raise RelayError("source checkout HEAD is not the operator-approved revision")
    if _run(["git", "-C", str(source), "status", "--porcelain", "-uno"]):
        raise RelayError("source checkout has local modifications")
    with tempfile.TemporaryDirectory(prefix="sse-relay-") as temp:
        shallow = Path(temp) / "sse-research"
        _run(["git", "clone", "--quiet", "--depth", "1",
              source.as_uri(), str(shallow)], timeout=120)
        if _run(["git", "-C", str(shallow), "rev-parse", "HEAD"]).lower() != approved_revision:
            raise RelayError("shallow clone revision mismatch")
        _run(["git", "-C", str(shallow), "remote", "remove", "origin"])
        # Ensure Git metadata is self-contained; no credential, private key,
        # untracked local files, or original Git history is distributed.
        blob = io.BytesIO()
        with tarfile.open(fileobj=blob, mode="w:gz") as tar:
            tar.add(shallow, arcname="sse-research", recursive=True)
        payload = blob.getvalue()
        if len(payload) > MAX_BYTES:
            raise RelayError("shallow release exceeds archive size limit")
        return payload


def validated_destination(ip: str, user: str, key: Path, roles: str) -> tuple[str, list[str]]:
    address = ipaddress.ip_address(ip)
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise RelayError("destination must have a private VM IP")
    if not NAME.fullmatch(user):
        raise RelayError("invalid remote Linux username")
    selected = roles.split(",")
    if not selected or len(selected) != len(set(selected)) or any(
            role not in ROLES for role in selected):
        raise RelayError("invalid or duplicate application roles")
    key = key.expanduser().resolve(strict=True)
    st = key.stat()
    if not key.is_file() or st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise RelayError("SSH provisioning key must be caller-owned and private")
    return user + "@" + str(address), selected


def transfer(source: Path, revision: str, host: str, user: str,
             key: Path, roles: str, apply: bool) -> dict:
    dest, selected = validated_destination(host, user, key, roles)
    payload = package_release(source, revision)
    digest = hashlib.sha256(payload).hexdigest()
    result = {"kind": "SSE_PRIVATE_VM_RELEASE_HANDOFF_PLAN",
              "destination": dest, "rolesRequested": selected,
              "sourceRevision": revision, "sha256": digest,
              "bundleBytes": len(payload), "mode": "APPLY" if apply else "DRY_RUN",
              "githubCredentialsRequiredOnDestination": False,
              "walletKeysCreated": False, "ethereumTransactionsSent": False}
    if not apply:
        return result

    command = (
        "python3 -c " + shlex.quote(
            "import base64;exec(base64.b64decode(" +
            repr(base64.b64encode(RECEIVER_SCRIPT.encode()).decode("ascii")) + "))") +
        " " + shlex.quote(digest) + " " + shlex.quote(revision)
    )
    ssh_command = [
        "ssh", "-T", "-i", str(key.expanduser().resolve()),
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=10", dest, command,
    ]
    # StrictHostKeyChecking requires the operator to verify and pin the host
    # key in their known_hosts BEFORE running --apply.
    done = subprocess.run(ssh_command, input=payload, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=300)
    if done.returncode:
        raise RelayError("SSH release transfer or remote installation failed; "
                         "inspect receiver locally; no automatic retry or overwrite")
    try:
        received = json.loads(done.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise RelayError("destination did not return a valid handoff receipt") from exc
    if (received.get("sha256") != digest or received.get("revision") != revision
            or received.get("pythonEnvironmentInstalled") is not True):
        raise RelayError("destination release receipt mismatch")
    return {"result": "VERIFIED_PRIVATE_VM_RELEASE_INSTALLED",
            "destination": dest, "rolesRequested": selected,
            "receiver": received, "walletKeysCreated": False,
            "ethereumTransactionsSent": False}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SSH-only verified Git source handoff to fresh Ubuntu VM")
    p.add_argument("--source", type=Path, default=Path("."))
    p.add_argument("--revision", required=True, help="externally approved full 40-character Git SHA")
    p.add_argument("--dest-ip", required=True, help="private IP, no public exposure")
    p.add_argument("--dest-user", required=True, help="actual portal-provisioned username")
    p.add_argument("--ssh-key", required=True, type=Path, help="private operator SSH key")
    p.add_argument("--roles", required=True, help="comma-separated intended roles")
    p.add_argument("--apply", action="store_true", help="explicitly allow remote first install")
    args = p.parse_args(argv)
    try:
        print(json.dumps(transfer(args.source, args.revision, args.dest_ip,
                                  args.dest_user, args.ssh_key,
                                  args.roles, args.apply), indent=2, sort_keys=True))
        return 0
    except (RelayError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print("SSE_PRIVATE_VM_HANDOFF_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
