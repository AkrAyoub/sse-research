#!/usr/bin/env python3
"""Owner-local key unlock for the V4 agent. SOURCE-ONLY (2026-11-27), never executed.

Keystore: encrypted UTC-V3 JSON validated by the existing R237 `safe_keystore`
(nonroot, 0700 dir, 0600 file). Passphrase sources, in order:
  1. systemd credential `sse-v4-passphrase` ($CREDENTIALS_DIRECTORY), used for
     unattended restart. Tradeoff (documented to the owner): anyone with root
     on the host can read it; choose interactive unlock if that is unacceptable.
  2. interactive getpass on a TTY.
The decrypted key is held only inside an eth_account LocalAccount object.
"""
import os
from getpass import getpass
from pathlib import Path

from eth_account import Account
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore


def _passphrase():
    cred = os.environ.get("CREDENTIALS_DIRECTORY")
    if cred:
        p = Path(cred) / "sse-v4-passphrase"
        if p.is_file() and not p.is_symlink():
            return p.read_text().rstrip("\n")
    if not os.isatty(0):
        raise SystemExit("no passphrase credential and no TTY: refusing to start signer")
    return getpass("SSE V4 wallet passphrase: ")


def unlock_account(policy):
    path = Path(policy["keystore"])
    doc = safe_keystore(path)
    key = Account.decrypt(doc, _passphrase())
    acct = Account.from_key(key)
    del key
    if acct.address.lower() != policy["wallet"]:
        raise SystemExit("keystore address does not match policy wallet")
    return acct
