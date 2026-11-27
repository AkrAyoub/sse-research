#!/usr/bin/env python3
"""R306 read-only canonical receipt and finality diagnostic; no wallet or send."""
import argparse
import json
from datetime import datetime,timezone
from sse_pos_r206_adaptive_v2_deployment_audit import rpc,verify,load
from pathlib import Path
import re

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    p.add_argument("--tx",action="append",required=True)
    a=p.parse_args()
    if any(not re.fullmatch(r"0x[0-9a-fA-F]{64}",x) for x in a.tx):
        p.error("transaction hashes required")
    proof=verify(load(a.manifest),a.rpc)
    ask=lambda method,params:rpc(a.rpc,method,params)
    latest=ask("eth_getBlockByNumber",["latest",False])
    finalized=ask("eth_getBlockByNumber",["finalized",False])
    h=int(finalized["number"],16)
    out={"chainId":31340,"observedUtc":datetime.now(timezone.utc).isoformat(),
         "latestHeight":int(latest["number"],16),"finalizedHeight":h,
         "latestTimestamp":int(latest["timestamp"],16),
         "finalizedTimestamp":int(finalized["timestamp"],16),
         "headToFinalizedSeconds":int(latest["timestamp"],16)-int(finalized["timestamp"],16),
         "transactions":[],"noSend":True}
    for tx in a.tx:
        rec=ask("eth_getTransactionReceipt",[tx])
        item={"hash":tx,"receiptPresent":rec is not None}
        if rec is not None:
            n=int(rec["blockNumber"],16)
            canonical=ask("eth_getBlockByNumber",[hex(n),False])
            match=bool(canonical and canonical["hash"].lower()==rec["blockHash"].lower() and rec["transactionHash"].lower()==tx.lower())
            item.update(block=n,canonical=match,successful=rec["status"]=="0x1",
                        finalized=match and n<=h,
                        includedTimestamp=int(canonical["timestamp"],16) if match else None)
        out["transactions"].append(item)
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
