#!/usr/bin/env python3
"""R351 public transaction intent journal. Read-only reconciliation; no resend.

An absent receipt is UNKNOWN, never permission to reuse a nonce or resend.
Only canonical finalized receipts are terminal. The caller must persist the
signed transaction hash before broadcast and serialize use of each wallet.
"""
import argparse
import json
import os
from pathlib import Path
import re
from sse_pos_r206_adaptive_v2_deployment_audit import load, rpc, verify
from sse_pos_r350_v2_canonical_lease_snapshot import block_identity
from sse_pos_r232_v2_monitor_probe import write_create_only

HASH=re.compile(r"0x[0-9a-f]{64}")
ADDR=re.compile(r"0x[0-9a-f]{40}")

def record_intent(root,manifest,sender,nonce,txhash,action,target,calldata,value):
    sender=sender.lower()
    txhash=txhash.lower()
    target=target.lower()
    if not ADDR.fullmatch(sender) or not ADDR.fullmatch(target) or not HASH.fullmatch(txhash):
        raise ValueError("invalid public transaction identity")
    if type(nonce) is not int or nonce<0 or type(value) is not int or value<0:
        raise ValueError("invalid nonce or value")
    if not isinstance(action,str) or not action or len(action)>64:
        raise ValueError("invalid action")
    if not isinstance(calldata,str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+",calldata):
        raise ValueError("invalid public calldata")
    root=Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("owner-private absolute journal directory required")
    if root.stat().st_uid!=os.geteuid() or root.stat().st_mode & 0o077:
        raise ValueError("journal directory not owner private")
    entry={"schema":"SSE_R351_PUBLIC_TX_INTENT_V1","chainId":31340,
           "market":manifest["market"]["address"].lower(),"sender":sender,
           "nonce":nonce,"transactionHash":txhash,"action":action,"target":target,
           "calldata":calldata.lower(),"valueWei":value}
    path=root / (sender+"-"+str(nonce)+".json")
    write_create_only(path,entry)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path

def reconcile(entry,manifest,url,*,transport=rpc):
    verify(manifest,url,transport=transport)
    if entry.get("schema")!="SSE_R351_PUBLIC_TX_INTENT_V1" or entry.get("chainId")!=31340 or entry.get("market")!=manifest["market"]["address"].lower():
        raise ValueError("wrong journal scope")
    h=entry["transactionHash"]
    sender=entry["sender"]
    nonce=entry["nonce"]
    if not HASH.fullmatch(h) or not ADDR.fullmatch(sender) or type(nonce) is not int or nonce<0:
        raise ValueError("invalid journal identity")
    ask=lambda m,p:transport(url,m,p)
    receipt=ask("eth_getTransactionReceipt",[h])
    result={"transactionHash":h,"sender":sender,"nonce":nonce,
            "automaticResendAuthorized":False,"terminal":False}
    if receipt is None:
        tx=ask("eth_getTransactionByHash",[h])
        result["status"]="KNOWN_UNCONFIRMED" if tx is not None else "UNKNOWN_NO_RECEIPT"
        result["pendingNonce"]=int(ask("eth_getTransactionCount",[sender,"pending"]),16)
        return result
    if receipt["transactionHash"].lower()!=h or receipt["from"].lower()!=sender or receipt["to"].lower()!=entry["target"]:
        raise ValueError("receipt identity mismatch")
    tx=ask("eth_getTransactionByHash",[h])
    if (not tx or tx["hash"].lower()!=h or tx["from"].lower()!=sender
        or tx["to"].lower()!=entry["target"] or int(tx["nonce"],16)!=nonce
        or tx["input"].lower()!=entry["calldata"] or int(tx["value"],16)!=entry["valueWei"]):
        raise ValueError("transaction does not match journal")
    n=int(receipt["blockNumber"],16)
    anchor=(n,receipt["blockHash"].lower())
    if block_identity(ask("eth_getBlockByNumber",[hex(n),False]))!=anchor:
        result["status"]="NONCANONICAL_RECEIPT"
        return result
    final,_=block_identity(ask("eth_getBlockByNumber",["finalized",False]))
    if block_identity(ask("eth_getBlockByNumber",[hex(n),False]))!=anchor:
        result["status"]="NONCANONICAL_RECEIPT"
        return result
    status=int(receipt["status"],16)
    if status not in (0,1):
        raise ValueError("unknown receipt status")
    result.update(includedHeight=n,includedHash=anchor[1],finalizedHeight=final,
                  terminal=final>=n,status=("FINALIZED_" if final>=n else "CANONICAL_")+("SUCCESS" if status else "REVERTED"))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--intent",type=Path,required=True)
    a=p.parse_args()
    try:
        if a.intent.is_symlink() or not a.intent.is_file() or a.intent.stat().st_size>65536:
            raise ValueError("bounded regular journal entry required")
        print(json.dumps(reconcile(json.loads(a.intent.read_text()),load(a.manifest),a.rpc),indent=2,sort_keys=True))
    except (ValueError,OSError,TypeError,KeyError) as exc:
        p.exit(2,"R351_REFUSED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
