#!/usr/bin/env python3
"""Create a unique Besu secp256k1 node identity on its OWN Ubuntu VM.

No GitHub/cloud API, Ethereum transaction, external key service, or copy of
another validator's private key is needed. Private key is written ONCE in a
mode-0700 local directory. Only the public validator record is shared.

Dependency: eth-account 0.14.0 (eth_keys is a transitive dependency).
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

from eth_keys import keys

SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
NODE_ID = re.compile(r"validator-[1-4]\Z")
TAILSCALE_SPACE = ipaddress.ip_network("100.64.0.0/10")
KEY_FILENAME = "node.key"


class IdentityError(ValueError):
    pass


def node_key_record(secret: bytes, node_id: str, overlay_ipv4: str) -> dict:
    if type(node_id) is not str or not NODE_ID.fullmatch(node_id):
        raise IdentityError("validator identity must be validator-1 through validator-4")
    try:
        overlay = ipaddress.IPv4Address(overlay_ipv4)
    except (ValueError, ipaddress.AddressValueError):
        raise IdentityError("node needs its own Tailscale overlay IPv4") from None
    if overlay not in TAILSCALE_SPACE:
        raise IdentityError("node locator must be Tailscale IPv4, not campus DHCP")
    if type(secret) is not bytes or len(secret) != 32:
        raise IdentityError("Besu key must be 32 bytes")
    scalar = int.from_bytes(secret, "big")
    if scalar < 1 or scalar >= SECP256K1_N:
        raise IdentityError("invalid secp256k1 private scalar")
    pub = keys.PrivateKey(secret).public_key
    pub64 = pub.to_bytes()
    address = pub.to_checksum_address().lower()
    return {
        "schema": "SSE_QBFT_PUBLIC_VALIDATOR_V1",
        "nodeId": node_id,
        "chainId": 31338,
        "validatorAddress": address,
        "enodePublicKey": pub64.hex(),
        "overlayIPv4": str(overlay),
        "enode": f"enode://{pub64.hex()}@{overlay}:30303",
        "privateKeyIncluded": False,
        "chainParticipationStarted": False,
        "physicalIndependenceProved": False,
    }


def read_private_key(path: Path) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise IdentityError("private key needs an existing regular absolute file")
    st = path.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o600):
        raise IdentityError("private key owner/mode must match local operator and 0600")
    content = path.read_text(encoding="ascii")
    if not re.fullmatch(r"[0-9a-f]{64}\n?", content):
        raise IdentityError("Besu private key file is not canonical 64-hex format")
    return bytes.fromhex(content.strip())


def _secured_directory(folder: Path) -> Path:
    if (not folder.is_absolute() or folder.is_symlink()
            or not folder.is_dir()):
        raise IdentityError("use an existing absolute non-symlink directory")
    st = folder.stat()
    if (st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700):
        raise IdentityError("validator private directory must be owned by operator and 0700")
    return folder


def _write_exclusive(path: Path, data: str, mode: int) -> None:
    if path.exists() or path.is_symlink():
        raise IdentityError("refusing to overwrite existing validator identity")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, mode)
    with os.fdopen(fd, "w", encoding="ascii") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())


def init_local(private_dir: Path, *, public_file: Path,
               node_id: str, overlay_ipv4: str) -> dict:
    if os.name != "posix" or sys.platform != "linux":
        raise IdentityError("validator identity creation requires Ubuntu/Linux")
    folder = _secured_directory(private_dir)
    if (public_file.parent != folder or public_file.name == KEY_FILENAME
            or public_file.is_symlink() or public_file.exists()):
        raise IdentityError("public manifest must be a NEW separate file inside private directory")
    key_file = folder / KEY_FILENAME
    if key_file.exists() or key_file.is_symlink():
        raise IdentityError("validator private key already exists; never replace it")
    # Validate everything before obtaining/writing a new secret.
    node_key_record((1).to_bytes(32, "big"), node_id, overlay_ipv4)
    # Rejection sampling (not modulo reduction), using operating system entropy.
    scalar = secrets.randbelow(SECP256K1_N - 1) + 1
    secret = scalar.to_bytes(32, "big")
    record = node_key_record(secret, node_id, overlay_ipv4)
    _write_exclusive(key_file, secret.hex() + "\n", 0o600)
    # Failure of the public write intentionally leaves the private key intact
    # for operator inspection, never an auto-regeneration or overwrite.
    _write_exclusive(public_file, json.dumps(record, sort_keys=True, indent=2) + "\n", 0o600)
    return record


def inspect_local(private_dir: Path, *, public_file: Path) -> dict:
    folder = _secured_directory(private_dir)
    key = read_private_key(folder / KEY_FILENAME)
    if public_file.parent != folder or public_file.is_symlink():
        raise IdentityError("untrusted public record path")
    doc = json.loads(public_file.read_text(encoding="utf-8"))
    if type(doc) is not dict:
        raise IdentityError("invalid public validator manifest structure")
    try:
        expected = node_key_record(key, doc.get("nodeId"), doc.get("overlayIPv4"))
    except (IdentityError, TypeError, ValueError):
        raise IdentityError("invalid node identity in public manifest") from None
    if set(doc) != set(expected):
        raise IdentityError("invalid public record fields")
    if doc != expected:
        raise IdentityError("local private/public validator identity mismatch")
    return expected


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Node-local Besu validator identity ceremony")
    p.add_argument("action", choices=("init", "inspect"))
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--public-file", type=Path, required=True)
    p.add_argument("--node-id")
    p.add_argument("--tailscale-ip")
    a = p.parse_args(argv)
    try:
        if a.action == "init":
            if not a.node_id or not a.tailscale_ip:
                raise IdentityError("init requires validator ID and Tailscale IPv4")
            result = init_local(a.private_dir, public_file=a.public_file,
                                node_id=a.node_id, overlay_ipv4=a.tailscale_ip)
        else:
            result = inspect_local(a.private_dir, public_file=a.public_file)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (IdentityError, ValueError, OSError, KeyError, TypeError) as exc:
        print("SSE_QBFT_IDENTITY_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
