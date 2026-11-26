#!/usr/bin/env python3
"""R377 bounded owner-local one-epoch runner. No remote signing interface."""
import argparse,json,sys,time,secrets,contextlib,io
from pathlib import Path
from getpass import getpass
from eth_account import Account
from sse_pos_r362_v3_market_operations import MARKET,LEDGER,verify,call,require,execute
from sse_pos_r367_v3_compute_wire import snapshot,check_proposal
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r206_adaptive_v2_deployment_audit import rpc
import sse_pos_r370_v3_monitor_session as monitor
import sse_pos_r371_v3_consumer_response as consumer
def invoke(fn,args):
    old=sys.argv
    sys.argv=[old[0]]+args
    try:fn()
    finally:sys.argv=old
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--role",choices=("consumer","monitor"),required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--epoch",type=int,required=True)
    p.add_argument("--address",required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--profile",type=Path,required=True)
    p.add_argument("--proposal",type=Path)
    p.add_argument("--cert",type=Path,required=True)
    p.add_argument("--fingerprint",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--admission-only",action="store_true",help="Consumer fault experiment: open and settle without claiming response authentication")
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    from sse_pos_r366_v3_scientific_proposal import proposal
    d=proposal(json.loads(a.profile.read_text()))
    s=snapshot(ask,a.lease,a.epoch);check_proposal(d,s)
    require(not s["exists"] and s["nextEpoch"]==a.epoch,"epoch already opened or wrong next epoch")
    require(sys.stdin.isatty() and sys.stderr.isatty(),"owner terminal required")
    require(not a.admission_only or a.role=="consumer","admission-only requires consumer")
    if a.role=="consumer":
        require(s["consumer"].lower()==a.address.lower() and a.proposal is not None,"wrong consumer")
        require(json.loads(a.proposal.read_text())==d,"proposal mismatch")
        allowed={"start","finalize"} if a.admission_only else {"start","authenticate","finalize"}
    else:
        require(call(ask,LEDGER,"confirmedMonitor(uint256,address)",("uint256","address"),(a.lease,a.address),("bool",))[0],"monitor not confirmed")
        allowed={"vote"}
    print(json.dumps({"chainId":31340,"market":MARKET,"lease":a.lease,"epoch":a.epoch,"role":a.role,"actions":sorted(allowed),"maxGasSpendWei":len(allowed)*10**10,"valueWei":0,"sessionSeconds":1200}),flush=True)
    require(input("Type ENABLE-ONE-V3-EPOCH: ")=="ENABLE-ONE-V3-EPOCH","not authorized")
    account=Account.from_key(Account.decrypt(safe_keystore(a.keystore),getpass("Application wallet password: ")))
    require(account.address.lower()==a.address.lower(),"wrong wallet")
    expiry=time.monotonic()+1200
    def send(action,params):
        require(time.monotonic()<expiry and action in allowed and params["leaseId"]==a.lease and params.get("epochId",a.epoch)==a.epoch,"session scope exceeded")
        allowed.remove(action)
        return execute(ask,action,params,a.address,10**10,send=True,account=account)
    common=["--lease",str(a.lease),"--epoch",str(a.epoch),"--cert",str(a.cert),"--fingerprint",a.fingerprint,"--output",str(a.output),"--rpc",a.rpc]
    if a.role=="monitor":
        invoke(monitor.main,common+["--profile",str(a.profile),"--monitor",a.address])
        e=json.loads(a.output.read_text())
        if not e["evidence"]["qualifiedConditionalSuccess"]:
            print("SESSION_ABSTAINED");return
        send("vote",dict(leaseId=a.lease,epochId=a.epoch,outcome=1,evidenceHash=e["evidenceHash"]))
    else:
        fresh=snapshot(ask,a.lease,a.epoch)
        require(not fresh["exists"] and fresh["nextEpoch"]==a.epoch,"epoch changed")
        send("start",dict(leaseId=a.lease,requestHash="0x"+secrets.token_hex(32)))
        if a.admission_only:
            print("ADMISSION_ONLY_EXPERIMENT_NO_RESPONSE_AUTHENTICATION",flush=True)
        else:
            invoke(consumer.main,common+["--proposal",str(a.proposal)])
            send("authenticate",json.loads(a.output.read_text())["authenticateParams"])
        while True:
            s=snapshot(ask,a.lease,a.epoch)
            if s["accounted"]:break
            require(time.monotonic()<expiry,"session expired before settlement")
            if s["headTimestamp"]>s["monitoringClose"]:
                send("finalize",dict(leaseId=a.lease,epochId=a.epoch));break
            print("MONITORING_REMAINING",s["monitoringClose"]-s["headTimestamp"],"SUCCESS_VOTES",s["successVotes"],flush=True)
            time.sleep(5)
    print("V3_EPOCH_SESSION_COMPLETE=true",flush=True)
if __name__=="__main__":main()
