#!/usr/bin/env python3
"""Index key-free experiment logs before a disposable VM is deleted.

Read-only with respect to source, wallets and the chain; creates one new
evidence hash manifest that an operator must separately review/archive.
Hashes do not preserve the actual logs or node state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

RUN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
FORBIDDEN = re.compile(r"(secret|token|private|keyfile|key\.json|mnemonic|\.env|credential|password|keystore|wallet)", re.I)
MAX_FILE = 15 * 1024 * 1024
MAX_INPUTS = 32
SUFFIXES = frozenset({".log", ".txt", ".csv", ".json"})


class EvidenceError(ValueError):
    pass


def git_sha(root: Path) -> str:
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           check=True, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        raise EvidenceError("cannot verify source Git revision") from None
    sha = p.stdout.strip().lower()
    if not SHA_RE.fullmatch(sha):
        raise EvidenceError("invalid Git revision")
    return sha


def inspect_file(root: Path, relative: str) -> dict:
    candidate = Path(relative)
    if (candidate.is_absolute() or ".." in candidate.parts
            or not candidate.parts or candidate.suffix.lower() not in SUFFIXES
            or FORBIDDEN.search(relative)):
        raise EvidenceError("unsafe or potential credential-bearing evidence path")
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise EvidenceError("symlink inside evidence path")
    if not current.is_file() or not 0 < current.stat().st_size <= MAX_FILE:
        raise EvidenceError("missing, empty or oversized evidence file")
    digest = hashlib.sha256()
    with current.open("rb") as source:
        while True:
            data = source.read(65536)
            if not data:
                break
            digest.update(data)
    return {"relativePath": candidate.as_posix(), "sha256": digest.hexdigest(),
            "bytes": current.stat().st_size}


def prepare(root: Path, *, run_id: str, environment: str,
            paths: list[str], now: int | None = None) -> dict:
    if type(run_id) is not str or not RUN_RE.fullmatch(run_id):
        raise EvidenceError("invalid experiment ID")
    if environment not in ("windows-local", "ubuntu-vm", "ubuntu-independent-vm",
                           "qbft-validator", "legacy-anvil", "external-participant"):
        raise EvidenceError("invalid experimental environment")
    if not 1 <= len(paths) <= MAX_INPUTS or len(paths) != len(set(paths)):
        raise EvidenceError("provide distinct 1-32 evidence files")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise EvidenceError("no source checkout")
    files = [inspect_file(root, path) for path in paths]
    return {
        "kind": "SSE_EXPERIMENT_EVIDENCE_V1",
        "runId": run_id,
        "recordedUnixSeconds": int(time.time()) if now is None else now,
        "sourceGitSha": git_sha(root),
        "environment": environment,
        "pythonVersion": platform.python_version(),
        "osType": platform.system(),
        "files": files,
        "rawEvidenceBackedUp": False,
        "chainStateBackedUp": False,
        "acceptanceReviewed": False,
        "warning": "Hash/index only; preserve raw logs and chain snapshots separately."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a read-only experiment evidence hash manifest")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--file", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        info = prepare(args.repo, run_id=args.run_id,
                       environment=args.environment, paths=args.file)
        if (args.output.exists() or args.output.is_symlink() or
                not args.output.parent.is_dir()):
            raise EvidenceError("output must be a NEW file in an existing directory")
        text = json.dumps(info, sort_keys=True, indent=2) + "\n"
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        print(json.dumps({"result": "EVIDENCE_HASH_MANIFEST_CREATED",
                          "path": str(args.output), "fileCount": len(info["files"]),
                          "rawDataPreserved": False,
                          "vmSafeToDestroy": False}, indent=2))
        return 0
    except (EvidenceError, OSError, ValueError) as exc:
        print("SSE_EVIDENCE_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
