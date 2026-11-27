#!/usr/bin/env python3
"""R370 V3 live monitor sampling. No fabricated negative votes.
Collect actual pinned-TLS responses, validate V3 signatures and chain context,
archive raw evidence, and emit a success vote proposal only when qualified.
"""
import argparse, hashlib,json,time,sys
from pathlib import Path
from urllib.request import Request,ProxyHandler,HTTPSHandler,build_opener
from eth_utils import keccak
from sse_pos_r362_v3_market_operations import MARKET,LEDGER,verify,call,require
from sse_pos_r367_v3_compute_wire import snapshot,check_proposal,validate_reply
from sse_pos_r366_v3_scientific_proposal import proposal
from sse_pos_r233_public_v2_compute_terms import canonical
from sse_pos_r232_v2_monitor_probe import NoRedirect,pinned_tls_context,write_create_only
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",type=Path,required=True)
    p.add_argument("--cert",type=Path,required=True)
    p.add_argument("--fingerprint",required=True)
    p.add_argument("--monitor",required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--epoch",type=int,default=0)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    d=proposal(json.loads(a.profile.read_text()))
    policy=d["policy"]
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    tls=pinned_tls_context(a.cert,a.fingerprint)
    opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=tls))
    end=time.monotonic()+900
    while True:
        s=snapshot(ask,a.lease,a.epoch);check_proposal(d,s)
        require(call(ask,LEDGER,"confirmedMonitor(uint256,address)",("uint256","address"),(a.lease,a.monitor),("bool",))[0],"monitor seat not confirmed")
        if s["exists"]:break
        require(time.monotonic()<end,"epoch startup wait expired")
        print("WAITING_FOR_EPOCH",flush=True);time.sleep(5)
    anchor=s["block"];anchor_hash=s["blockHash"]
    challenge={k:s[k] for k in ("leaseId","epochId","requestHash")}
    records=[]
    for i in range(policy["minProbeCount"]):
        started=time.monotonic()
        fresh=snapshot(ask,a.lease,a.epoch)
        require(fresh["requestHash"]==s["requestHash"] and not fresh["sealed"] and fresh["headTimestamp"]<fresh["monitoringClose"],"monitoring window ended or epoch changed")
        q=Request(d["profile"]["origin"]+"/v3/challenge",data=canonical(challenge),headers={"Content-Type":"application/json"},method="POST")
        rec={"sample":i,"utcUnixNs":time.time_ns(),"chainBlock":fresh["block"],"chainBlockHash":fresh["blockHash"]}
        http_started=time.monotonic()
        try:
            with opener.open(q,timeout=6) as res:
                raw=res.read(8193)
                elapsed=round((time.monotonic()-http_started)*1000)
                require(res.status==200 and len(raw)<=8192,"invalid HTTP reply")
            reply=json.loads(raw)
            h=validate_reply(reply,fresh)
            rec.update(elapsedMs=elapsed,reply=reply,responseHash=h,bodySha256=hashlib.sha256(raw).hexdigest(),correct=True)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            rec.update(correct=False,elapsedMs=round((time.monotonic()-http_started)*1000),error=type(exc).__name__)
        records.append(rec)
        print("SAMPLE",i,rec["correct"],rec["elapsedMs"],flush=True)
        if i+1<policy["minProbeCount"]:
            time.sleep(max(0,policy["probeIntervalMs"]/1000-(time.monotonic()-started)))
    final=snapshot(ask,a.lease,a.epoch)
    # Preserve observations while authentication is still eligible.
    # Do not turn absence of a transaction into negative service evidence.
    wait_end=time.monotonic()+240
    while (not final["authenticated"] and not final["sealed"]
           and final["requestHash"]==s["requestHash"]
           and final["headTimestamp"]<=final["responseDeadline"]
           and time.monotonic()<wait_end):
        print("WAITING_FOR_RESPONSE_AUTHENTICATION",flush=True)
        time.sleep(3)
        final=snapshot(ask,a.lease,a.epoch)
    require(ask("eth_getBlockByNumber",[anchor,False])["hash"]==anchor_hash,"observation anchor reorganized")
    qualified=(final["authenticated"] and not final["sealed"] and final["requestHash"]==s["requestHash"] and final["headTimestamp"]<final["monitoringClose"] and all(r["correct"] and r["elapsedMs"]<=policy["maxObservedLatencyMs"] and r.get("responseHash")==final["responseHash"] for r in records))
    evidence={"schema":"SSE_V3_REAL_MONITOR_SESSION_V1","chainId":31340,"market":MARKET,"ledger":LEDGER,"monitor":a.monitor.lower(),"challenge":challenge,"policyHash":s["policyHash"],"records":records,"qualifiedConditionalSuccess":qualified,"physicalSlaTruthProved":False}
    h="0x"+keccak(b"SSE_V3_MONITOR_EVIDENCE_V1\x00"+canonical(evidence)).hex()
    write_create_only(a.output,{"evidence":evidence,"evidenceHash":h})
    if qualified:print("VOTE_PARAMS="+json.dumps({"leaseId":a.lease,"epochId":a.epoch,"outcome":1,"evidenceHash":h}),flush=True)
    else:print("INCONCLUSIVE_NO_VOTE",flush=True)
if __name__=="__main__":main()
