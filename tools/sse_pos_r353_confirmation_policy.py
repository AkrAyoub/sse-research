#!/usr/bin/env python3
"""R353b: explicit risk policy for canonical observations, not settlement finality.
Default remains finalized. Canonical authorization requires an explicit
bounded exposure budget and a fresh canonical anchor. No signing or sends.
"""
from dataclasses import dataclass
from sse_pos_r350_v2_canonical_lease_snapshot import block_identity,inspect_canonical
from sse_pos_r229_v2_finalized_lease_snapshot import inspect
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

CANONICAL_ACTIONS=frozenset(("observe","provider-response","service-delivery","monitor-sample","confirm-seat","accept","start-epoch","authenticate-response","vote"))
FINALIZED_ONLY=frozenset(("settlement-accounting","withdrawal-accounting","fund","resolve-inconclusive"))

@dataclass(frozen=True)
class Policy:
    mode:str="finalized"
    min_confirmations:int=1
    max_unfinalized_wei:int=0
    def __post_init__(self):
        if self.mode not in ("finalized","canonical"):
            raise ValueError("unknown assurance mode")
        if type(self.min_confirmations) is not int or not 1<=self.min_confirmations<=256:
            raise ValueError("invalid minimum confirmations")
        if type(self.max_unfinalized_wei) is not int or not 0<=self.max_unfinalized_wei<2**256:
            raise ValueError("invalid exposure budget")

def authorize_observation(manifest,url,lease_id,epoch_id,action,policy,*,exposure_wei=0,prior_exposure_wei=0,transport=rpc):
    if action not in CANONICAL_ACTIONS|FINALIZED_ONLY:
        raise ValueError("unknown policy action")
    if any(type(x) is not int or x<0 for x in (exposure_wei,prior_exposure_wei)):
        raise ValueError("invalid exposure")
    if policy.mode=="finalized" or action in FINALIZED_ONLY:
        return {"assurance":"FINALIZED","snapshot":inspect(manifest,url,lease_id,epoch_id,transport=transport),
                "action":action,"automaticSigningAuthorized":False}
    if exposure_wei+prior_exposure_wei>policy.max_unfinalized_wei:
        raise ValueError("unfinalized exposure budget exceeded")
    state=inspect_canonical(manifest,url,lease_id,epoch_id,confirmations=policy.min_confirmations,transport=transport)
    height=state["observedExecutionHeight"]
    anchor=(height,state["observedExecutionHash"])
    head,_=block_identity(transport(url,"eth_getBlockByNumber",["latest",False]))
    if head-height+1<policy.min_confirmations:
        raise ValueError("canonical observation has insufficient confirmations")
    if block_identity(transport(url,"eth_getBlockByNumber",[hex(height),False]))!=anchor:
        raise ValueError("canonical observation reorganized")
    return {"assurance":"PROVISIONAL_CANONICAL","snapshot":state,"action":action,
            "anchorHeight":height,"anchorHash":anchor[1],"confirmations":head-height+1,
            "declaredExposureWei":exposure_wei+prior_exposure_wei,
            "automaticSigningAuthorized":False,"revalidationRequired":True}

def revalidate_anchor(result,url,*,transport=rpc):
    if result["assurance"]!="PROVISIONAL_CANONICAL":
        raise ValueError("expected provisional observation")
    h=result["anchorHeight"]
    return block_identity(transport(url,"eth_getBlockByNumber",[hex(h),False]))==(h,result["anchorHash"])
