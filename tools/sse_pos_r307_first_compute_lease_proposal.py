#!/usr/bin/env python3
"""R307 reproducible public first-lease proposal; no signing, funding or SLA claim."""
import argparse
import json
from pathlib import Path
from sse_pos_r233_public_v2_compute_terms import resource_hash,plan,RESOURCE_SCHEMA,POLICY_SCHEMA,WORKLOAD,TIMEOUT

def proposal(safety):
    profile={"schema":RESOURCE_SCHEMA,"serviceKind":"deterministic_compute",
             "workloadSpec":WORKLOAD,"origin":"https://[fca0:2328:77f8:9326:689f::1]:9443",
             "dockerImageId":"sha256:848cde736008713d2f72e8de20cc669326abc678e41f644d3d63480ce77bd20d",
             "cpuMilli":500,"memoryBytes":268435456}
    policy={"schema":POLICY_SCHEMA,"chainId":31340,
            "market":"0x6C01dBd7aA336a96d8Ab09Ea631E209612224080",
            "resourceProfileHash":resource_hash(profile),
            "measuredFinalitySafetySeconds":safety,
            "confirmationSeconds":max(3600,safety*2),
            "responseSeconds":max(3600,safety*2),
            "monitoringSeconds":max(3600,safety*2),
            "maxObservedLatencyMs":5000,"probeIntervalMs":60000,
            "minProbeCount":10,"minCorrectBps":10000,
            "timeoutTreatment":TIMEOUT}
    commitments=plan(profile,policy,epochs=1,seats=4,faults=1,reward=100000000000000)
    return {"profile":profile,"policy":policy,"commitments":commitments,
            "proposedProviderEpochFeeWei":"1000000000000000",
            "proposedTotalEscrowWei":"1400000000000000",
            "tlsFingerprintOutOfBand":"7895f7fbfde39c0d167c711f33e9cb4e14f5bddc65d9c022621dc6e77af81db5",
            "tlsFingerprintCommittedOnChain":False,
            "proposedOnly":True,"transactionAuthorized":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--finality-safety-seconds",type=int,required=True)
    a=p.parse_args()
    if not 1<=a.finality_safety_seconds<=302400:
        p.error("positive measured safety margin required, at most 302400 seconds")
    print(json.dumps(proposal(a.finality_safety_seconds),indent=2,sort_keys=True))

if __name__=="__main__":
    main()
