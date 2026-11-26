#!/usr/bin/env python3
"""Configure a verified local BLS password file for unattended Lighthouse.
Never print the password or replace the slashing protection database.
Run only with the local VC stopped.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from getpass import getpass
from Crypto.Cipher import AES
from py_ecc.bls import G2ProofOfPossession as bls

def configure(root):
    vc=root/"lighthouse"
    validators=vc/"validators"
    definitions=validators/"validator_definitions.yml"
    original=json.loads((root/"keystore.json").read_text())
    pub=original["pubkey"]
    imported=validators/("0x"+pub)/"keystore.json"
    for p in (root,vc,validators,definitions,imported,validators/"slashing_protection.sqlite"):
        if p.is_symlink() or p.stat().st_uid!=os.geteuid() or p.stat().st_mode&0o077:
            raise ValueError("unsafe owner-private validator path")
    wallet=json.loads(imported.read_text())
    if wallet["pubkey"]!=pub or wallet["crypto"]!=original["crypto"]:
        raise ValueError("imported key differs from original")
    password=getpass("Existing BLS validator password (hidden): ")
    c=wallet["crypto"]
    k=c["kdf"]["params"]
    if c["kdf"]["function"]!="pbkdf2" or k["prf"]!="hmac-sha256":
        raise ValueError("unexpected key derivation")
    d=hashlib.pbkdf2_hmac("sha256",password.encode("ascii"),bytes.fromhex(k["salt"]),k["c"],k["dklen"])
    ciphertext=bytes.fromhex(c["cipher"]["message"])
    if hashlib.sha256(d[16:]+ciphertext).hexdigest()!=c["checksum"]["message"]:
        raise ValueError("wrong BLS password")
    private=AES.new(d[:16],AES.MODE_CTR,nonce=b"",initial_value=int(c["cipher"]["params"]["iv"],16)).decrypt(ciphertext)
    if bls.SkToPk(int.from_bytes(private,"big")).hex()!=pub:
        raise ValueError("wrong BLS key")
    del private,d
    text=definitions.read_text()
    if text.count("voting_public_key:")!=1 or pub not in text or text.count("voting_keystore_path:")!=1:
        raise ValueError("unexpected validator definition; preserve")
    # Lighthouse import may store a scalar password inline. Never print it
    # or parse it as executable data. Replace only the exact single scalar
    # field in this one-key definition, using the freshly verified password.
    lines=text.splitlines()
    inline=[i for i,line in enumerate(lines) if line.lstrip().startswith("voting_keystore_password:")]
    paths=[i for i,line in enumerate(lines) if line.lstrip().startswith("voting_keystore_password_path:")]
    if paths or len(inline)>1:
        raise ValueError("existing password path or multiple fields; preserve and inspect")
    if inline:
        i=inline[0]
        scalar=lines[i].split(":",1)[1].strip()
        if not scalar or scalar.startswith(("|",">","&","*","!","[","{")):
            raise ValueError("unsupported inline password representation")
        # A YAML single-line scalar cannot have a more-indented continuation.
        indent=len(lines[i])-len(lines[i].lstrip())
        if i+1<len(lines) and lines[i+1].strip() and len(lines[i+1])-len(lines[i+1].lstrip())>indent:
            raise ValueError("unsupported multiline password representation")
        del lines[i]
    for i,line in enumerate(lines):
        if line.lstrip().startswith("voting_keystore_path:"):
            if "/data/validators/0x"+pub+"/keystore.json" not in line:
                raise ValueError("unexpected imported key path")
            indent=line[:len(line)-len(line.lstrip())]
            lines.insert(i+1,indent+"voting_keystore_password_path: /data/validator-unlock.pass")
            break
    secret=vc/"validator-unlock.pass"
    temp=vc/".validator-definitions-r358j.tmp"
    os.umask(0o077)
    with secret.open("x") as f:
        f.write(password)
        f.flush()
        os.fsync(f.fileno())
    del password
    with temp.open("x") as f:
        f.write("\n".join(lines)+"\n")
        f.flush()
        os.fsync(f.fileno())
    fd=os.open(vc,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    os.replace(temp,definitions)
    fd=os.open(validators,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    print("R358_LOCAL_BLS_UNLOCK_CONFIGURED=true")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    a=p.parse_args()
    try: configure(a.directory)
    except (ValueError,OSError,KeyError) as exc: p.exit(2,"R358_UNLOCK_REFUSED: "+str(exc)+"\n")
