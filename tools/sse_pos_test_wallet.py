#!/usr/bin/env python3
"""Create disposable SSE research EOA test-wallet encrypted keystore.

This is NOT a consensus validator BLS key. No real ETH is needed or
purchased. A faucet address generated here can be given genesis test ETH.
Private key is never printed or uploaded; passphrase is prompted twice,
not passed in CLI arguments or stored in plaintext. One non-overwriting
keystore per role; no hidden default Anvil accounts.
"""
from __future__ import annotations
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys

ROLE=re.compile(r"[a-z][a-z0-9-]{2,31}\Z")

class WalletError(ValueError):
    pass

def plan(role:str)->dict:
    if type(role) is not str or not ROLE.fullmatch(role):
        raise WalletError("invalid wallet role")
    return {"schema":"SSE_POS_TEST_WALLET_PLAN_V1",
            "role":role,"ethereumMainnet":False,
            "nativeBalanceInitiallyTestEth":0,
            "consensusValidatorKey":False,
            "privateKeyPrinted":False,
            "walletCreated":False}

def create(directory:Path,role:str,passphrase:str)->dict:
    report=plan(role)
    if (os.name!="posix" or os.geteuid()==0 or
            not directory.is_absolute() or not directory.is_dir()
            or directory.is_symlink() or
            stat.S_IMODE(directory.stat().st_mode)!=0o700 or
            directory.stat().st_uid!=os.geteuid()):
        raise WalletError("owner-only existing 0700 directory under nonroot POSIX required")
    if type(passphrase) is not str or len(passphrase)<16:
        raise WalletError("use 16+ character wallet encryption passphrase")
    path=directory/(role+".keystore.json")
    if path.exists() or path.is_symlink():
        raise WalletError("refusing to overwrite existing wallet")
    try:
        from eth_account import Account
        wallet=Account.create(os.urandom(32))
        encrypted=Account.encrypt(wallet.key,passphrase)
    except (ImportError,ValueError) as exc:
        raise WalletError("eth-account wallet encryption unavailable") from exc
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(encrypted,f,sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return {**report,"walletCreated":True,
            "address":wallet.address,
            "keystorePath":str(path),
            "encryptedWithPassphrase":True,
            "passphraseStored":False,
            "privateKeyPrinted":False,
            "testFundsCreated":False,
            "ethereumTransactionsSent":False}

def main(argv=None):
    p=argparse.ArgumentParser(description="Create SSE research EOA keystore; never prints secret")
    p.add_argument("--role",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        if a.apply:
            a1=getpass("New test-wallet encryption password (16+ chars): ")
            a2=getpass("Confirm password: ")
            if a1!=a2:
                raise WalletError("passphrases do not match")
            report=create(a.output_dir,a.role,a1)
        else:
            report=plan(a.role)
        print(json.dumps(report,sort_keys=True,indent=2))
        return 0
    except (WalletError,OSError,ValueError) as exc:
        print("SSE_POS_TEST_WALLET_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
