#!/usr/bin/env python3
"""R366 reproducible scientific compute lease proposal, no signing.
Retains existing resource descriptor hash; distinct V3 policy commitment.
"""
import argparse,json
from pathlib import Path
from eth_utils import keccak
from sse_pos_r233_public_v2_compute_terms import resource_hash,canonical
from sse_pos_r362_v3_market_operations import MARKET,verify,call
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

def proposal(profile):
    ph=resource_hash(profile)
    terms={"endpointHash":"0x"+keccak(text=profile["origin"]).hex(),
           "epochs":4,"monitorBudget":16*10**14,"perMonitorEpochReward":10**14,
           "requiredFaultTolerance":1,"gasBoundSeats":4,"confirmationSeconds":3600,
           "responseSeconds":180,"monitoringSeconds":300,"evidenceSeconds":600,
           "reservationFee":2*10**14,"exposureBudget":12*10**14,
           "conditionalQuorumPolicy":True}
    policy={"schema":"SSE_V3_COMPUTE_SLA_POLICY_V1","chainId":31340,"market":MARKET,
            "resourceProfileHash":ph,"terms":terms,"epochFeeWei":10**15,
            "maxObservedLatencyMs":5000,"probeIntervalMs":10000,"minProbeCount":10,
            "minCorrectBps":10000,"timeoutTreatment":"INCONCLUSIVE_UNLESS_INDEPENDENTLY_ESTABLISHED",
            "receiptTreatment":"BINDING_PROVIDER_ADMISSION_NOT_PROOF_OF_NETWORK_DELIVERY_TIME",
            "quorumTreatment":"CONDITIONAL_ON_SOUND_MEASUREMENT_AND_AT_MOST_ONE_BYZANTINE_SELECTED_IDENTITY"}
    h="0x"+keccak(b"SSE_PUBLIC_V3_COMPUTE_SLA_V1\x00"+canonical(policy)).hex()
    return {"profile":profile,"policy":policy,"profileHash":ph,"policyHash":h,
            "terms":terms,"epochFeeWei":10**15,"totalEscrowWei":56*10**14}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--profile",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    if call(ask,MARKET,"activeMonitorCount()")[0]<4:
        raise ValueError("four active monitors required for this experiment")
    d=proposal(json.loads(a.profile.read_text()))
    with a.output.open("x") as f:json.dump(d,f,indent=2,sort_keys=True)
    print(json.dumps(d,indent=2))
if __name__=="__main__":main()
