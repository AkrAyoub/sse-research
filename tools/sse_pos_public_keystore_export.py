#!/usr/bin/env python3
"""R25: extract PUBLIC-only metadata from locally owned encrypted EIP-2335 keys.

Never decrypt, upload, log, copy, or transmit keystore ciphertext, passwords,
mnemonics or signing keys. Even valid-looking keystore metadata does NOT prove
BLS subgroup validity or actual private-key control.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

from sse_pos_genesis_contributions import (
    SCHEMA, BALANCE_GWEI, OPERATOR_ID, HEX_PUB, _unique_json
)

EVM_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
MAX_ENCRYPTED_KEYSTORE_BYTES = 128_000
MAX_LOCAL_KEYS = 4096


class PublicKeystoreExportError(ValueError):
    pass


def secure_keystore_dir(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise PublicKeystoreExportError("owner local encrypted keystore directory required")
    ds = directory.stat()
    if ds.st_uid != os.geteuid() or stat.S_IMODE(ds.st_mode) != 0o700:
        raise PublicKeystoreExportError("keystore directory must be owner-owned 0700")
    # EIP-2335 export folders have flat keystore-*.json; Lighthouse local
    # account CLI also writes <validator_pubkey>/voting-keystore.json.
    # Only these exact shapes are supported. Password files are never read.
    flats = sorted(directory.glob("*.json"))
    nested = sorted(directory.glob("*/voting-keystore.json"))
    files = flats + nested
    if len(set(files)) != len(files):
        raise PublicKeystoreExportError("duplicate keystore path")
    if not 1 <= len(files) <= MAX_LOCAL_KEYS:
        raise PublicKeystoreExportError("must contain actual local encrypted validator key files")
    for p in files:
        if p.parent != directory:
            folder = p.parent
            if folder.is_symlink() or not folder.is_dir():
                raise PublicKeystoreExportError("nested validator dir invalid")
            fs_dir = folder.stat()
            if (fs_dir.st_uid != os.geteuid()
                    or stat.S_IMODE(fs_dir.st_mode) != 0o700):
                raise PublicKeystoreExportError("nested validator dir must be 0700 owner")
        if p.is_symlink() or not p.is_file():
            raise PublicKeystoreExportError("keystore symlink/non-file refused")
        fs = p.stat()
        if fs.st_uid != os.geteuid() or stat.S_IMODE(fs.st_mode) != 0o600:
            raise PublicKeystoreExportError("encrypted keystore files must be owner-owned 0600")
        if not 0 < fs.st_size <= MAX_ENCRYPTED_KEYSTORE_BYTES:
            raise PublicKeystoreExportError("keystore size invalid")
    return files


def public_pubkey_from_encrypted_keyfile(path: Path) -> str:
    # Never return/print the parsed JSON, which contains encrypted material.
    try:
        root = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_json)
    except (UnicodeError, ValueError) as exc:
        raise PublicKeystoreExportError("invalid encrypted EIP-2335 keystore JSON") from exc
    if type(root) is not dict or type(root.get("version")) is not int or root["version"] != 4:
        raise PublicKeystoreExportError("only encrypted EIP-2335 keystore v4 supported")
    kdf = root.get("crypto")
    if type(kdf) is not dict or not all(k in kdf for k in ("kdf", "cipher", "checksum")):
        raise PublicKeystoreExportError("missing encrypted signing keystore structure")
    cipher = kdf["cipher"]
    if (type(cipher) is not dict or type(cipher.get("message")) is not str
            or not re.fullmatch(r"[0-9a-fA-F]{64}", cipher["message"])):
        raise PublicKeystoreExportError("encrypted keystore cipher message missing")
    key = root.get("pubkey")
    if type(key) is not str:
        raise PublicKeystoreExportError("missing public signing BLS key")
    key = key.lower().removeprefix("0x")
    formatted = "0x" + key
    if not HEX_PUB.fullmatch(formatted) or int(key, 16) == 0:
        raise PublicKeystoreExportError("invalid public BLS key shape")
    return formatted


def export_public(directory: Path, *, operator_id: str,
                  withdrawal_address: str, output: Path) -> dict:
    if not OPERATOR_ID.fullmatch(operator_id):
        raise PublicKeystoreExportError("invalid declarative operator label")
    if not EVM_ADDRESS.fullmatch(withdrawal_address) or int(withdrawal_address, 16) == 0:
        raise PublicKeystoreExportError("nonzero real owner TEST-only withdrawal address required")
    files = secure_keystore_dir(directory)
    pubs = [public_pubkey_from_encrypted_keyfile(f) for f in files]
    if len(pubs) != len(set(pubs)):
        raise PublicKeystoreExportError("duplicate BLS public signing key in local keystores")
    cred = "0x01" + "00" * 11 + withdrawal_address[2:].lower()
    public_json = {
        "schema": SCHEMA,
        "operatorId": operator_id,
        "validators": [
            {
                "pubkey": key,
                "withdrawalCredentials": cred,
                "balanceGwei": BALANCE_GWEI,
            } for key in sorted(pubs)
        ],
    }
    if output.is_symlink() or output.exists() or not output.parent.is_dir():
        raise PublicKeystoreExportError("public output must be create-only in existing directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(output, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(public_json, out, sort_keys=True, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise
    # Only PUBLIC metadata emitted. No ciphertext, UUID/path or password.
    return {
        "schema": "SSE_R25_PUBLIC_KEYSTORE_EXPORT_REVIEW_V1",
        "operatorId": operator_id,
        "publicValidatorKeys": len(pubs),
        "publicOutput": str(output),
        "encryptedKeystoresNotCopied": True,
        "blsPrivateKeyPossessionVerified": False,
        "publicMultioperatorNetworkReady": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Locally export PUBLIC BLS pubkeys from encrypted EIP-2335 keystore metadata; never copy secrets")
    p.add_argument("--keystore-dir", type=Path, required=True)
    p.add_argument("--operator-id", required=True)
    p.add_argument("--withdrawal-address", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = export_public(
            args.keystore_dir, operator_id=args.operator_id,
            withdrawal_address=args.withdrawal_address, output=args.output
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (PublicKeystoreExportError, OSError, ValueError) as exc:
        print("SSE_R25_KEYSTORE_EXPORT_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
