#!/usr/bin/env python3
"""Install a signed SSE GitHub-source snapshot from public HTTPS, without a GitHub token.

Publisher manually exports reviewed Git commit as .tar.gz, signs SHA256 + SHA
via the existing sse_release_verify.py manifest (Ed25519). This installer
stages source only, never touches wallets, chain state, SSH, systemd, or Docker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tempfile
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sse_release_verify import ReleaseError, verify_envelope

MAX_ARCHIVE = 80 * 1024 * 1024
MAX_FILES = 20000
MAX_EXTRACTED = 128 * 1024 * 1024


class InstallerError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InstallerError("release artifact redirect forbidden")


def download_verified(url: str, expected_sha256: str, destination: Path) -> int:
    """Trusted URL comes only from a verified publisher envelope."""
    request = Request(url, headers={"Accept": "application/gzip"})
    total = 0
    digest = hashlib.sha256()
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise InstallerError("release endpoint not successful")
            with destination.open("xb") as out:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ARCHIVE:
                        raise InstallerError("release exceeds 80 MiB download cap")
                    digest.update(chunk)
                    out.write(chunk)
        if total == 0 or digest.hexdigest() != expected_sha256:
            raise InstallerError("signed artifact SHA256 mismatch")
        return total
    except (OSError, TimeoutError):
        raise InstallerError("release download unavailable") from None


def safe_extract(archive_path: Path, staging: Path) -> Path:
    """Extract ONLY regular files/directories inside one sse-research/ root."""
    extracted = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_FILES:
            raise InstallerError("empty/oversized release file list")
        for item in members:
            name = PurePosixPath(item.name)
            if (name.is_absolute() or not name.parts or name.parts[0] != "sse-research"
                    or any(part in ("..", ".") for part in name.parts)
                    or not (item.isfile() or item.isdir())
                    or item.size < 0 or item.size > 32 * 1024 * 1024
                    or item.mode & 0o6000):
                raise InstallerError("unsafe release archive entry")
            extracted += item.size
            if extracted > MAX_EXTRACTED:
                raise InstallerError("release expands beyond size cap")
        archive.extractall(path=staging, filter="data")
    repo = staging / "sse-research"
    if not repo.is_dir() or repo.is_symlink():
        raise InstallerError("release did not contain sse-research directory")
    if not (repo / "contracts" / "SSESettlement.sol").is_file():
        raise InstallerError("release missing expected source tree")
    if (repo / ".git").exists():
        raise InstallerError("release must be a Git archive without private history")
    return repo


def install(envelope: dict, publisher_public_pem: str, *,
            expected_chain_id: int, settlement: str,
            roles: tuple[str, ...], target: Path,
            now: int | None = None, download=download_verified) -> dict:
    verified = verify_envelope(envelope, publisher_public_pem,
                               expected_chain_id=expected_chain_id,
                               settlement=settlement,
                               required_roles=roles, now=now)
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise InstallerError("release target must be a new absolute path")
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink():
        raise InstallerError("release parent must be existing real directory")
    with tempfile.TemporaryDirectory(prefix=".sse-release-stage-", dir=parent) as temp:
        work = Path(temp)
        bundle = work / "release.tar.gz"
        count = download(verified["artifactUrl"], verified["artifactSha256"], bundle)
        actual = hashlib.sha256(bundle.read_bytes()).hexdigest()
        if actual != verified["artifactSha256"] or not 0 < count <= MAX_ARCHIVE:
            raise InstallerError("unverified release archive bytes")
        repo = safe_extract(bundle, work)
        if target.exists() or target.is_symlink():
            raise InstallerError("release target appeared concurrently")
        repo.rename(target)
    return {
        "result": "SIGNED_GITHUB_SOURCE_SNAPSHOT_INSTALLED",
        "approvedGitRevision": verified["revision"],
        "releasePath": str(target),
        "publisherSignatureVerified": True,
        "archiveSha256Verified": True,
        "includesGitHistory": False,
        "dependenciesInstalled": False,
        "networkJoined": False,
        "ethereumRolesActivated": False,
        "ethereumTransactionsSent": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Install reviewed SSE source snapshot from public HTTPS")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--publisher-public-key", type=Path, required=True)
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--settlement", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--target", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    try:
        if (a.manifest.is_symlink() or a.publisher_public_key.is_symlink()
                or a.manifest.stat().st_size > 16384
                or a.publisher_public_key.stat().st_size > 8192):
            raise InstallerError("invalid signed manifest/public key")
        roles = tuple(x.strip() for x in a.roles.split(","))
        envelope = json.loads(a.manifest.read_text("utf-8"))
        pem = a.publisher_public_key.read_text("utf-8")
        if a.apply:
            result = install(envelope, pem, expected_chain_id=a.chain_id,
                             settlement=a.settlement, roles=roles, target=a.target)
        else:
            info = verify_envelope(envelope, pem, expected_chain_id=a.chain_id,
                                   settlement=a.settlement, required_roles=roles)
            result = {"result": "SIGNED_RELEASE_VERIFIED_DRY_RUN",
                      "revision": info["revision"],
                      "sourceTarget": str(a.target), "networkJoined": False,
                      "transactionsSent": False}
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (InstallerError, ReleaseError, OSError, ValueError, UnicodeError,
            tarfile.TarError) as exc:
        print("SSE_SIGNED_INSTALL_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
