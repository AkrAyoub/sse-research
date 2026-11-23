#!/usr/bin/env python3
"""R233: public HTTPS dynamic-DNS resource/SLA terms for actual chain31340 V2.

Separate from older V1 Tailscale-only resource/SLA manifests. These
canonical off-chain profile/policy hashes are committed in V2 resource
requests; a signed hash is NOT actual physical CPU/SLA evidence. No DNS,
Docker or wallet access occurs in this source-only planning module.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

from sse_challenge import keccak256
from sse_pos_r232_v2_monitor_probe import canonical_origin, Refused as OriginRefused
from sse_pos_r228_v2_typed_data import checked_addr,checked_hash

RESOURCE_SCHEMA="SSE_V2_PUBLIC_COMPUTE_PROFILE_V1"
POLICY_SCHEMA="SSE_V2_PUBLIC_COMPUTE_SLA_POLICY_V1"
RESOURCE_PREFIX=b"SSE_PUBLIC_V2_COMPUTE_RESOURCE_V1\x00"
POLICY_PREFIX=b"SSE_PUBLIC_V2_COMPUTE_SLA_V1\x00"
IMAGE=re.compile(r"sha256:[0-9a-f]{64}\Z")
PROFILE_KEYS={
    "schema","serviceKind","workloadSpec","origin",
    "dockerImageId","cpuMilli","memoryBytes"
}
POLICY_KEYS={
    "schema","chainId","market","resourceProfileHash",
    "measuredFinalitySafetySeconds","confirmationSeconds",
    "responseSeconds","monitoringSeconds",
    "maxObservedLatencyMs","probeIntervalMs",
    "minProbeCount","minCorrectBps","timeoutTreatment",
}
WORKLOAD="SSE_SHA256_CHAIN_8192_V1"
TIMEOUT="INCONCLUSIVE_UNLESS_INDEPENDENTLY_ESTABLISHED"

class Refused(ValueError):
    pass


def u(value,label,lo,hi):
    if type(value) is not int or not lo<=value<=hi:
        raise Refused("invalid "+label)
    return value


def validate_profile(profile):
    if type(profile) is not dict or set(profile)!=PROFILE_KEYS or profile["schema"]!=RESOURCE_SCHEMA:
        raise Refused("unknown/altered public V2 compute resource manifest")
    if profile["serviceKind"]!="deterministic_compute" or profile["workloadSpec"]!=WORKLOAD:
        raise Refused("unsupported physical workload")
    try:
        canonical_origin(profile["origin"])
    except OriginRefused as exc:
        raise Refused("unapproved V2 compute origin") from exc
    if type(profile["dockerImageId"]) is not str or not IMAGE.fullmatch(profile["dockerImageId"]):
        raise Refused("must pin exact Docker image ID")
    u(profile["cpuMilli"],"cpuMilli",1,64000)
    u(profile["memoryBytes"],"memoryBytes",64*2**20,512*2**30)
    return profile


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


def resource_hash(profile):
    validate_profile(profile)
    return "0x"+keccak256(RESOURCE_PREFIX+canonical(profile)).hex()


def validate_policy(policy,profile):
    validate_profile(profile)
    if (type(policy) is not dict or set(policy)!=POLICY_KEYS or
        policy["schema"]!=POLICY_SCHEMA or policy["chainId"]!=31340):
        raise Refused("unknown/altered original-chain V2 SLA policy")
    checked_addr(policy["market"])
    if policy["resourceProfileHash"]!=resource_hash(profile):
        raise Refused("SLA policy does not commit actual immutable resource profile")
    safety=u(policy["measuredFinalitySafetySeconds"],
             "measuredFinalitySafetySeconds",1,604800)
    confirmation=u(policy["confirmationSeconds"],"confirmationSeconds",3600,604800)
    response=u(policy["responseSeconds"],"responseSeconds",1,604800)
    monitoring=u(policy["monitoringSeconds"],"monitoringSeconds",1,604800)
    if response<safety or confirmation<safety:
        raise Refused("response/confirmation deadlines shorter than stated finality safety")
    probe=u(policy["probeIntervalMs"],"probeIntervalMs",100,3600000)
    latency=u(policy["maxObservedLatencyMs"],"maxObservedLatencyMs",1,3600000)
    count=u(policy["minProbeCount"],"minProbeCount",1,10000)
    u(policy["minCorrectBps"],"minCorrectBps",1,10000)
    if (count*probe>monitoring*1000 or
        latency>monitoring*1000 or
        policy["timeoutTreatment"]!=TIMEOUT):
        raise Refused("no viable strict monitor sampling/evidence deadline")
    return policy


def policy_hash(policy,profile):
    validate_policy(policy,profile)
    return "0x"+keccak256(POLICY_PREFIX+canonical(policy)).hex()


def funding_terms(profile,policy,*,epochs,expected_seats,
                  fault_tolerance,reward_per_seat_epoch_wei):
    validate_policy(policy,profile)
    u(epochs,"epochs",1,64)
    u(expected_seats,"expected_seats",4,64)
    u(fault_tolerance,"fault_tolerance",1,64)
    u(reward_per_seat_epoch_wei,"monitor reward",1,2**128-1)
    if expected_seats<3*fault_tolerance+1:
        raise Refused("declared committee seats insufficient for modeled f")
    budget=expected_seats*epochs*reward_per_seat_epoch_wei
    if budget>=2**256:
        raise Refused("monitor reward escrow uint256 overflow")
    return {
        "endpointHash":"0x"+keccak256(profile["origin"].encode("ascii")).hex(),
        "epochs":epochs,"monitorBudgetWei":budget,
        "perMonitorEpochRewardWei":reward_per_seat_epoch_wei,
        "requiredFaultTolerance":fault_tolerance,
        "gasBoundSeats":expected_seats,
        "confirmationSeconds":policy["confirmationSeconds"],
        "responseSeconds":policy["responseSeconds"],
        "monitoringSeconds":policy["monitoringSeconds"],
    }


def plan(profile,policy,*,epochs,seats,faults,reward):
    terms=funding_terms(profile,policy,epochs=epochs,
                        expected_seats=seats,fault_tolerance=faults,
                        reward_per_seat_epoch_wei=reward)
    return {
        "schema":"SSE_R233_V2_PUBLIC_COMPUTE_REQUEST_COMMITMENTS_V1",
        "chainId":31340,"resourceProfileHash":resource_hash(profile),
        "slaPolicyHash":policy_hash(policy,profile),
        "fundingTermsProposal":terms,
        "responseDeadlineIncludesDeclaredFinalitySafety":True,
        "gasBoundSeatsAreNotNetworkPopulationLimit":True,
        "actualEligibleIndependentMonitorsVerified":False,
        "physicalResourcesMeasured":False,
        "nativeTestEthReceived":False,
        "transactionSignedOrSubmitted":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile",required=True,type=Path)
    p.add_argument("--policy",required=True,type=Path)
    p.add_argument("--epochs",type=int,required=True)
    p.add_argument("--expected-seats",type=int,required=True)
    p.add_argument("--fault-tolerance",type=int,required=True)
    p.add_argument("--per-monitor-epoch-reward-wei",type=int,required=True)
    a=p.parse_args(argv)
    try:
        for path in (a.profile,a.policy):
            if path.is_symlink() or not path.is_file() or path.stat().st_size>8192:
                raise Refused("manifest file must be small regular and non-symlink")
        profile=json.loads(a.profile.read_text("utf-8"))
        policy=json.loads(a.policy.read_text("utf-8"))
        report=plan(profile,policy,epochs=a.epochs,seats=a.expected_seats,
                    faults=a.fault_tolerance,reward=a.per_monitor_epoch_reward_wei)
        print(json.dumps(report,sort_keys=True,indent=2))
        return 0
    except (Refused,ValueError,TypeError,KeyError,OSError,OverflowError) as exc:
        print("R233_PUBLIC_V2_COMPUTE_TERMS_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
