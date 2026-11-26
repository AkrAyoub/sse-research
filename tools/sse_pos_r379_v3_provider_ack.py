#!/usr/bin/env python3
"""R379 explicit owner admission acknowledgment for a real active V3 request.
Signs ProviderAck only for the actual lease provider; submits via journaled engine.
Acknowledgment does not assert physical delivery time or successful execution.
"""
import argparse,json,sys
from pathlib import Path
from getpass import getpass
from eth_account import Account
from sse_pos_r362_v3_market_operations import verify,require,execute
from sse_pos_r367_v3_compute_wire import snapshot,check_proposal,typed
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r206_adaptive_v2_deployment_audit import rpc
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proposal",type=Path,required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--epoch",type=int,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    d=json.loads(a.proposal.read_text())
    s=snapshot(ask,a.lease,a.epoch);check_proposal(d,s)
    require(s["exists"] and not s["acknowledged"] and s["headTimestamp"]<s["evidenceClose"],"acknowledgment not eligible")
    require(sys.stdin.isatty() and sys.stderr.isatty(),"owner terminal required")
    print(json.dumps({"leaseId":a.lease,"epochId":a.epoch,"requestHash":s["requestHash"],"provider":s["provider"],"meaning":"provider admits this actual request; not proof of performance","maxGasWei":10**10}),flush=True)
    require(input("Type ACKNOWLEDGE-ACTUAL-V3-REQUEST: ")=="ACKNOWLEDGE-ACTUAL-V3-REQUEST","not authorized")
    account=Account.from_key(Account.decrypt(safe_keystore(a.keystore),getpass("Provider wallet password: ")))
    require(account.address.lower()==s["provider"].lower(),"wrong provider")
    fresh=snapshot(ask,a.lease,a.epoch);check_proposal(d,fresh)
    require(fresh["requestHash"]==s["requestHash"] and not fresh["acknowledged"] and fresh["headTimestamp"]<fresh["evidenceClose"],"request changed or expired")
    sig="0x"+bytes(account.sign_message(typed(fresh,"ProviderAck")).signature).hex()
    execute(ask,"acknowledge",{"leaseId":a.lease,"epochId":a.epoch,"signature":sig},account.address,10**10,send=True,account=account)
    require(snapshot(ask,a.lease,a.epoch)["acknowledged"],"acknowledgment not observed")
    print("V3_PROVIDER_ACKNOWLEDGMENT_VERIFIED=true")
if __name__=="__main__":main()
