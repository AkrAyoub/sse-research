#!/usr/bin/env python3
"""R349 bounded finalized V2 SLA sampling. No signing or broadcast.

A session records every attempted request, including inconclusive errors.
A passing sample set is conditional observational evidence, not physical
attestation or a verdict over the entire contractual monitoring window.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone

from sse_pos_r232_v2_monitor_probe import (
    prepared_monitor, pinned_tls_context, http_probe, inspect_response,
    write_create_only, write_bytes_create_only,
)
from sse_pos_r229_v2_finalized_lease_snapshot import inspect
from sse_pos_r206_adaptive_v2_deployment_audit import load, rpc
from sse_pos_r233_public_v2_compute_terms import resource_hash, policy_hash
from sse_challenge import keccak256


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def evaluate(records, policy, response_hash):
    count = len(records)
    correct = sum(r.get("providerSignatureVerified") is True
                  and r.get("signedResponseHash") == response_hash
                  for r in records)
    within = sum(r.get("providerSignatureVerified") is True
                 and r.get("signedResponseHash") == response_hash
                 and type(r.get("elapsedMs")) is int
                 and 0 <= r["elapsedMs"] <= policy["maxObservedLatencyMs"]
                 for r in records)
    passed = (count >= policy["minProbeCount"] and correct == count
              and within == count)
    return {"attempts": count, "authenticatedCorrect": correct,
            "withinLatency": within,
            "conditionalSampleOutcome": "SUPPORTED_SAMPLE_SUCCESS" if passed else "INCONCLUSIVE",
            "automaticVoteAuthorized": False,
            "physicalSlaTruthVerified": False}


def run(a):
    manifest = load(a.manifest)
    profile = json.loads(a.profile.read_text())
    policy = json.loads(a.policy.read_text())
    ph, sh = resource_hash(profile), policy_hash(policy, profile)
    tls = pinned_tls_context(a.tls_cert, a.tls_fingerprint)
    depth = getattr(a,"canonical_confirmations",None)
    provisional = depth is not None
    from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical,block_identity
    def snapshot_now():
        if provisional:
            return inspect_canonical(manifest,a.rpc,a.lease_id,a.epoch_id,confirmations=depth)
        return inspect(manifest,a.rpc,a.lease_id,a.epoch_id)
    def check_anchor(state):
        if provisional:
            h=state["observedExecutionHeight"]
            if block_identity(rpc(a.rpc,"eth_getBlockByNumber",[hex(h),False]))!=(h,state["observedExecutionHash"]):
                raise ValueError("sample canonical anchor reorganized")
    snapshot = snapshot_now()
    ctx = prepared_monitor(snapshot, a.monitor, profile["origin"], rpc_url=a.rpc,allow_canonical=True) if provisional else prepared_monitor(snapshot,a.monitor,profile["origin"],rpc_url=a.rpc)
    lease = snapshot["lease"]
    ep = snapshot["epoch"]["ledger"]
    if (lease["profileHash"] != ph or lease["policyHash"] != sh
        or policy["market"].lower() != snapshot["market"].lower()
        or not ep["responseAuthenticated"]):
        raise ValueError("committed terms or finalized authenticated response missing")
    rh = ep["responseHash"]
    if a.count < policy["minProbeCount"] or a.count > 120:
        raise ValueError("sample count must meet policy and be <=120")
    interval = policy["probeIntervalMs"] / 1000
    if interval < 1:
        raise ValueError("R349 requires at least one second sample interval")
    def check_window():
        head = rpc(a.rpc, "eth_getBlockByNumber", ["latest", False])
        if max(int(head["timestamp"], 16), time.time()) + 10 >= ep["monitoringClose"]:
            raise ValueError("insufficient remaining monitoring window")
    check_window()
    if time.time() + (a.count-1)*interval + 10 >= ep["monitoringClose"]:
        raise ValueError("sample session cannot fit remaining window")
    root = a.output.absolute()
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    records = []
    challenge = {k:ctx[k] for k in ("leaseId","epochId","requestHash")}
    for i in range(a.count):
        if i:
            time.sleep(max(0, next_at-time.monotonic()))
        check_window()
        check_anchor(snapshot)
        current = snapshot_now()
        if provisional:
            prepared_monitor(current,a.monitor,profile["origin"],rpc_url=a.rpc,allow_canonical=True)
        else:
            prepared_monitor(current,a.monitor,profile["origin"],rpc_url=a.rpc)
        now_ep = current["epoch"]["ledger"]
        if (not now_ep["responseAuthenticated"] or now_ep["responseHash"] != rh
            or current["epoch"]["market"]["requestHash"] != ctx["requestHash"]
            or now_ep["monitoringClose"] != ep["monitoringClose"]
            or current["lease"]["profileHash"] != ph or current["lease"]["policyHash"] != sh
            or current["lease"]["provider"] != lease["provider"] or current["lease"]["endpointHash"] != lease["endpointHash"]):
            raise ValueError("finalized epoch context changed")
        next_at = time.monotonic() + interval
        observed = http_probe(ctx["origin"],challenge,
                              min(8, max(1,policy["maxObservedLatencyMs"]/1000+1)),
                              tls_context=tls)
        record = {"sampleIndex":i,"observedAtUtc":datetime.now(timezone.utc).isoformat(),
                  "leaseId":a.lease_id,"epochId":a.epoch_id,"monitor":ctx["monitor"],
                  "requestHash":ctx["requestHash"],
                  **({"canonicalHeight":current["observedExecutionHeight"],"canonicalHash":current["observedExecutionHash"]} if provisional else {"finalizedHeight":current["finalizedExecutionHeight"]}),
                  "elapsedMs":observed["elapsedMs"],"transportStatus":observed["transportStatus"]}
        if observed["body"] is not None:
            raw = observed["body"]
            write_bytes_create_only(root / f"sample-{i:04d}.reply", raw)
            record["rawReplySha256"] = hashlib.sha256(raw).hexdigest()
        try:
            record.update(inspect_response(observed,current,ctx,allow_canonical=True) if provisional else inspect_response(observed,current,ctx))
        except (ValueError,TypeError,KeyError) as exc:
            record.update(providerSignatureVerified=False,validationError=type(exc).__name__)
        check_anchor(current)
        write_create_only(root / f"sample-{i:04d}.json",record)
        records.append(record)
        print(json.dumps({"sample":i+1,"elapsedMs":record["elapsedMs"],
                          "verified":record.get("providerSignatureVerified",False)}),flush=True)
    if provisional:
        check_anchor(snapshot)
        for record in records:
            h=record["canonicalHeight"]
            if block_identity(rpc(a.rpc,"eth_getBlockByNumber",[hex(h),False]))!=(h,record["canonicalHash"]):
                raise ValueError("archived sample anchor reorganized; no summary issued")
    report = {"schema":"SSE_R356_CANONICAL_SAMPLE_SESSION_V1" if provisional else "SSE_R349_FINALIZED_SAMPLE_SESSION_V1",
              "chainId":31340,"market":snapshot["market"],"monitor":ctx["monitor"],
              "leaseId":a.lease_id,"epochId":a.epoch_id,"requestHash":ctx["requestHash"],
              "responseHash":rh,"profileHash":ph,"policyHash":sh,
              "records":records,**evaluate(records,policy,rh)}
    if provisional:
        report.update(canonicalConfirmations=depth,initialCanonicalHeight=snapshot["observedExecutionHeight"],initialCanonicalHash=snapshot["observedExecutionHash"],finalizedAuthorization=False)
    prefix=b"SSE_R356_CANONICAL_SAMPLE_SESSION_V1\x00" if provisional else b"SSE_R349_SAMPLE_SESSION_V1\x00"
    report["evidenceHash"]="0x"+keccak256(prefix+canonical(report)).hex()
    write_create_only(root / "summary.json",report)
    print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","profile","policy","tls-cert","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--rpc",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"),required=True)
    p.add_argument("--lease-id",type=int,required=True)
    p.add_argument("--epoch-id",type=int,required=True)
    p.add_argument("--monitor",required=True)
    p.add_argument("--tls-fingerprint",required=True)
    p.add_argument("--count",type=int,required=True)
    p.add_argument("--canonical-confirmations",type=int,help="explicit provisional observations; no finalized vote authorization")
    try:
        run(p.parse_args())
    except (ValueError,OSError,TypeError,KeyError) as exc:
        p.exit(2,"R349_REFUSED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
