#!/usr/bin/env python3
"""One bounded treasury top-up for each of two actual validator owners.
Run on the original treasury owner host. No retry of consumed intent.
Requires eth-account and existing owner-encrypted execution keystore.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from getpass import getpass
from eth_account import Account
from eth_utils import to_checksum_address
from sse_pos_r206_adaptive_v2_deployment_audit import rpc,GENESIS
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r232_v2_monitor_probe import write_create_only

SOURCE="0x13fb73aace8a11be2899d047635a757a224ce00b"
DEST={"4707":"0xd74a2abc5a906bafe39471cee222c48bdd62de3f","4709":"0xbbd4f07be80e1f4c40a1b470a180c0f38352beaf"}
TARGET=32010000000000000000
PRICE_CAP=1000

def quote(url,role):
    if rpc(url,"eth_chainId",[])!=hex(31340) or rpc(url,"eth_getBlockByNumber",["0x0",False])["hash"]!=GENESIS:
        raise ValueError("wrong native chain")
    dst=DEST[role]
    for addr in (SOURCE,dst):
        if rpc(url,"eth_getCode",[addr,"latest"])!="0x":
            raise ValueError("expected ordinary execution wallet")
    nonce=int(rpc(url,"eth_getTransactionCount",[SOURCE,"latest"]),16)
    if nonce!=int(rpc(url,"eth_getTransactionCount",[SOURCE,"pending"]),16):
        raise ValueError("treasury has pending transaction")
    balance=int(rpc(url,"eth_getBalance",[dst,"latest"]),16)
    value=max(0,TARGET-balance)
    price=int(rpc(url,"eth_gasPrice",[]),16)
    if not 0<price<=PRICE_CAP:
        raise ValueError("gas price exceeds cap")
    if value and (int(rpc(url,"eth_estimateGas",[{"from":SOURCE,"to":dst,"value":hex(value),"data":"0x"}]),16)!=21000 or int(rpc(url,"eth_getBalance",[SOURCE,"latest"]),16)<value+21000*price):
        raise ValueError("funding gas or balance check failed")
    return {"chainId":31340,"from":SOURCE,"to":dst,"nonce":nonce,"valueWei":value,"gasPriceWei":price,"gas":21000,"targetBalanceWei":TARGET,"recipientBalanceWei":balance}

def send(a):
    if os.geteuid()==0 or not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ValueError("nonroot owner terminal required")
    root=a.keystore.parent
    marker=root/(".r358-validator-"+a.role+"-funding.json")
    if marker.exists() or marker.is_symlink():
        raise ValueError("funding intent already exists; reconcile first")
    q=quote(a.rpc,a.role)
    print(json.dumps(q,indent=2),flush=True)
    if not q["valueWei"]: return
    if input("Type FUND-VALIDATOR-"+a.role+" to authorize exact top-up: ")!="FUND-VALIDATOR-"+a.role:
        raise ValueError("not authorized")
    key=Account.decrypt(safe_keystore(a.keystore),getpass("Existing treasury execution wallet password: "))
    try:
        if Account.from_key(key).address.lower()!=SOURCE or quote(a.rpc,a.role)!=q:
            raise ValueError("wrong signer or changed funding conditions")
        signed=Account.sign_transaction({"chainId":31340,"nonce":q["nonce"],"to":to_checksum_address(q["to"]),"value":q["valueWei"],"gas":21000,"gasPrice":q["gasPriceWei"],"data":b""},key)
    finally:
        del key
    digest="0x"+bytes(signed.hash).hex()
    write_create_only(marker,{**q,"transactionHash":digest})
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    print("R358_FUNDING_INTENT_TX="+digest,flush=True)
    ack=rpc(a.rpc,"eth_sendRawTransaction",["0x"+bytes(signed.raw_transaction).hex()])
    if ack.lower()!=digest: raise ValueError("acknowledgement mismatch; reconcile")
    print("R358_FUNDING_BROADCAST_ACKNOWLEDGED="+digest,flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role",choices=sorted(DEST),required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:18545")
    p.add_argument("--send",action="store_true")
    a=p.parse_args()
    try:
        if a.send: send(a)
        else: print(json.dumps(quote(a.rpc,a.role),indent=2))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(2,"R358_FUNDING_REFUSED: "+str(exc)+"\n")
if __name__=="__main__": main()
