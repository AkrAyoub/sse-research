#!/usr/bin/env python3
"""SSE's own PoS chain: independent validator deposit-data verifier.

Only PUBLIC BLS pubkeys/withdrawal credentials/signature/deposit roots
are read. The BLS SECRET KEY is generated independently by a validator
client or consensus-deposit CLI on the participant's machine and NEVER
sent to SSE operators. This program cannot approve/deny a validator:
the underlying Ethereum PoS deposit contract and Beacon activation
rules do that. No real ETH, Tailscale or administrator invite involved.

Output is ABI calldata for Ethereum's standard DepositContract.deposit
(bytes pubkey, bytes withdrawal_credentials, bytes signature,
bytes32 deposit_data_root). A *separate*, explicitly authorized
transaction from the participant must send 32 worthless test ETH
on chain31339. We verify the exact SSZ DepositData root but do not
perform BLS proof-of-possession verification; the PoS consensus client
must enforce its own deposit validity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from Crypto.Hash import keccak
from eth_abi import encode

CHAIN=31339
VALUE_WEI=32*10**18
GWEI=32_000_000_000
CONTRACT="0x00000000219ab540356cBB839Cbe05303d7705Fa"
HEX=re.compile(r"[0-9a-fA-F]+\Z")
FORK=re.compile(r"0x[0-9a-fA-F]{8}\Z")

class DepositError(ValueError):
    pass


def _bytes(record:dict,key:str,length:int)->bytes:
    value=record.get(key)
    if (type(value) is not str or len(value)!=2*length
            or not HEX.fullmatch(value)):
        raise DepositError(key+" must be "+str(length)+" bytes of unprefixed hex")
    return bytes.fromhex(value)


def ssz_deposit_root(pubkey:bytes,withdrawal:bytes,signature:bytes,amount_gwei:int)->bytes:
    if (len(pubkey)!=48 or len(withdrawal)!=32 or len(signature)!=96
            or type(amount_gwei) is not int
            or not 0<=amount_gwei<2**64):
        raise DepositError("invalid SSZ DepositData field lengths/amount")
    sha=lambda x:hashlib.sha256(x).digest()
    pubroot=sha(pubkey+b"\x00"*16)
    sigroot=sha(sha(signature[:64])+sha(signature[64:]+b"\x00"*32))
    amountroot=amount_gwei.to_bytes(8,"little")+b"\x00"*24
    return sha(sha(pubroot+withdrawal)+sha(amountroot+sigroot))


def validate(record:dict,*,expected_fork:str)->dict:
    if (type(record) is not dict
            or type(expected_fork) is not str or not FORK.fullmatch(expected_fork)):
        raise DepositError("valid deposit JSON and pinned network fork version required")
    if (type(record.get("fork_version")) is not str
            or record["fork_version"].lower()!=expected_fork[2:].lower()):
        raise DepositError("deposit signed for different consensus fork")
    amount=record.get("amount")
    if type(amount) is not int or amount!=GWEI:
        raise DepositError("exact 32-test-ETH PoS deposit amount required")
    pub=_bytes(record,"pubkey",48)
    if pub==b"\x00"*48:
        raise DepositError("zero BLS validator key")
    wd=_bytes(record,"withdrawal_credentials",32)
    if wd[0] not in (0,1,2):
        raise DepositError("invalid withdrawal credential version")
    sig=_bytes(record,"signature",96)
    root=_bytes(record,"deposit_data_root",32)
    if root!=ssz_deposit_root(pub,wd,sig,amount):
        raise DepositError("deposit_data_root SSZ mismatch")
    # The cryptographic BLS signature itself is NOT verified here.
    # The Beacon consensus layer decides eligibility and activation.
    selector=keccak.new(digest_bits=256)
    selector.update(b"deposit(bytes,bytes,bytes,bytes32)")
    calldata="0x"+selector.digest()[:4].hex()+encode(
        ["bytes","bytes","bytes","bytes32"],[pub,wd,sig,root]
    ).hex()
    return {
        "schema":"SSE_OWN_POS_VALIDATOR_DEPOSIT_PLAN_V1",
        "chainId":CHAIN,"realEthRequired":False,
        "depositValueTestWei":VALUE_WEI,
        "depositValueTestEth":32,
        "depositContract":CONTRACT,
        "validatorBlsPubkey":"0x"+pub.hex(),
        "withdrawalCredentials":"0x"+wd.hex(),
        "depositDataRoot":"0x"+root.hex(),
        "calldata":calldata,
        "calldataSha256":hashlib.sha256(bytes.fromhex(calldata[2:])).hexdigest(),
        "sszRootVerified":True,
        "cryptographicBlsProofVerified":False,
        "validatorActivationVerified":False,
        "validatorAcceptedBySSEAdministrator":False,
        "stakingTransactionBroadcast":False,
        "walletPrivateKeyRead":False,
        "testEthEconomicallySybilResistant":False,
    }


def read_deposit(path:Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>32768:
        raise DepositError("deposit-data JSON missing/oversized/symlinked")
    obj=json.loads(path.read_text("utf-8"))
    if type(obj) is list and len(obj)==1:
        obj=obj[0]
    if type(obj) is not dict:
        raise DepositError("provide exactly one deposit-data record")
    return obj


def write_once(path:Path,record:dict):
    if (not path.is_absolute() or not path.parent.is_dir()
            or path.parent.is_symlink() or path.exists() or path.is_symlink()):
        raise DepositError("calldata evidence output must be new absolute file")
    data=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def main(argv=None):
    p=argparse.ArgumentParser(description="Self-service 32-test-ETH PoS validator deposit, no SSE approval")
    p.add_argument("--deposit-data",type=Path,required=True)
    p.add_argument("--fork-version",required=True,
                   help="0x-prefixed fork version read from our OWN Beacon genesis spec")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        checked=validate(read_deposit(a.deposit_data),expected_fork=a.fork_version)
        write_once(a.output,checked)
        # Do NOT dump call data into terminal: keep one file for actual
        # independent participant's eventual explicit transaction.
        brief={k:v for k,v in checked.items() if k!="calldata"}
        brief["calldataFile"]=str(a.output)
        print(json.dumps(brief,sort_keys=True,indent=2))
        return 0
    except (DepositError,OSError,ValueError,TypeError) as exc:
        print("SSE_POS_DEPOSIT_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
