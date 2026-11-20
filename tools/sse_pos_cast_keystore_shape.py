#!/usr/bin/env python3
"""Read-only PUBLIC SCHEMA-NAMES ONLY probe for an existing Cast EOA keystore.

Never prints a JSON value, ciphertext, password, file path, private key or
recovery phrase. A shape report is NOT cryptographic or password verification.
Use before changing strict acceptance rules in sse_pos_local_wallet_report.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import sys

FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,39}\Z")


class ShapeProbeError(ValueError):
    pass


def _unique_json(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ShapeProbeError("duplicate keystore JSON field")
        out[k] = v
    return out


def _names(mapping) -> list[str]:
    if type(mapping) is not dict:
        raise ShapeProbeError("expected JSON object")
    if not all(type(k) is str and FIELD_NAME.fullmatch(k) for k in mapping):
        # Never print an attacker-controlled key name, which could
        # maliciously include a secret value or control characters.
        raise ShapeProbeError("invalid JSON field name")
    return sorted(mapping)


def shape_only(directory: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise ShapeProbeError("private keystore directory unavailable")
    dst = directory.stat()
    if dst.st_uid != os.geteuid() or stat.S_IMODE(dst.st_mode) & 0o077:
        raise ShapeProbeError("private keystore directory owner/mode invalid")
    files = list(directory.iterdir())
    if len(files) != 1:
        raise ShapeProbeError("expected exactly one existing keystore")
    f = files[0]
    if f.is_symlink() or not f.is_file():
        raise ShapeProbeError("keystore must be a normal non-symlink file")
    st = f.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) & 0o077:
        raise ShapeProbeError("keystore owner/mode invalid")
    if not 100 <= st.st_size <= 65536:
        raise ShapeProbeError("keystore length outside encrypted JSON bounds")
    try:
        data = json.loads(f.read_text(encoding="utf-8"), object_pairs_hook=_unique_json)
    except (ValueError, UnicodeError) as exc:
        raise ShapeProbeError("encrypted keystore is not valid unique-key JSON") from exc
    top = _names(data)
    crypto_fields = []
    for crypto_key in ("crypto", "Crypto"):
        if crypto_key in data:
            crypto_fields = _names(data[crypto_key])
    version = data.get("version")
    return {
        "schema": "SSE_R28_CAST_ENCRYPTED_KEYSTORE_PUBLIC_SCHEMA_ONLY_V1",
        "topLevelFieldNames": top,
        "encryptionFieldNames": crypto_fields,
        "versionIsIntegerThree": type(version) is int and version == 3,
        "addressIsText": type(data.get("address")) is str,
        "privateValuesOrCiphertextPrinted": False,
        "keystorePathOrPasswordPrinted": False,
        "decryptionOrWalletSigningPerformed": False,
        "validEncryptionEnvelopeProved": False,
    }


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Print ONLY field names of existing encrypted owner-local EOA; never field values"
    )
    parser.add_argument("keystore_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        report = shape_only(args.keystore_directory)
    except (ShapeProbeError, OSError) as exc:
        # Error messages are constant and do not interpolate secrets or paths.
        print("R28_WALLET_SHAPE_REFUSED: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
