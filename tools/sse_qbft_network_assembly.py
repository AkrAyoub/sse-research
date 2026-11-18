#!/usr/bin/env python3
"""Assemble four PUBLIC validator announcements into one R9 genesis/catalog.

Never handles or generates private keys. Public addresses from four independently
operated VMs feed the canonical QBFT genesis; after boot0 is observed the same
roster feeds a time-bound SIGNABLE peer catalog, with an actual genesis hash.
No GitHub Actions and no Ethereum transactions.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time

from eth_keys import keys

from sse_qbft_lab_config import genesis, trials
from sse_network_peers import (validate_enode, validate_payload,
                               CHAIN_ID, SCHEMA, PeerCatalogError)

SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX32 = re.compile(r"0x[0-9a-f]{64}\Z")
ALLOWED_ID = {f"validator-{i}" for i in range(1, 5)}
PUBLIC_FIELDS = {
    "schema", "nodeId", "chainId", "validatorAddress", "enodePublicKey",
    "overlayIPv4", "enode", "privateKeyIncluded",
    "chainParticipationStarted", "physicalIndependenceProved"
}


class AssemblyError(ValueError):
    pass


def load_public(source: Path) -> dict:
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 4096:
        raise AssemblyError("unsafe or oversized public validator record")
    try:
        doc = json.loads(source.read_text("utf-8"))
    except (ValueError, UnicodeError):
        raise AssemblyError("invalid public validator JSON") from None
    if type(doc) is not dict or set(doc) != PUBLIC_FIELDS:
        raise AssemblyError("public record schema mismatch")
    if (doc["schema"] != "SSE_QBFT_PUBLIC_VALIDATOR_V1"
            or doc["nodeId"] not in ALLOWED_ID
            or type(doc["chainId"]) is not int or doc["chainId"] != CHAIN_ID
            or doc["privateKeyIncluded"] is not False
            or doc["chainParticipationStarted"] is not False
            or doc["physicalIndependenceProved"] is not False):
        raise AssemblyError("invalid source role, chain or attestation fields")
    pub = doc["enodePublicKey"]
    if type(pub) is not str or not re.fullmatch(r"[0-9a-f]{128}\Z", pub):
        raise AssemblyError("invalid P2P public key")
    try:
        address = keys.PublicKey(bytes.fromhex(pub)).to_checksum_address().lower()
    except (ValueError, TypeError):
        raise AssemblyError("invalid validator public key") from None
    if doc["validatorAddress"] != address:
        raise AssemblyError("validator address does not derive from P2P node key")
    key, ip, port = validate_enode(doc["enode"])
    if (key != pub or ip != doc["overlayIPv4"] or port != 30303
            or ipaddress.ip_address(ip) not in ipaddress.ip_network("100.64.0.0/10")):
        raise AssemblyError("enode locator/key does not match public validator record")
    return doc


def validate_roster(public: list[dict]) -> list[dict]:
    if len(public) != 4:
        raise AssemblyError("require four independent public validator records")
    ids = {d["nodeId"] for d in public}
    addresses = {d["validatorAddress"] for d in public}
    keys_ = {d["enodePublicKey"] for d in public}
    locators = {d["overlayIPv4"] for d in public}
    if ids != ALLOWED_ID or len(addresses) != 4 or len(keys_) != 4 or len(locators) != 4:
        raise AssemblyError("duplicate identity/key/IP or missing validator slot")
    return sorted(public, key=lambda d: d["nodeId"])


def make_genesis_bundle(public: list[dict], funded: list[str] | None = None) -> dict:
    records = validate_roster(public)
    return {
        "genesis.json": genesis([d["validatorAddress"] for d in records],
                                funded=funded or []),
        "benchmark-plan.json": trials(),
        "public-roster.json": {
            "schema": "SSE_QBFT_PUBLIC_ROSTER_V1",
            "chainId": CHAIN_ID,
            "validators": records,
            "privateKeysIncluded": False,
            "independentHostsVerified": False,
        },
    }


def make_catalog(public: list[dict], *, genesis_hash: str,
                 revision: str, issued: int, ttl: int = 86400) -> dict:
    records = validate_roster(public)
    if (type(revision) is not str or not SHA.fullmatch(revision)
            or type(genesis_hash) is not str or not HEX32.fullmatch(genesis_hash)
            or not 3600 <= ttl <= 7 * 86400):
        raise AssemblyError("invalid Git revision/genesis block hash/catalog TTL")
    payload = {
        "schema": SCHEMA, "chainId": CHAIN_ID,
        "genesisHash": genesis_hash, "revision": revision,
        "issuedAt": issued, "expiresAt": issued + ttl,
        "nodes": [{"nodeId": d["nodeId"], "role": "validator",
                   "enode": d["enode"]} for d in records],
    }
    validate_payload(payload, chain_id=CHAIN_ID, genesis_hash=genesis_hash, now=issued)
    return payload


def write_bundle(folder: Path, content: dict[str, object]):
    if not folder.is_dir() or folder.is_symlink():
        raise AssemblyError("output must be an existing private directory")
    for name in content:
        if (folder / name).exists() or (folder / name).is_symlink():
            raise AssemblyError("refusing to overwrite existing QBFT artifact")
    for name, data in content.items():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(folder / name, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, sort_keys=True)+"\n")


def main(argv=None):
    p=argparse.ArgumentParser(description="Assemble key-free R9 genesis and signable peers")
    p.add_argument("action", choices=("genesis","catalog"))
    p.add_argument("--public", action="append", required=True, type=Path)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--fund", action="append", default=[])
    p.add_argument("--genesis-hash")
    p.add_argument("--revision")
    p.add_argument("--ttl-seconds", type=int, default=86400)
    a=p.parse_args(argv)
    try:
        records=[load_public(x) for x in a.public]
        if a.action=="genesis":
            content=make_genesis_bundle(records,funded=a.fund)
        else:
            if not a.revision or not a.genesis_hash:
                raise AssemblyError("catalog needs actual observed genesis hash and Git revision")
            content={"peer-catalog-unsigned.json":make_catalog(
                records,genesis_hash=a.genesis_hash,
                revision=a.revision,issued=int(time.time()),ttl=a.ttl_seconds)}
        write_bundle(a.output_dir,content)
        print(json.dumps({"result":"PUBLIC_ONLY_QBFT_"+a.action.upper()+"_CREATED",
                          "files":sorted(content), "privateKeysIncluded":False,
                          "networkStarted":False,"transactionsSent":False},indent=2))
        return 0
    except (AssemblyError,PeerCatalogError,ValueError,OSError,TypeError,
            KeyError) as exc:
        print("SSE_QBFT_ASSEMBLY_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
