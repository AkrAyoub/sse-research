#!/usr/bin/env python3
"""Report only PUBLIC address from a locally encrypted Foundry V3 keystore.

Structural verification only: does not decrypt, test the owner's password or
prove custody. NEVER prints the JSON, passphrase, private key, or path to secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

ADDR = re.compile(r"[0-9a-fA-F]{40}\Z")
EXPECTED_KEYS = frozenset({"address", "crypto", "Crypto", "id", "version"})
BAD = frozenset({"privateKey", "private_key", "secretKey", "secret_key", "mnemonic"})


class WalletCheckError(ValueError):
    pass


def inspect_encrypted_dir(directory: Path) -> dict:
    if not directory.is_dir() or directory.is_symlink():
        raise WalletCheckError("keystore directory missing or symlinked")
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise WalletCheckError("keystore directory is accessible by group/other")
    paths = list(directory.iterdir())
    if len(paths) != 1:
        raise WalletCheckError("expected exactly one new encrypted keystore")
    f = paths[0]
    if f.is_symlink() or not f.is_file():
        raise WalletCheckError("keystore must be an ordinary, non-symlink file")
    if f.stat().st_size > 65536 or f.stat().st_size < 100:
        raise WalletCheckError("invalid encrypted keystore file size")
    if stat.S_IMODE(f.stat().st_mode) & 0o077:
        raise WalletCheckError("keystore file has insecure permissions")
    try:
        document = json.loads(f.read_text("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise WalletCheckError("keystore is not valid JSON") from exc
    if type(document) is not dict or BAD & set(document):
        raise WalletCheckError("sensitive/plaintext or invalid keystore fields")
    if not {"address", "id", "version"} <= set(document) or len(set(document) - EXPECTED_KEYS) > 0:
        raise WalletCheckError("unexpected keystore schema")
    addr = document["address"]
    if type(addr) is not str:
        raise WalletCheckError("encrypted keystore missing EOA address")
    if addr.startswith("0x"):
        addr = addr[2:]
    if not ADDR.fullmatch(addr):
        raise WalletCheckError("invalid EOA address in encrypted keystore")
    crypto = document.get("crypto", document.get("Crypto"))
    if type(crypto) is not dict or not all(key in crypto for key in (
        "cipher", "ciphertext", "cipherparams", "kdf", "kdfparams", "mac"
    )):
        raise WalletCheckError("keystore has no Ethereum UTC-V3 encryption envelope")
    if type(crypto["ciphertext"]) is not str or not crypto["ciphertext"]:
        raise WalletCheckError("missing encrypted private key ciphertext")
    if type(document["version"]) is not int or document["version"] != 3:
        raise WalletCheckError("expected encrypted V3 Ethereum keystore")
    return {
        "withdrawalAddress": "0x" + addr,
        "encryptedKeystoreStructurePresent": True,
        "privateKeyPrinted": False,
        "walletPasswordVerified": False,
        "operatorPhysicalIndependenceVerified": False,
        "testEthAvailable": False,
        "genesisOrValidatorActivated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keystore_dir", type=Path)
    args = parser.parse_args()
    try:
        out = inspect_encrypted_dir(args.keystore_dir)
    except (WalletCheckError, OSError) as exc:
        print("R20_WALLET_REFUSED: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
