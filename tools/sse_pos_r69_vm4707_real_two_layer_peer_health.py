#!/usr/bin/env python3
"""R69 VM4707: READ-ONLY real non-signing EL+CL post-launch observations.

No Docker mutation, no signer/wallet/JWT, no network/peer-changing RPC.
Reads exact Docker process state and two localhost APIs only.
Zero peer or unavailable API is reported (never fabricated as success).
Run only on the already created R59/R68 observer, not on original VM4706.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error

import sse_pos_r59_native_ipv6_observer as r59
import sse_pos_r68_vm4707_real_native_observer_join as r68

MAX_RESPONSE_BYTES=50000
EL="http://127.0.0.1:28545/"
BN="http://127.0.0.1:25052"
API_PATHS=(
    "/eth/v1/beacon/genesis",
    "/eth/v1/node/peer_count",
    "/eth/v1/node/syncing",
    "/eth/v1/beacon/headers/head",
    "/eth/v1/beacon/states/head/finality_checkpoints",
)

class R69Refused(ValueError):
    pass

def docker_state(name:str)->dict:
    if name not in (r59.EL,r59.BN):
        raise R69Refused("unreviewed Docker container name")
    try:
        process=subprocess.run(
            ["sudo","-n","docker","inspect","--format",
             "{{json .State}}",name],capture_output=True,text=True,
            check=False,timeout=15,
        )
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise R69Refused("Docker status inspection unavailable") from exc
    if process.returncode:
        raise R69Refused("expected original-chain non-signing observer container missing")
    try:
        state=json.loads(process.stdout)
    except ValueError as exc:
        raise R69Refused("Docker state JSON unreadable") from exc
    if not isinstance(state,dict):
        raise R69Refused("Docker state object malformed")
    return {
        "running":state.get("Running") is True,
        "exitCode":state.get("ExitCode") if type(state.get("ExitCode")) is int else None,
        "oomKilled":state.get("OOMKilled") is True,
        "restarting":state.get("Restarting") is True,
    }

def get_local_json(url:str, method:str="GET", json_body:dict|None=None)->dict:
    if (method=="GET" and url not in {BN+x for x in API_PATHS}) and (
        method!="POST" or url!=EL
    ):
        raise R69Refused("unreviewed remote API endpoint")
    if method=="POST":
        if not isinstance(json_body,dict) or json_body.get("method") not in (
            "eth_chainId","eth_blockNumber","net_peerCount","eth_syncing"
        ):
            raise R69Refused("unreviewed RPC method")
        data=json.dumps(json_body,separators=(",",":")).encode()
    else:
        data=None
    request=urllib.request.Request(
        url,method=method,data=data,headers={
            "Accept":"application/json","Content-Type":"application/json"
        }
    )
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request,timeout=5) as resp:
            if resp.status!=200:
                raise R69Refused("local client API returned non-200")
            body=resp.read(MAX_RESPONSE_BYTES+1)
    except (OSError,urllib.error.URLError,ValueError) as exc:
        raise R69Refused("local client API unavailable") from exc
    if len(body)>MAX_RESPONSE_BYTES:
        raise R69Refused("local client API response too large")
    try:
        obj=json.loads(body)
    except (ValueError,UnicodeError) as exc:
        raise R69Refused("local client API returned malformed JSON") from exc
    if not isinstance(obj,dict):
        raise R69Refused("local client API JSON schema invalid")
    return obj

def rpc(method:str)->object:
    response=get_local_json(
        EL,"POST",{"jsonrpc":"2.0","id":1,"method":method,"params":[]}
    )
    if response.get("jsonrpc")!="2.0" or response.get("id")!=1 or (
        "error" in response or "result" not in response
    ):
        raise R69Refused("requested local EL RPC not exposed")
    return response["result"]

def beacon(path:str)->dict:
    result=get_local_json(BN+path)
    data=result.get("data")
    if not isinstance(data,dict):
        raise R69Refused("local BN REST returned missing data")
    return data

def uint(value:object, *, hex_result:bool=False)->int:
    if hex_result:
        if not isinstance(value,str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}",value):
            raise R69Refused("invalid hexadecimal ETH quantity")
        return int(value,16)
    if not isinstance(value,str) or not re.fullmatch(r"[0-9]{1,16}",value):
        raise R69Refused("invalid Beacon numeric quantity")
    return int(value)

def observed()->dict:
    iface,host_ipv6=r59.overlay_ip()
    out={
        "schema":"SSE_R69_REAL_VM4707_NON_SIGNING_ETHEREUM_EL_CL_POST_LAUNCH_V1",
        "mode":"read_only_actual_non_signing_vm4707",
        "actualVm4707OpenOverlayIpv6":host_ipv6,
        "actualVm4707OpenOverlayInterface":iface,
        "executionDocker":docker_state(r59.EL),
        "beaconDocker":docker_state(r59.BN),
        "originalR67FinalizedReferenceEpoch":r68.SOURCE_OBSERVED_FINALIZED_EPOCH,
        "originalR67FinalizedReferenceRoot":r68.SOURCE_OBSERVED_FINALIZED_ROOT,
        "outsideProviderP2pSyncAndDistributedValidatorsNotYetProven":True,
        "noDockerOrBlockchainMutations":True,
        "noValidatorKeysOrEngineJwtRead":True,
    }
    for kind,fn in (
        ("execution",lambda:{
            "chainId":uint(rpc("eth_chainId"),hex_result=True),
            "latestBlock":uint(rpc("eth_blockNumber"),hex_result=True),
            "nativePeerCount":uint(rpc("net_peerCount"),hex_result=True),
            "ethSyncing":rpc("eth_syncing"),
        }),
        ("beacon",lambda:{
            "genesisTime":beacon("/eth/v1/beacon/genesis").get("genesis_time"),
            "connectedPeers":uint(beacon("/eth/v1/node/peer_count")["connected"]),
            "isSyncing":beacon("/eth/v1/node/syncing").get("is_syncing"),
            "headSlot":uint(beacon("/eth/v1/beacon/headers/head")["header"]["message"]["slot"]),
            "finalizedEpoch":uint(beacon("/eth/v1/beacon/states/head/finality_checkpoints")["finalized"]["epoch"]),
            "finalizedRoot":beacon("/eth/v1/beacon/states/head/finality_checkpoints")["finalized"]["root"],
        }),
    ):
        try:
            data=fn()
            out[kind]={"apiStatus":"reachable",**data}
            if kind=="execution":
                out[kind]["chain31340Verified"]=data["chainId"]==31340
            else:
                epoch=data["finalizedEpoch"]
                root=data["finalizedRoot"]
                if not isinstance(root,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",root):
                    raise R69Refused("Beacon finalized root malformed")
                out[kind]["epoch122SameCheckpointIfAtEpoch122"]=(
                    root.lower()==r68.SOURCE_OBSERVED_FINALIZED_ROOT.lower()
                    if epoch==r68.SOURCE_OBSERVED_FINALIZED_EPOCH else None
                )
        except (R69Refused,KeyError,TypeError,ValueError):
            out[kind]={"apiStatus":"unavailable_or_unexpected_schema"}
    el=out["execution"]
    bn=out["beacon"]
    out["bothClientsRunning"]=(out["executionDocker"]["running"] and out["beaconDocker"]["running"])
    out["bothNativePeerCountsPositive"]=(
        isinstance(el.get("nativePeerCount"),int) and el["nativePeerCount"]>0 and
        isinstance(bn.get("connectedPeers"),int) and bn["connectedPeers"]>0
    )
    out["realIndependentSameEpochFinalizedRootAgreementStillNeedsOwnerComparison"]=True
    return out

def main()->int:
    p=argparse.ArgumentParser(description="read-only true VM4707 non-signing Ethereum P2P and sync status")
    p.add_argument("--audit",action="store_true")
    args=p.parse_args()
    if not args.audit:
        print("R69_ONLY_READONLY_AUDIT_ALLOWED",file=sys.stderr)
        return 2
    try:
        print(json.dumps(observed(),sort_keys=True,indent=2))
        return 0
    except (R69Refused,r59.R59Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R69_VM4707_READONLY_HEALTH_REFUSED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
