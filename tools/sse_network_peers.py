#!/usr/bin/env python3
"""Signed QBFT peer catalog: portable peer discovery across clouds and changing IPs.

Trust the pinned offline Ed25519 public key, genesis hash and chain ID.
Peer DNS names are LOCATORS; enode public keys are peer IDENTITIES.
This module never sends transactions, grants validator status, or exposes RPC.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import ipaddress
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

SCHEMA = "SSE_QBFT_PEERS_V1"
CHAIN_ID = 31338
MAX_NODES = 64
MAX_MANIFEST_BYTES = 65536
MAX_AGE_SECONDS = 14 * 86400
IDENTITY = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
HEX32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
GITSHA = re.compile(r"[0-9a-fA-F]{40}\Z")
ENODE = re.compile(r"enode://([0-9a-fA-F]{128})@([a-zA-Z0-9.-]+):([0-9]{1,5})\Z")
DNS = re.compile(r"(?=.{4,253}\Z)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z")
FIELDS = frozenset({"schema", "chainId", "genesisHash", "revision", "issuedAt", "expiresAt", "nodes"})
NODE_FIELDS = frozenset({"nodeId", "role", "enode"})
ROLES = frozenset({"validator", "bootstrap", "full"})


class PeerCatalogError(ValueError):
    pass


def canonical(payload: dict) -> bytes:
    if type(payload) is not dict or set(payload) != FIELDS:
        raise PeerCatalogError("unexpected peer manifest fields")
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          allow_nan=False, ensure_ascii=True).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PeerCatalogError("noncanonical manifest") from exc


def validate_enode(url: str) -> tuple[str, str, int]:
    if type(url) is not str or len(url) > 460:
        raise PeerCatalogError("invalid enode URL")
    match = ENODE.fullmatch(url)
    if not match:
        raise PeerCatalogError("enode must include a complete node public key, host, TCP port")
    node_key, host, port_string = match.groups()
    if int(node_key, 16) == 0:
        raise PeerCatalogError("zero enode public key")
    port = int(port_string)
    if not 1024 <= port <= 65535:
        raise PeerCatalogError("invalid P2P port")
    host = host.lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if not DNS.fullmatch(host) or host.endswith(".local"):
            raise PeerCatalogError("peer address must use an FQDN or routable/overlay IP")
    else:
        # 100.64/10 is Tailscale's CGNAT address space; other RFC1918 lab
        # addresses do not provide globally reachable bootstrap locators.
        overlay = ip in ipaddress.ip_network("100.64.0.0/10")
        if not overlay and not ip.is_global:
            raise PeerCatalogError("unroutable private/loopback peer IP; use overlay name/IP")
    return node_key.lower(), host, port


def validate_payload(payload: dict, *, chain_id: int, genesis_hash: str,
                     now: int | None = None) -> dict:
    canonical(payload)
    now = int(time.time()) if now is None else now
    if (payload["schema"] != SCHEMA or type(payload["chainId"]) is not int
            or payload["chainId"] != CHAIN_ID
            or chain_id != CHAIN_ID):
        raise PeerCatalogError("incorrect QBFT chain ID or schema")
    gh = payload["genesisHash"]
    if (type(gh) is not str or not HEX32.fullmatch(gh)
            or int(gh, 16) == 0 or gh.lower() != genesis_hash.lower()):
        raise PeerCatalogError("mismatched immutable genesis hash")
    if type(payload["revision"]) is not str or not GITSHA.fullmatch(payload["revision"]):
        raise PeerCatalogError("unapproved release revision format")
    issued = payload["issuedAt"]
    expires = payload["expiresAt"]
    if (type(issued) is not int or type(expires) is not int
            or not 0 <= issued <= now < expires
            or expires - issued > MAX_AGE_SECONDS):
        raise PeerCatalogError("expired, future-dated or overlong peer catalog")
    nodes = payload["nodes"]
    if type(nodes) is not list or not 4 <= len(nodes) <= MAX_NODES:
        raise PeerCatalogError("QBFT catalog requires 4-64 named nodes")
    ids, keys, validators = set(), set(), 0
    for node in nodes:
        if type(node) is not dict or set(node) != NODE_FIELDS:
            raise PeerCatalogError("invalid node schema")
        name, role, enode = node["nodeId"], node["role"], node["enode"]
        if type(name) is not str or not IDENTITY.fullmatch(name) or name in ids:
            raise PeerCatalogError("duplicate or malformed stable node identity")
        if type(role) is not str or role not in ROLES:
            raise PeerCatalogError("invalid QBFT node role")
        key, _, _ = validate_enode(enode)
        if key in keys:
            raise PeerCatalogError("duplicated node key")
        ids.add(name)
        keys.add(key)
        validators += int(role == "validator")
    if validators < 4:
        raise PeerCatalogError("initial independent QBFT research requires 4 validators")
    return {"chainId": CHAIN_ID, "genesisHash": gh.lower(),
            "revision": payload["revision"].lower(), "validators": validators,
            "nodes": nodes, "expiresAt": expires}


def _import_public(pem: str):
    try:
        key = ECC.import_key(pem)
    except (ValueError, TypeError) as exc:
        raise PeerCatalogError("invalid Ed25519 trust key") from None
    if key.curve != "Ed25519" or key.has_private():
        raise PeerCatalogError("expected independent pinned PUBLIC Ed25519 trust key")
    return key


def verify(envelope: dict, public_key_pem: str, *, chain_id: int,
           genesis_hash: str, now: int | None = None) -> dict:
    if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
        raise PeerCatalogError("invalid signed peer catalog envelope")
    message = canonical(envelope["payload"])
    text = envelope["signature"]
    if type(text) is not str or len(text) > 128:
        raise PeerCatalogError("invalid signature")
    try:
        signature = base64.b64decode(text, validate=True)
        if len(signature) != 64:
            raise PeerCatalogError("incorrect signature length")
        eddsa.new(_import_public(public_key_pem), "rfc8032").verify(message, signature)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise PeerCatalogError("peer catalog signature verification failed") from None
    result = validate_payload(envelope["payload"], chain_id=chain_id,
                              genesis_hash=genesis_hash, now=now)
    return {**result, "signatureVerified": True, "transactionsSent": False}


def sign(payload: dict, private_key_pem: str, *, chain_id: int,
         genesis_hash: str, now: int | None = None) -> dict:
    # Run only on an offline / separately secured operator computer.
    validate_payload(payload, chain_id=chain_id, genesis_hash=genesis_hash, now=now)
    try:
        secret = ECC.import_key(private_key_pem)
        if secret.curve != "Ed25519" or not secret.has_private():
            raise PeerCatalogError("expected offline PRIVATE Ed25519 signing key")
        signature = eddsa.new(secret, "rfc8032").sign(canonical(payload))
    except (ValueError, TypeError) as exc:
        raise PeerCatalogError("invalid offline signing key") from None
    return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}


def bootnodes(verified: dict, *, self_id: str) -> str:
    if type(self_id) is not str or not IDENTITY.fullmatch(self_id):
        raise PeerCatalogError("invalid own stable node identity")
    if self_id not in {item["nodeId"] for item in verified["nodes"]}:
        raise PeerCatalogError("own identity not authorized in catalog")
    peers = [n["enode"] for n in verified["nodes"] if n["nodeId"] != self_id]
    return "".join(value + "\n" for value in peers)


def _read(path: Path, max_bytes: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise PeerCatalogError("invalid or oversized input file")
    return path.read_text(encoding="utf-8")


def _create_new(path: Path, content: str):
    if not path.parent.is_dir() or path.is_symlink() or path.exists():
        raise PeerCatalogError("refusing to overwrite output or use missing directory")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    ap = argparse.ArgumentParser(description="SSE signed WAN peer catalog (no transactions)")
    sub = ap.add_subparsers(dest="action", required=True)
    for command in ("sign", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--chain-id", type=int, default=CHAIN_ID)
        p.add_argument("--genesis-hash", required=True)
        p.add_argument("--output", type=Path)
        if command == "sign":
            p.add_argument("--payload", type=Path, required=True)
            p.add_argument("--private-key", type=Path, required=True)
        else:
            p.add_argument("--manifest", type=Path, required=True)
            p.add_argument("--public-key", type=Path, required=True)
            p.add_argument("--self-id")
    a = ap.parse_args(argv)
    try:
        if a.action == "sign":
            secret_file = a.private_key
            if (secret_file.is_symlink() or not secret_file.is_file()
                    or (os.name == "posix" and stat.S_IMODE(secret_file.stat().st_mode) != 0o600)):
                raise PeerCatalogError("offline signing key must be private file mode 0600")
            doc = json.loads(_read(a.payload, MAX_MANIFEST_BYTES))
            envelope = sign(doc, _read(secret_file, 8192), chain_id=a.chain_id,
                            genesis_hash=a.genesis_hash)
            if a.output is None:
                raise PeerCatalogError("signing requires a new output file")
            _create_new(a.output, json.dumps(envelope, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"result": "SIGNED_CATALOG_CREATED", "path": str(a.output)}))
        else:
            envelope = json.loads(_read(a.manifest, MAX_MANIFEST_BYTES))
            details = verify(envelope, _read(a.public_key, 8192),
                             chain_id=a.chain_id, genesis_hash=a.genesis_hash)
            if a.output:
                if not a.self_id:
                    raise PeerCatalogError("--output needs --self-id")
                _create_new(a.output, bootnodes(details, self_id=a.self_id))
            print(json.dumps({k: v for k, v in details.items() if k != "nodes"},
                             sort_keys=True, indent=2))
        return 0
    except (PeerCatalogError, ValueError, OSError, UnicodeError) as exc:
        print("SSE_PEERS_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
