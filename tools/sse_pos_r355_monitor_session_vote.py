#!/usr/bin/env python3
"""R355a: one owner-approved monitoring session with timely evidence-bound vote.

Uses existing finalized R349 sampling and R353 archive validation. Owner
authorizes ONE conditional Success report, within a fixed fee cap, for a
specific lease/epoch/monitor. No automatic failure report, retry, settlement,
or withdrawal. Password stays in process memory only during this session.
"""
import argparse
from getpass import getpass
import json
from pathlib import Path
import sys
import time

from sse_pos_r206_adaptive_v2_deployment_audit import load,rpc
from sse_pos_r229_v2_finalized_lease_snapshot import inspect
from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical
from sse_pos_r349_v2_monitor_sample_session import run
from sse_pos_r353_monitor_evidence_vote_plan import plan as evidence_plan
from sse_pos_r242_v2_owner_local_send import readonly_quote,submit_once,AUTHORIZE
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore

CONSENT="AUTHORIZE-ONE-CONDITIONAL-SLA-SUCCESS-VOTE"

def execute(a):
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ValueError("owner-interactive terminal required")
    if not 0<a.max_total_wei<=10**12:
        raise ValueError("session gas budget must be positive and <= 10**12 wei")
    manifest=load(a.manifest)
    profile=json.loads(a.profile.read_text())
    policy=json.loads(a.policy.read_text())
    snapshot=inspect(manifest,a.rpc,a.lease_id,a.epoch_id)
    from sse_pos_r232_v2_monitor_probe import prepared_monitor
    from sse_pos_r233_public_v2_compute_terms import resource_hash,policy_hash
    ctx=prepared_monitor(snapshot,a.monitor,profile["origin"],rpc_url=a.rpc)
    current=inspect_canonical(manifest,a.rpc,a.lease_id,a.epoch_id)
    ep=current["epoch"]["ledger"]
    if not ep["responseAuthenticated"] or ep["monitoringSealed"]:
        raise ValueError("no authenticated open epoch")
    if snapshot["lease"]["profileHash"]!=resource_hash(profile) or snapshot["lease"]["policyHash"]!=policy_hash(policy,profile):
        raise ValueError("committed SLA terms mismatch")
    if not policy["minProbeCount"]<=a.count<=120:
        raise ValueError("invalid sample count")
    if time.time()+(a.count-1)*policy["probeIntervalMs"]/1000+90>=ep["monitoringClose"]:
        raise ValueError("insufficient time for samples and vote")
    monitor=ctx["monitor"]
    from sse_pos_r229_v2_finalized_lease_snapshot import query,decode_struct
    voted=decode_struct(query(rpc,a.rpc,current["ledger"],"voted(uint256,uint256,address)",(a.lease_id,a.epoch_id,int(monitor,16)),current["observedExecutionHeight"]),(("voted","bool"),))["voted"]
    if voted:
        raise ValueError("monitor already voted")
    print(json.dumps({"chainId":31340,"market":snapshot["market"],"ledger":snapshot["ledger"],
        "leaseId":a.lease_id,"epochId":a.epoch_id,"monitor":monitor,
        "profileHash":snapshot["lease"]["profileHash"],"policyHash":snapshot["lease"]["policyHash"],
        "requestHash":ctx["requestHash"],"responseHash":ep["responseHash"],
        "sampleCount":a.count,"maximumTransactionSpendWei":a.max_total_wei,
        "onlyPermittedOutcome":1,"monitoringClose":ep["monitoringClose"],
        "automaticFailureVote":False,"physicalSlaTruthVerified":False},indent=2),flush=True)
    if input("Type "+CONSENT+" to authorize this bounded conditional report: ")!=CONSENT:
        raise ValueError("session not authorized")
    from eth_account import Account
    wallet=safe_keystore(a.keystore)
    password=getpass("Local encrypted application wallet password (held only for this session): ")
    try:
        key=Account.decrypt(wallet,password)
        try:
            if Account.from_key(key).address.lower()!=monitor:
                raise ValueError("wrong application wallet")
        finally:
            del key
        run(a)
        prepared=evidence_plan(manifest,a.rpc,a.output,profile,policy,a.lease_id,a.epoch_id)
        if prepared["monitor"]!=monitor or prepared["params"]["outcome"]!=1:
            raise ValueError("evidence outside approved scope")
        tx,offer=readonly_quote(manifest,a.rpc,"vote","monitor",prepared["params"],monitor,a.max_total_wei)
        result=submit_once(tx,offer,manifest,a.rpc,a.keystore,
                           confirm=lambda _: AUTHORIZE,get_password=lambda _: password,
                           journal_dir=a.journal_dir)
        print(json.dumps(result,indent=2,sort_keys=True),flush=True)
        return result
    finally:
        del password

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","profile","policy","tls-cert","output","keystore"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--rpc",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"),required=True)
    p.add_argument("--lease-id",type=int,required=True)
    p.add_argument("--epoch-id",type=int,required=True)
    p.add_argument("--monitor",required=True)
    p.add_argument("--tls-fingerprint",required=True)
    p.add_argument("--count",type=int,required=True)
    p.add_argument("--max-total-wei",type=int,required=True)
    p.add_argument("--journal-dir",type=Path,default=Path.home()/".local/share/sse-transaction-journal")
    try:
        execute(p.parse_args())
    except (ValueError,TypeError,KeyError,OSError) as exc:
        p.exit(2,"R355_REFUSED: "+str(exc)+"\n")
if __name__=="__main__":
    main()
