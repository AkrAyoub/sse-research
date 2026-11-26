#!/usr/bin/env python3
"""R358d: one native chain31340 deposit with durable create-only intent.
Never automatically retry an uncertain broadcast. Local duplicate protection,
not a global guarantee against another operator depositing the same key.
"""
import argparse
import json
import os
from pathlib import Path
from getpass import getpass
import sys
from eth_account import Account
from sse_pos_r358_validator_deposit import prepare,read_deposit
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r206_adaptive_v2_deployment_audit import rpc
from sse_pos_r232_v2_monitor_probe import write_create_only

def send(root,url,sender,keystore,max_fee):
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ValueError("owner terminal required")
    if root.is_symlink() or root.stat().st_uid!=os.geteuid() or root.stat().st_mode & 0o077:
        raise ValueError("private validator directory required")
    journal=root/"deposit-intent.json"
    if journal.exists() or journal.is_symlink():
        raise ValueError("existing deposit intent: reconcile, never retry")
    record=read_deposit(root/"deposit-data.json")
    plan=prepare(record,url,sender)
    if not plan["readyForOwnerDeposit"]:
        raise ValueError("insufficient staking balance")
    sender=plan["sender"]
    if sender!=plan["withdrawalAddress"]:
        raise ValueError("this self-funded path requires owner withdrawal EOA")
    nonce=int(rpc(url,"eth_getTransactionCount",[sender,"pending"]),16)
    if nonce!=int(rpc(url,"eth_getTransactionCount",[sender,"latest"]),16):
        raise ValueError("pending wallet transaction; reconcile first")
    gas=(plan["gasEstimate"]*120+99)//100
    price=int(plan["gasPriceWei"])
    if price<=0 or not 0<gas*price<=max_fee or int(plan["senderBalanceWei"])<int(plan["depositValueTestWei"])+gas*price:
        raise ValueError("deposit fee or balance outside approved bound")
    tx={"chainId":31340,"nonce":nonce,"to":plan["depositContract"],
        "value":int(plan["depositValueTestWei"]),"gas":gas,"gasPrice":price,"data":plan["calldata"]}
    print(json.dumps({"chainId":31340,"sender":sender,"validatorPubkey":plan["validatorBlsPubkey"],
                      "withdrawalAddress":plan["withdrawalAddress"],"valueWei":tx["value"],
                      "maximumFeeWei":gas*price,"nonce":nonce},indent=2),flush=True)
    if input("Type STAKE-32-TEST-ETH to authorize one deposit: ")!="STAKE-32-TEST-ETH":
        raise ValueError("not authorized")
    key=Account.decrypt(safe_keystore(keystore),getpass("Local execution wallet password: "))
    try:
        if Account.from_key(key).address.lower()!=sender:
            raise ValueError("wrong execution wallet")
        fresh=prepare(record,url,sender)
        if not fresh["readyForOwnerDeposit"] or fresh["gasEstimate"]>gas or int(fresh["gasPriceWei"])>price or int(fresh["senderBalanceWei"])<tx["value"]+gas*price:
            raise ValueError("deposit conditions changed")
        for tag in ("pending","latest"):
            if int(rpc(url,"eth_getTransactionCount",[sender,tag]),16)!=nonce:
                raise ValueError("wallet nonce changed")
        signed=Account.sign_transaction(tx,key)
    finally:
        del key
    digest="0x"+bytes(signed.hash).hex()
    write_create_only(journal,{"chainId":31340,"validatorPubkey":plan["validatorBlsPubkey"],
        "sender":sender,"nonce":nonce,"transactionHash":digest,"depositDataRoot":plan["depositDataRoot"],
        "valueWei":tx["value"],"maximumFeeWei":gas*price})
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    result=rpc(url,"eth_sendRawTransaction",["0x"+bytes(signed.raw_transaction).hex()])
    if result.lower()!=digest: raise ValueError("unexpected acknowledgement; reconcile journal")
    print(json.dumps({"transactionHash":digest,"broadcastAcknowledged":True,"activationVerified":False},indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--sender",required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--max-fee-wei",type=int,default=10**15)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    try: send(a.directory,a.rpc,a.sender,a.keystore,a.max_fee_wei)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(2,"R358_STAKE_REFUSED: "+str(exc)+"\n")
if __name__=="__main__": main()
