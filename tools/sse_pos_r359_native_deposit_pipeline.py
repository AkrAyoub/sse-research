#!/usr/bin/env python3
"""Read-only chain31340 execution/consensus deposit pipeline diagnostics.
No signing, RPC writes, configuration changes or client restarts.
"""
import argparse
import json
import time
import urllib.error
from pathlib import Path
from sse_pos_r358_validator_deposit import beacon,BEACON_ROOT,CONTRACT
from sse_pos_r206_adaptive_v2_deployment_audit import rpc,GENESIS

def optional(path):
    try:
        return {"available":True,"data":beacon(path)}
    except urllib.error.HTTPError as e:
        return {"available":False,"httpStatus":e.code}
    except (ValueError,OSError) as e:
        return {"available":False,"reason":type(e).__name__}

def payload_summary(block,keys):
    msg=block["message"]
    body=msg["body"]
    payload=body["execution_payload"]
    requests=body.get("execution_requests")
    deposits=requests.get("deposits",[]) if isinstance(requests,dict) else []
    legacy=body.get("deposits",[])
    return {"slot":int(msg["slot"]),"proposerIndex":msg["proposer_index"],
            "executionHeight":int(payload["block_number"]),"executionHash":payload["block_hash"],
            "executionTimestamp":int(payload["timestamp"]),
            "executionRequestsPresent":requests is not None,
            "depositRequestCount":len(deposits),
            "matchingDepositRequests":[{"pubkey":d["pubkey"],"index":d.get("index"),"amount":d["amount"]} for d in deposits if d["pubkey"].lower() in keys],
            "legacyDepositCount":len(legacy),
            "matchingLegacyDeposits":[d["data"]["pubkey"] for d in legacy if d["data"]["pubkey"].lower() in keys]}

def inspect(url,height,keys):
    ask=lambda m,p:rpc(url,m,p)
    genesis=beacon("/eth/v1/beacon/genesis")
    if ask("eth_chainId",[])!=hex(31340) or ask("eth_getBlockByNumber",["0x0",False])["hash"]!=GENESIS or genesis["genesis_validators_root"]!=BEACON_ROOT:
        raise ValueError("wrong original network")
    spec=beacon("/eth/v1/config/spec")
    seconds=int(spec["SECONDS_PER_SLOT"]); slots=int(spec["SLOTS_PER_EPOCH"])
    start=int(genesis["genesis_time"])
    block=ask("eth_getBlockByNumber",[hex(height),False])
    if not isinstance(block,dict): raise ValueError("deposit block missing")
    timestamp=int(block["timestamp"],16)
    slot,remainder=divmod(timestamp-start,seconds)
    if slot<0 or remainder: raise ValueError("execution timestamp not aligned to beacon slot")
    sync=beacon("/eth/v1/node/syncing")
    checkpoints=beacon("/eth/v1/beacon/states/head/finality_checkpoints")
    heads={}
    for tag in ("latest","safe","finalized"):
        b=ask("eth_getBlockByNumber",[tag,False])
        heads[tag]=None if b is None else {"height":int(b["number"],16),"hash":b["hash"],"timestamp":int(b["timestamp"],16)}
    consensus={}
    for tag in (str(slot),"head",checkpoints["finalized"]["root"]):
        item=optional("/eth/v2/beacon/blocks/"+tag)
        if item["available"]:
            consensus[tag]=payload_summary(item["data"],keys)
        else: consensus[tag]=item
    pending=optional("/eth/v1/beacon/states/head/pending_deposits")
    if pending["available"]:
        rows=pending["data"]
        pending={"available":True,"count":len(rows),"matching":[{"pubkey":d["pubkey"],"slot":d.get("slot"),"amount":d["amount"]} for d in rows if d["pubkey"].lower() in keys]}
    target=consensus[str(slot)]
    finalized_payload=consensus[checkpoints["finalized"]["root"]]
    result={"chainId":31340,"wallclockSlot":int((time.time()-start)//seconds),
        "headSlot":int(sync["head_slot"]),"slotsPerEpoch":slots,"secondsPerSlot":seconds,
        "sync":sync,"checkpoints":checkpoints,"executionHeads":heads,
        "depositExecutionBlock":{"height":height,"hash":block["hash"],"timestamp":timestamp,
            "expectedBeaconSlot":slot,"expectedBeaconEpoch":slot//slots,"requestsHash":block.get("requestsHash")},
        "depositBlockMatchesBeaconPayload":target.get("executionHash")==block["hash"],
        "beaconBlocks":consensus,"pendingDeposits":pending,
        "finalizedBeaconPayloadMatchesELFinalized":finalized_payload.get("executionHash")==((heads["finalized"] or {}).get("hash")),
        "spec":{k:spec.get(k) for k in ("ELECTRA_FORK_EPOCH","ELECTRA_FORK_VERSION","ETH1_FOLLOW_DISTANCE","SECONDS_PER_ETH1_BLOCK","EPOCHS_PER_ETH1_VOTING_PERIOD","MAX_PENDING_DEPOSITS_PER_EPOCH","MIN_ACTIVATION_BALANCE","MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA","MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT")},
        "validators":beacon("/eth/v1/beacon/states/head/validators?"+ "&".join("id="+k for k in sorted(keys))),
        "stateChanged":False}
    if ask("eth_getBlockByNumber",[hex(height),False])["hash"]!=block["hash"]:
        raise ValueError("deposit anchor changed during audit")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--height",type=int,required=True)
    p.add_argument("--pubkey",action="append",required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    try: print(json.dumps(inspect(a.rpc,a.height,{k.lower() for k in a.pubkey}),indent=2,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError) as exc: p.exit(2,"R359_AUDIT_REFUSED: "+str(exc)+"\n")
if __name__=="__main__": main()
