#!/usr/bin/env python3
"""Create one owner-local chain31340 validator and valid public deposit data.
Requires py-ecc==8.0.0 and existing pycryptodome. No network or broadcast.
Use Lighthouse account validator import before running a signing client.
Never copy the signing key to a second live validator client.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import uuid
from getpass import getpass
from Crypto.Cipher import AES
from py_ecc.bls import G2ProofOfPossession as bls
from py_ecc.optimized_bls12_381 import curve_order
from sse_pos_validator_deposit import ssz_deposit_root
from sse_pos_r228_v2_typed_data import checked_addr

FORK=bytes.fromhex("a3400001")
AMOUNT=32000000000
def sha(data):
    return hashlib.sha256(data).digest()

def deposit_message_root(pub,wd):
    return sha(sha(sha(pub+bytes(16))+wd)+sha(AMOUNT.to_bytes(8,"little")+bytes(24)+bytes(32)))

def signing_root(pub,wd):
    domain=bytes.fromhex("03000000")+sha(FORK+bytes(28)+bytes(32))[:28]
    return sha(deposit_message_root(pub,wd)+domain)

def generate(root,withdrawal,password):
    address=checked_addr(withdrawal)
    if not root.is_absolute() or root.exists() or root.is_symlink() or not root.parent.is_dir() or root.parent.is_symlink() or root.parent.stat().st_uid!=os.geteuid() or os.geteuid()==0:
        raise ValueError("new absolute owner-local key directory required")
    # ASCII avoids EIP2335 Unicode normalization ambiguity.
    if len(password)<16 or not password.isascii() or not password.isprintable():
        raise ValueError("use at least 16 printable ASCII password characters")
    sk=secrets.randbelow(curve_order-1)+1
    pub=bls.SkToPk(sk)
    wd=b"\x01"+bytes(11)+bytes.fromhex(address[2:])
    sig=bls.Sign(sk,signing_root(pub,wd))
    if not bls.Verify(pub,signing_root(pub,wd),sig):
        raise ValueError("BLS deposit proof self-check failed")
    salt=secrets.token_bytes(32)
    iv=secrets.token_bytes(16)
    derived=hashlib.pbkdf2_hmac("sha256",password.encode("ascii"),salt,262144,32)
    ciphertext=AES.new(derived[:16],AES.MODE_CTR,nonce=b"",initial_value=int.from_bytes(iv,"big")).encrypt(sk.to_bytes(32,"big"))
    wallet={"crypto":{"kdf":{"function":"pbkdf2","params":{"dklen":32,"c":262144,"prf":"hmac-sha256","salt":salt.hex()},"message":""},
                      "checksum":{"function":"sha256","params":{},"message":sha(derived[16:]+ciphertext).hex()},
                      "cipher":{"function":"aes-128-ctr","params":{"iv":iv.hex()},"message":ciphertext.hex()}},
            "description":"SSE chain31340 only","pubkey":pub.hex(),"path":"","uuid":str(uuid.uuid4()),"version":4}
    deposit={"pubkey":pub.hex(),"withdrawal_credentials":wd.hex(),"amount":AMOUNT,"signature":sig.hex(),
             "deposit_message_root":deposit_message_root(pub,wd).hex(),"deposit_data_root":ssz_deposit_root(pub,wd,sig,AMOUNT).hex(),
             "fork_version":FORK.hex(),"network_name":"sse31340","deposit_cli_version":"sse-r358"}
    os.umask(0o077)
    root.mkdir(mode=0o700)
    for name,obj in (("keystore.json",wallet),("deposit-data.json",[deposit])):
        with (root/name).open("x") as f:
            json.dump(obj,f,indent=2)
            f.flush()
            os.fsync(f.fileno())
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return {"validatorPubkey":"0x"+pub.hex(),"withdrawalAddress":address,"depositDataFile":str(root/"deposit-data.json"),"depositValueTestEth":32,"blsProofVerified":True,"broadcast":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--withdrawal-address",required=True)
    a=p.parse_args()
    try:
        password=getpass("New encrypted BLS keystore password (min 16 ASCII chars): ")
        if password!=getpass("Repeat password: "): raise ValueError("password mismatch")
        print(json.dumps(generate(a.directory,a.withdrawal_address,password),indent=2))
    except (ValueError,OSError) as exc:
        p.exit(2,"R358_REFUSED: "+str(exc)+"\n")
if __name__=="__main__":
    main()
