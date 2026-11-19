#!/usr/bin/env python3
"""Verify signed SSE software release manifests before any VM update.

Release verification is intentionally read-only. The approved Ed25519 public key
must be distributed out of band, not dynamically downloaded with the manifest.
A passing check does not activate code, deploy a contract or authorize restarts.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
ROLES = frozenset(("provider", "consumer", "monitor", "observer"))
FIELDS = frozenset(("kind", "revision", "chainId", "settlement", "roles",
                    "createdAt", "expiresAt", "artifactUrl", "artifactSha256"))


class ReleaseError(ValueError):
    pass


def canonical(payload: dict) -> bytes:
    if type(payload) is not dict or set(payload) != FIELDS:
        raise ReleaseError("unexpected release manifest fields")
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReleaseError("non-canonical release manifest payload") from exc


def inspect_payload(payload, *, expected_chain_id: int, settlement: str,
                    required_roles: tuple[str, ...], now: int) -> dict:
    canonical(payload)
    if payload["kind"] != "SSE_RELEASE_V1" or type(payload["revision"]) is not str or not SHA.fullmatch(payload["revision"]):
        raise ReleaseError("unsupported release or invalid immutable commit")
    if type(payload["chainId"]) is not int or payload["chainId"] != expected_chain_id:
        raise ReleaseError("release is not for this chain")
    if (type(payload["settlement"]) is not str or not ADDRESS.fullmatch(payload["settlement"])
            or payload["settlement"].lower() != settlement.lower() or int(payload["settlement"], 16) == 0):
        raise ReleaseError("release is not for this settlement")
    roles = payload["roles"]
    if (type(roles) is not list or not roles or any(type(x) is not str or x not in ROLES for x in roles)
            or len(roles) != len(set(roles)) or not set(required_roles).issubset(set(roles))):
        raise ReleaseError("incompatible release roles")
    if (type(payload["createdAt"]) is not int or type(payload["expiresAt"]) is not int
            or not 0 <= payload["createdAt"] <= now < payload["expiresAt"]
            or payload["expiresAt"] - payload["createdAt"] > 14 * 86400):
        raise ReleaseError("release manifest expired or future-dated")
    url = payload["artifactUrl"]
    if type(url) is not str:
        raise ReleaseError("release artifact URL invalid")
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username or u.password or
            u.fragment or u.query or not u.path.startswith("/") or
            any(c.isspace() for c in url)):
        raise ReleaseError("release artifact requires plain HTTPS URL")
    if type(payload["artifactSha256"]) is not str or not HEX.fullmatch(payload["artifactSha256"]):
        raise ReleaseError("invalid artifact SHA-256 digest")
    return {"revision": payload["revision"].lower(), "roles": roles,
            "chainId": expected_chain_id, "settlement": settlement.lower(),
            "artifactUrl": url, "artifactSha256": payload["artifactSha256"].lower()}


def verify_envelope(envelope: dict, public_key_pem: str, *,
                    expected_chain_id: int, settlement: str,
                    required_roles: tuple[str, ...], now: int | None = None) -> dict:
    from Crypto.PublicKey import ECC
    from Crypto.Signature import eddsa

    if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
        raise ReleaseError("invalid signed release envelope")
    data = canonical(envelope["payload"])
    signature = envelope["signature"]
    if type(signature) is not str or len(signature) > 128:
        raise ReleaseError("signature encoding invalid")
    try:
        sig = base64.b64decode(signature, validate=True)
        if len(sig) != 64:
            raise ReleaseError("Ed25519 signature length invalid")
        pub = ECC.import_key(public_key_pem)
        if pub.has_private() or pub.curve != "Ed25519":
            raise ReleaseError("expected public Ed25519 verification key")
        eddsa.new(pub, "rfc8032").verify(data, sig)
    except (ValueError, binascii.Error, TypeError) as exc:
        raise ReleaseError("release signature verification failed") from None
    details = inspect_payload(envelope["payload"], expected_chain_id=expected_chain_id,
                              settlement=settlement, required_roles=required_roles,
                              now=int(time.time()) if now is None else now)
    return {**details, "verified": True, "requiresOperatorRolloutGate": True,
            "softwareApplied": False, "chainTransactionsSent": False}


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only SSE signed-release verification")
    p.add_argument("--envelope", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--settlement", required=True)
    p.add_argument("--roles", required=True)
    p.add_argument("--installed-sha", required=True)
    args = p.parse_args(argv)
    try:
        if not SHA.fullmatch(args.installed_sha):
            raise ReleaseError("invalid installed commit")
        roles = tuple(x.strip() for x in args.roles.split(","))
        if not roles or any(x not in ROLES for x in roles) or len(set(roles)) != len(roles):
            raise ReleaseError("invalid configured roles")
        if args.envelope.stat().st_size > 16384 or args.public_key.stat().st_size > 8192:
            raise ReleaseError("release data too large")
        details = verify_envelope(json.loads(args.envelope.read_text(encoding="utf-8")),
                                  args.public_key.read_text(encoding="ascii"),
                                  expected_chain_id=args.chain_id,
                                  settlement=args.settlement,
                                  required_roles=roles)
        details["updateAvailable"] = details["revision"] != args.installed_sha.lower()
        print(json.dumps(details, sort_keys=True, indent=2))
        return 0
    except (ReleaseError, OSError, ValueError, UnicodeError) as exc:
        print("SSE_RELEASE_VERIFY_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
