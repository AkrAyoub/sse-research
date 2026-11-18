#!/usr/bin/env python3
"""Reproducible SSE observation-limited settlement falsification experiment.

A MODEL, not live infrastructure, a physical-truth oracle, an EVM execution,
or universal safety proof. Abstracts reachable on-chain counterexamples.
The finite seeded universe includes HTTP/compute worlds N,F,S, partitions,
up to two adversarial monitors, untrusted ACK claims and ambiguous signed
provider responses. Provides three explicitly different evidence policies:
quorum-style, ambiguity-hold, and an omniscient illustrative oracle.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys

SERVICES=("HTTP_CHALLENGE","DETERMINISTIC_COMPUTE")
WORLDS=("N","F","S")
POLICIES=("observed_quorum","ambiguity_hold","ideal_oracle")
SHA=re.compile(r"[0-9a-f]{40}\Z")
MAX_ROWS=100000
FIELDS=(
    "service","world","partitionedMonitors","adversarialMonitors",
    "replication","onlineAdversarialMonitors","observedSuccessVotes","observedFailureVotes",
    "signedResponseVisible","untrustedAckClaim","hypotheticalVerifiedOutcome",
    "policy","providerCreditWei","consumerCreditWei","heldWei",
    "providerOvercreditWei","consumerOvercreditWei","isUnsafeCredit",
)

class CampaignError(ValueError):
    pass

def wilson95(k:int,n:int)->tuple[float,float]:
    if type(k) is not int or type(n) is not int or n<1 or not 0<=k<=n:
        raise CampaignError("invalid binomial counts")
    z=1.959963984540054
    p=k/n
    den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    # At k=0 or k=n, floating-point roundoff must not exclude the
    # observed proportion from its own Wilson confidence interval.
    return min(max(0.,center-half),p),max(min(1.,center+half),p)

def allocation(histories:set[str],fee:int,reservation:int)->tuple[int,int,int]:
    """WP02 bounds: L=min entitlement, consumer=fee-max, held=max-min."""
    if (not isinstance(histories,set) or not histories
            or not histories.issubset(WORLDS)
            or type(fee) is not int or type(reservation) is not int
            or fee<=0 or not 0<=reservation<=fee):
        raise CampaignError("invalid histories/escrow")
    ent={"N":reservation,"F":0,"S":fee}
    low=min(ent[h] for h in histories)
    high=max(ent[h] for h in histories)
    result=(low,fee-high,high-low)
    assert sum(result)==fee
    return result

def scenario(seed:int,service:str,world:str,offline:int,bad:int,index:int)->dict:
    digest=hashlib.sha256(
        f"SSE-R10-V1|{seed}|{service}|{world}|{offline}|{bad}|{index}".encode()
    ).digest()
    rng=random.Random(int.from_bytes(digest,"big"))
    ids=list(range(4))
    rng.shuffle(ids)
    disconnected=set(ids[:offline])
    # Assigned Byzantine identities and offline links are orthogonal
    # independent factors. A Byzantine node may itself be partitioned.
    rng.shuffle(ids)
    adversary=set(ids[:bad])
    # A signed response may be broadcast without physical delivery;
    # monitors may miss a real delivery. Rates are declared model knobs,
    # NOT measured network statistics.
    broadcast=rng.random()<(.20 if world=="N" else .72 if world=="F" else .88)
    ack=rng.random()<(.08 if world=="N" else .35 if world=="F" else .30)
    success=failure=0
    for monitor in range(4):
        if monitor in disconnected:
            continue
        if monitor in adversary:
            vote="S" if broadcast and rng.random()<.75 else "F"
        else:
            vote="S" if broadcast else "F"
        success+=int(vote=="S")
        failure+=int(vote=="F")
    # Explicitly HYPOTHETICAL trusted physical outcome certificate.
    # It is not a feature of today's SSE contracts.
    certified=world if rng.random()<.22 else ""
    return dict(
        service=service,world=world,partitionedMonitors=offline,
        adversarialMonitors=bad,replication=index,
        onlineAdversarialMonitors=len(adversary-disconnected),
        observedSuccessVotes=success,observedFailureVotes=failure,
        signedResponseVisible=broadcast,untrustedAckClaim=ack,
        hypotheticalVerifiedOutcome=certified,
    )

def policy_allocation(case:dict,policy:str,fee:int,reservation:int):
    if policy=="ideal_oracle":
        return allocation({case["world"]},fee,reservation)
    if policy=="ambiguity_hold":
        certificate=case["hypotheticalVerifiedOutcome"]
        return allocation({certificate} if certificate in WORLDS else set(WORLDS),
                          fee,reservation)
    if policy!="observed_quorum":
        raise CampaignError("unsupported policy")
    # CE01-CE04 inspired comparator; NOT a Solidity byte-for-byte emulator.
    if case["observedSuccessVotes"]>=3 and case["signedResponseVisible"]:
        possible={"S"}
    elif case["observedFailureVotes"]>=3:
        possible={"F"} if case["untrustedAckClaim"] else {"N","F"}
    else:
        possible=set(WORLDS)
    return allocation(possible,fee,reservation)

def trial_rows(*,seed:int,replications:int,fee:int,reservation:int):
    if (type(seed) is not int or not 0<=seed<2**63
            or type(replications) is not int or not 1<=replications<=500
            or type(fee) is not int or type(reservation) is not int
            or not 0<=reservation<=fee or fee<1
            or 270*replications>MAX_ROWS):
        raise CampaignError("parameters exceed preregistered model bounds")
    for service in SERVICES:
        for world in WORLDS:
            for offline in range(5):
                for bad in range(3):
                    for idx in range(replications):
                        case=scenario(seed,service,world,offline,bad,idx)
                        entitled={"N":reservation,"F":0,"S":fee}[world]
                        for policy in POLICIES:
                            provider,consumer,held=policy_allocation(
                                case,policy,fee,reservation)
                            assert provider+consumer+held==fee
                            overp=max(0,provider-entitled)
                            overc=max(0,consumer-(fee-entitled))
                            yield {
                                **case,"policy":policy,
                                "providerCreditWei":provider,
                                "consumerCreditWei":consumer,
                                "heldWei":held,
                                "providerOvercreditWei":overp,
                                "consumerOvercreditWei":overc,
                                "isUnsafeCredit":(overp+overc)>0,
                            }

def summarize(rows:list[dict],*,seed:int,replications:int,fee:int,reservation:int):
    if len(rows)!=270*replications:
        raise CampaignError("incomplete full-factor model grid")
    groups={}
    for row in rows:
        key=(row["policy"],row["partitionedMonitors"],row["adversarialMonitors"])
        groups.setdefault(key,[]).append(row)
    arms=[]
    for (policy,offline,bad),group in sorted(groups.items()):
        n=len(group)
        failures=sum(r["isUnsafeCredit"] for r in group)
        lower,upper=wilson95(failures,n)
        arms.append({
            "policy":policy,"partitionedMonitors":offline,"adversarialMonitors":bad,
            "trials":n,"unsafeCreditTrials":failures,
            "unsafeCreditRate":failures/n,
            "unsafeRateWilson95Lower":lower,"unsafeRateWilson95Upper":upper,
            "meanHeldWei":statistics.fmean(r["heldWei"] for r in group),
            "meanProviderOvercreditWei":statistics.fmean(r["providerOvercreditWei"] for r in group),
            "meanConsumerOvercreditWei":statistics.fmean(r["consumerOvercreditWei"] for r in group),
        })
    return {
        "schema":"SSE_R10_OBSERVATION_SETTLEMENT_CAMPAIGN_V1",
        "scientificStatus":"SYNTHETIC_MODEL_ONLY",
        "notMeasuredLiveNetwork":True,
        "notAnImplementedSmartContractPatch":True,
        "notUniversalPhysicalSoundnessProof":True,
        "hypotheticalTrustedReceiptNotDeployed":True,
        "services":list(SERVICES),"worlds":list(WORLDS),"policies":list(POLICIES),
        "seed":seed,"replicationsPerStratum":replications,"feeWei":fee,
        "reservationWei":reservation,
        "totalPolicyRows":len(rows),
        "uniqueModelScenarios":len(rows)//len(POLICIES),
        "committeeSize":4,"quorum":3,"arms":arms,
        "limits":"Wilson intervals quantify sampling variability in this finite "
                 "synthetic model, not external validity. Actual network"
                 "latency and physical SLA outcomes were not measured.",
    }

def write_once(path:Path,payload:bytes):
    if (not path.is_absolute() or not path.parent.is_dir()
            or path.parent.is_symlink() or path.exists() or path.is_symlink()):
        raise CampaignError("new output files in existing secure directory required")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())

def run(directory:Path,*,revision:str,seed:int=20261118,
        replications:int=25,fee:int=25,reservation:int=5):
    if (type(revision) is not str or not SHA.fullmatch(revision)
            or not directory.is_absolute() or not directory.is_dir()
            or directory.is_symlink() or (os.name=="posix" and directory.stat().st_mode&0o022)):
        raise CampaignError("secure directory and exact source SHA required")
    names=("trials.csv","summary.json","summary.md","manifest.json")
    if any((directory/n).exists() or (directory/n).is_symlink() for n in names):
        raise CampaignError("refusing to overwrite immutable research output")
    rows=list(trial_rows(seed=seed,replications=replications,
                         fee=fee,reservation=reservation))
    report=summarize(rows,seed=seed,replications=replications,
                     fee=fee,reservation=reservation)
    output=io.StringIO(newline="")
    writer=csv.DictWriter(output,fieldnames=FIELDS,lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csvbytes=output.getvalue().encode()
    jsonbytes=(json.dumps(report,sort_keys=True,indent=2)+"\n").encode()
    md=[
        "# SSE R10 observation-limited settlement model",
        "",
        "**Synthetic simulation, not measured blockchain/physical network.**",
        "",
        f"- Source revision: {revision}",
        f"- Model scenarios: {report['uniqueModelScenarios']}",
        f"- Policy trials: {len(rows)}",
        f"- Fee/reservation (wei): {fee}/{reservation}",
        "",
        "| Policy | Unsafe release trials | Mean withheld wei |",
        "|---|---:|---:|",
    ]
    for name in POLICIES:
        subset=[r for r in rows if r["policy"]==name]
        md.append(f"| {name} | {sum(r['isUnsafeCredit'] for r in subset)} / "
                  f"{len(subset)} | {statistics.fmean(r['heldWei'] for r in subset):.3f} |")
    md.extend([
        "",
        "The 'observed_quorum' arm is an abstraction of the current "
        "SSE EVM counterexamples, not an exploit frequency. "
        "A signed response is not proof of physical consumer delivery. "
        "The 'ambiguity_hold' arm assumes a hypothetical trusted outcome "
        "certificate for a declared fraction of trials; that oracle is NOT "
        "present in the deployed contract. The ideal comparator knows true "
        "world labels that operational nodes do NOT know. "
        "Holding funds conservatively improves immediate financial safety "
        "in this model at an explicit capital-liveness cost.",
        "",
        "Next: require actual independent VM observations, controlled "
        "network partitions, service execution witnesses, pinned source "
        "and four-validator RPC agreement before reporting external validity.",
        "",
    ])
    mdbytes=("\n".join(md)).encode()
    artifacts={"trials.csv":csvbytes,"summary.json":jsonbytes,"summary.md":mdbytes}
    for name,blob in artifacts.items():
        write_once(directory/name,blob)
    manifest={
        "schema":"SSE_R10_MODEL_EVIDENCE_V1",
        "gitCommit":revision,"seed":seed,"rawDataKind":"synthetic",
        "rawDataPreserved":True,"liveNetworkMeasured":False,
        "artifacts":{name:{"sha256":hashlib.sha256(blob).hexdigest(),
                           "bytes":len(blob)} for name,blob in artifacts.items()},
        "operatorApprovalForPublicationRequired":True,
        "ethereumTransactionsSent":False,"vmsModified":False,
    }
    write_once(directory/"manifest.json",
               (json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode())
    return manifest

def main(argv=None):
    p=argparse.ArgumentParser(description="SSE model falsification: deterministic preregistered campaign")
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--seed",type=int,default=20261118)
    p.add_argument("--replications",type=int,default=25)
    p.add_argument("--fee-wei",type=int,default=25)
    p.add_argument("--reservation-wei",type=int,default=5)
    a=p.parse_args(argv)
    try:
        result=run(a.output_dir,revision=a.source_commit,seed=a.seed,
                   replications=a.replications,fee=a.fee_wei,
                   reservation=a.reservation_wei)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (CampaignError,OSError,TypeError,ValueError) as exc:
        print("SSE_R10_MODEL_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
