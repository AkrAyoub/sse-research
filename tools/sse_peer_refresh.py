#!/usr/bin/env python3
"""Fetch signed WAN peer announcements and stage Besu bootnodes without trusting IPs.

No GitHub Actions, Ethereum signing, automatic service restarts or validator votes.
Can be run manually or by an approved Ubuntu systemd timer.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sse_network_peers import (PeerCatalogError, bootnodes, verify,
                               MAX_MANIFEST_BYTES, _read)


class PeerRefreshError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PeerRefreshError("peer manifest redirects forbidden")


def trusted_https_url(value: str) -> str:
    if type(value) is not str or len(value) > 2048 or any(x.isspace() for x in value):
        raise PeerRefreshError("invalid manifest HTTPS URL")
    u = urlsplit(value)
    if (u.scheme != "https" or not u.hostname or u.username or u.password
            or u.query or u.fragment or not u.path.startswith("/")
            or ".." in u.path.split("/")):
        raise PeerRefreshError("manifest requires plain HTTPS with no credentials")
    return value


def download_manifest(url: str) -> bytes:
    trusted_https_url(url)
    req = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=10) as response:
            if response.status != 200:
                raise PeerRefreshError("manifest endpoint did not return HTTP 200")
            result = response.read(MAX_MANIFEST_BYTES + 1)
    except (OSError, TimeoutError):
        raise PeerRefreshError("signed manifest endpoint unavailable") from None
    if len(result) > MAX_MANIFEST_BYTES:
        raise PeerRefreshError("signed manifest too large")
    return result


def _atomic_replace(path: Path, data: bytes) -> None:
    parent = path.parent
    if (not parent.is_dir() or parent.is_symlink() or
            parent.stat().st_mode & 0o022 or
            (path.exists() and (path.is_symlink() or not path.is_file()))):
        raise PeerRefreshError("peer output must be in protected real directory")
    fd, tmp = tempfile.mkstemp(prefix=".sse-peers-", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def prepare(raw: bytes, public_key: str, *, chain_id: int,
            genesis_hash: str, self_id: str,
            previous: dict | None = None, now=None) -> tuple[dict, bytes]:
    if len(raw) > MAX_MANIFEST_BYTES:
        raise PeerRefreshError("oversized peer catalog")
    try:
        envelope = json.loads(raw)
    except (ValueError, UnicodeError):
        raise PeerRefreshError("invalid peer catalog JSON") from None
    checked = verify(envelope, public_key, chain_id=chain_id,
                     genesis_hash=genesis_hash, now=now)
    if previous is not None:
        # A last-known good catalog may have EXPIRED while a VM was offline.
        # Authenticate that signed historical record at a time inside its
        # validity window, then reject rollback to an earlier publication.
        try:
            previous_expiry = previous["payload"]["expiresAt"]
            check_time = min(int(__import__("time").time()) if now is None else now,
                             previous_expiry - 1)
        except (KeyError, TypeError):
            raise PeerRefreshError("invalid prior catalog") from None
        verify(previous, public_key, chain_id=chain_id,
               genesis_hash=genesis_hash, now=check_time)
        if envelope["payload"]["issuedAt"] < previous["payload"]["issuedAt"]:
            raise PeerRefreshError("peer catalog rollback rejected")
        if (envelope["payload"]["issuedAt"] == previous["payload"]["issuedAt"]
                and envelope != previous):
            raise PeerRefreshError("conflicting catalog at same publication time")
    nodes = bootnodes(checked, self_id=self_id).encode("ascii")
    return envelope, nodes


def main(argv=None):
    p = argparse.ArgumentParser(description="Secure periodic QBFT bootstrap peer refresh")
    p.add_argument("--url", required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--chain-id", type=int, default=31338)
    p.add_argument("--genesis-hash", required=True)
    p.add_argument("--self-id", required=True)
    p.add_argument("--manifest-state", type=Path, required=True)
    p.add_argument("--bootnodes-out", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    try:
        raw = download_manifest(a.url)
        prev = None
        if a.manifest_state.exists():
            prev = json.loads(_read(a.manifest_state, MAX_MANIFEST_BYTES))
        envelope, nodes = prepare(raw, _read(a.public_key, 8192),
                                  chain_id=a.chain_id, genesis_hash=a.genesis_hash,
                                  self_id=a.self_id, previous=prev)
        if a.apply:
            # The source envelope is preserved to reject rollback on the next run.
            # Peers are a discovery hint; restarting Besu is not implicit.
            _atomic_replace(a.manifest_state,
                            (json.dumps(envelope, sort_keys=True, indent=2) + "\n").encode())
            _atomic_replace(a.bootnodes_out, nodes)
        print(json.dumps({
            "result": "PEERS_STAGED" if a.apply else "PEERS_VERIFIED_DRY_RUN",
            "peerCount": len(nodes.splitlines()),
            "publishedAt": envelope["payload"]["issuedAt"],
            "chainId": a.chain_id,
            "besuRestartPerformed": False,
            "ethereumTransactionsSent": False,
        }, indent=2, sort_keys=True))
        return 0
    except (PeerCatalogError, PeerRefreshError, OSError, ValueError,
            UnicodeError) as exc:
        print("SSE_PEER_REFRESH_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
