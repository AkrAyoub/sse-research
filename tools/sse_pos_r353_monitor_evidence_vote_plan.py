#!/usr/bin/env python3
"""R353a: independently revalidate R349 archives; prepare a conditional vote.
No signing, no broadcast, no retrospective vote after close. Local timing
and operator honesty are assumptions, not cryptographically proven facts.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from sse_challenge import keccak256
from sse_pos_r349_v2_monitor_sample_session import canonical,evaluate
from sse_pos_r231_v2_compute_wire import validate_signed_reply
from sse_pos_r232_v2_monitor_probe import prepared_monitor,_unique_pairs
from sse_pos_r233_public_v2_compute_terms import resource_hash,policy_hash
from sse_pos_r229_v2_finalized_lease_snapshot import inspect,query,decode_struct
from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical
from sse_pos_r206_adaptive_v2_deployment_audit import load,rpc

def read(path,limit=65536):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
        raise ValueError("missing or unsafe evidence file")
    return path.read_bytes()

def document(path):
    return json.loads(read(path),object_pairs_hook=_unique_pairs)

def audit(root,profile,policy,snapshot):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe archive directory")
    report=document(root/"summary.json")
    commitment=report.pop("evidenceHash")
    if commitment!="0x"+keccak256(b"SSE_R349_SAMPLE_SESSION_V1\x00"+canonical(report)).hex():
        raise ValueError("summary commitment mismatch")
    ep=snapshot["epoch"]["ledger"]
    lease=snapshot["lease"]
    ctx=prepared_monitor(snapshot,report["monitor"],profile["origin"])
    expected={"schema":"SSE_R349_FINALIZED_SAMPLE_SESSION_V1","chainId":31340,
              "market":snapshot["market"],"leaseId":snapshot["leaseId"],
              "epochId":snapshot["epochId"],"requestHash":ctx["requestHash"],
              "responseHash":ep["responseHash"],"profileHash":resource_hash(profile),
              "policyHash":policy_hash(policy,profile)}
    if any(report.get(k)!=v for k,v in expected.items()) or not ep["responseAuthenticated"] or expected["profileHash"]!=lease["profileHash"] or expected["policyHash"]!=lease["policyHash"]:
        raise ValueError("archive differs from committed epoch")
    records=report["records"]
    if not isinstance(records,list) or not policy["minProbeCount"]<=len(records)<=120:
        raise ValueError("invalid sample count")
    previous=None
    for i,r in enumerate(records):
        if document(root/f"sample-{i:04d}.json")!=r:
            raise ValueError("sample record differs from summary")
        if r["sampleIndex"]!=i or any(r.get(k)!=ctx[k] for k in ("leaseId","epochId","monitor","requestHash","origin")):
            raise ValueError("sample scope mismatch")
        raw=read(root/f"sample-{i:04d}.reply",8192)
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=r["rawReplySha256"] or digest!=r["rawHttpBodySha256"]:
            raise ValueError("raw response mismatch")
        reply=json.loads(raw,object_pairs_hook=_unique_pairs)
        check=validate_signed_reply(reply,snapshot)
        if check["responseHash"]!=ep["responseHash"] or r["signedResponseHash"]!=ep["responseHash"]:
            raise ValueError("wrong authenticated response")
        obs=r["rawObservation"]
        if obs["httpStatus"]!=200 or obs["responseBodySha256"]!=digest or obs["elapsedMs"]!=r["elapsedMs"] or obs["providerPublicSignatureVerified"] is not True:
            raise ValueError("observation mismatch")
        if hashlib.sha256(canonical(obs)).hexdigest()!=r["rawObservationSha256"]:
            raise ValueError("observation commitment mismatch")
        stamp=datetime.fromisoformat(r["observedAtUtc"])
        if stamp.utcoffset() is None:
            raise ValueError("missing timestamp offset")
        ts=stamp.timestamp()
        start=ep["responseDeadline"]-lease["responseSeconds"]
        if not start<=ts<=ep["monitoringClose"] or (previous is not None and ts-previous<policy["probeIntervalMs"]/1000-1):
            raise ValueError("sample timing outside committed policy")
        previous=ts
        if type(r["finalizedHeight"]) is not int or not 0<r["finalizedHeight"]<=snapshot["finalizedExecutionHeight"]:
            raise ValueError("invalid sample height")
    outcome=evaluate(records,policy,ep["responseHash"])
    if any(report.get(k)!=v for k,v in outcome.items()) or outcome["conditionalSampleOutcome"]!="SUPPORTED_SAMPLE_SUCCESS":
        raise ValueError("no supported sample success")
    return {"monitor":ctx["monitor"],"evidenceHash":commitment,
            "attempts":len(records),"conditionalSampleOutcome":outcome["conditionalSampleOutcome"],
            "localTimingIndependentlyAttested":False,"physicalSlaTruthVerified":False,
            "automaticVoteAuthorized":False}

def plan(manifest,url,root,profile,policy,lease_id,epoch_id):
    snapshot=inspect(manifest,url,lease_id,epoch_id)
    result=audit(root,profile,policy,snapshot)
    current=inspect_canonical(manifest,url,lease_id,epoch_id)
    ep=current["epoch"]["ledger"]
    if current["lease"]["phase"]!=4 or ep["monitoringSealed"] or not ep["responseAuthenticated"] or ep["responseHash"]!=snapshot["epoch"]["ledger"]["responseHash"]:
        raise ValueError("canonical epoch no longer permits vote")
    height=current["observedExecutionHeight"]
    block=rpc(url,"eth_getBlockByNumber",[hex(height),False])
    if block["hash"]!=current["observedExecutionHash"] or int(block["timestamp"],16)+30>=ep["monitoringClose"]:
        raise ValueError("canonical anchor changed or vote window closed")
    args=(lease_id,epoch_id,int(result["monitor"],16))
    for getter,params,expected in (("confirmedMonitor(uint256,address)",(lease_id,args[2]),True),("voted(uint256,uint256,address)",args,False)):
        observed=decode_struct(query(rpc,url,current["ledger"],getter,params,height),(("value","bool"),))["value"]
        if observed!=expected:
            raise ValueError("monitor not confirmed or already voted")
    if rpc(url,"eth_getBlockByNumber",[hex(height),False])["hash"]!=block["hash"]:
        raise ValueError("canonical anchor changed")
    return {**result,"action":"vote","role":"monitor","params":{"leaseId":lease_id,"epochId":epoch_id,"outcome":1,"evidenceHash":result["evidenceHash"]},"ownerReviewRequired":True,"transactionSubmitted":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","archive","profile","policy"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--rpc",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"),required=True)
    p.add_argument("--lease-id",type=int,required=True)
    p.add_argument("--epoch-id",type=int,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(plan(load(a.manifest),a.rpc,a.archive,document(a.profile),document(a.policy),a.lease_id,a.epoch_id),indent=2,sort_keys=True))
    except (ValueError,OSError,TypeError,KeyError) as exc:
        p.exit(2,"R353_REFUSED: "+str(exc)+"\n")
if __name__=="__main__":
    main()
