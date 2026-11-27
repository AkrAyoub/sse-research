#!/usr/bin/env python3
"""Prepare the exact funded bid from public committed terms and canonical receipt.
Read-only. Refuses mismatched commitments, wrong provider, early funding,
and unfinalized bid. Does not sign, submit or wait.
"""
import argparse
import json
from pathlib import Path
from sse_challenge import keccak256
from sse_pos_r206_adaptive_v2_deployment_audit import load,rpc,verify
from sse_pos_r229_v2_finalized_lease_snapshot import query,decode_struct
from sse_pos_r233_public_v2_compute_terms import resource_hash,policy_hash,funding_terms
from sse_pos_r350_v2_canonical_lease_snapshot import block_identity

def prepare(manifest,url,request_id,bid_tx,consumer,provider,profile,policy,*,epochs=1,seats=4,faults=1,reward=10**14):
    proof=verify(manifest,url)
    market=manifest["market"]["address"].lower()
    head=rpc(url,"eth_getBlockByNumber",["latest",False])
    height,digest=block_identity(head)
    r=decode_struct(query(rpc,url,market,"requests(uint256)",(request_id,),height),
        (("consumer","address"),("profileHash","bytes32"),("policyHash","bytes32"),("maxEpochFee","uint256"),("biddingClose","uint64"),("selected","bool")))
    if r["consumer"]!=consumer.lower() or r["selected"]:
        raise ValueError("request not owned or already selected")
    if r["profileHash"]!=resource_hash(profile) or r["policyHash"]!=policy_hash(policy,profile):
        raise ValueError("request hashes do not match provided real profile and policy; do not fund")
    if policy["market"].lower()!=market:
        raise ValueError("wrong policy market")
    receipt=rpc(url,"eth_getTransactionReceipt",[bid_tx])
    if not receipt or receipt["status"]!="0x1" or receipt["transactionHash"].lower()!=bid_tx.lower():
        raise ValueError("successful bid receipt required")
    bh=int(receipt["blockNumber"],16)
    if block_identity(rpc(url,"eth_getBlockByNumber",[hex(bh),False]))!=(bh,receipt["blockHash"].lower()):
        raise ValueError("bid receipt not canonical")
    topic="0x"+keccak256(b"BidPlaced(uint256,uint256,address,uint256)").hex()
    logs=[l for l in receipt["logs"] if l["address"].lower()==market and len(l["topics"])==4 and l["topics"][0]==topic and int(l["topics"][1],16)==request_id and l["topics"][3][-40:].lower()==provider.lower()[2:]]
    if len(logs)!=1:
        raise ValueError("expected unique matching provider bid event")
    index=int(logs[0]["topics"][2],16)
    price=int(logs[0]["data"],16)
    bid=decode_struct(query(rpc,url,market,"getBid(uint256,uint256)",(request_id,index),height),(("provider","address"),("price","uint256")))
    if bid!={"provider":provider.lower(),"price":price} or not 0<price<=r["maxEpochFee"]:
        raise ValueError("canonical bid differs from receipt")
    terms=funding_terms(profile,policy,epochs=epochs,expected_seats=seats,fault_tolerance=faults,reward_per_seat_epoch_wei=reward)
    if block_identity(rpc(url,"eth_getBlockByNumber",[hex(height),False]))!=(height,digest):
        raise ValueError("request anchor reorganized")
    ready_time=int(head["timestamp"],16)>=r["biddingClose"]
    ready_final=proof["finalizedExecutionHeight"]>=bh
    return {"requestId":request_id,"bidIndex":index,"provider":provider.lower(),"bidEpochFeeWei":price,
        "biddingClose":r["biddingClose"],"chainTimestamp":int(head["timestamp"],16),
        "biddingClosed":ready_time,"bidFinalized":ready_final,"readyToFund":ready_time and ready_final,
        "params":{"requestId":request_id,"bidIndex":index,"bidEpochFeeWei":price,"terms":terms},
        "escrowWei":price*epochs+terms["monitorBudgetWei"],"transactionSubmitted":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","profile","policy"): p.add_argument("--"+name,type=Path,required=True)
    for name in ("bid-tx","consumer","provider"): p.add_argument("--"+name,required=True)
    p.add_argument("--request-id",type=int,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    try:
        print(json.dumps(prepare(load(a.manifest),a.rpc,a.request_id,a.bid_tx,a.consumer,a.provider,json.loads(a.profile.read_text()),json.loads(a.policy.read_text())),indent=2,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError) as e: p.exit(2,"R360_FUND_REFUSED: "+str(e)+"\n")
if __name__=="__main__": main()
