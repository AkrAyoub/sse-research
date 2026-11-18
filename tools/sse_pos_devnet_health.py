#!/usr/bin/env python3
"""Read-only EL+Beacon observations for our OWN Ethereum PoS chain 31339.

No access keys, no user approvals, no wallet actions. The Beacon validator
endpoint reports consensus membership from an actual CL client, not an SSE
role request, Tailscale device, or QBFT vote. RPC endpoints must be 127.0.0.1
HTTP tunnel or HTTPS; physical RPC/validator independence requires separate
evidence and cannot be inferred from multiple URLs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

CHAIN=31339
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
PUB=re.compile(r"0x[0-9a-fA-F]{96}\Z")
ZERO="0x"+"00"*32
MAX_JSON=1_000_000


class HealthError(ValueError):
    pass


def safe_url(url:str)->str:
    if type(url) is not str or len(url)>400:
        raise HealthError("invalid or oversized RPC URL")
    u=urlsplit(url)
    if (u.username or u.password or u.query or u.fragment or u.path not in ("","/")
            or u.hostname is None or u.port is None
            or u.scheme not in ("http","https")):
        raise HealthError("no remote cleartext, credentials or RPC path accepted")
    if u.scheme=="http" and u.hostname not in ("127.0.0.1","localhost","::1"):
        raise HealthError("remote RPC needs HTTPS or trusted local SSH tunnel")
    if not 1<=u.port<=65535:
        raise HealthError("invalid RPC port")
    return url.rstrip("/")


def _request(url:str,method:str|None=None,params=None):
    headers={"Accept":"application/json"}
    if method is not None:
        body=json.dumps({"jsonrpc":"2.0","id":7,"method":method,
                         "params":params or []}).encode()
        headers["Content-Type"]="application/json"
        req=Request(url,data=body,headers=headers,method="POST")
    else:
        req=Request(url,headers=headers,method="GET")
    try:
        with urlopen(req,timeout=6) as response:
            if response.status != 200:
                raise HealthError("RPC returned non-200")
            raw=response.read(MAX_JSON+1)
        if len(raw)>MAX_JSON:
            raise HealthError("oversized RPC result")
        result=json.loads(raw)
    except (OSError,UnicodeError,ValueError) as e:
        raise HealthError("RPC unavailable or invalid response") from e
    if type(result) is not dict:
        raise HealthError("RPC response is not an object")
    if method is not None:
        if (result.get("jsonrpc")!="2.0" or result.get("id")!=7
                or "error" in result or result.get("result") is None):
            raise HealthError("execution RPC returned error")
        return result["result"]
    return result


def observe(*,execution_url:str,beacon_url:str,expected_genesis:str|None=None,
            validator_pubkey:str|None=None,require_finality:bool=False,
            execution_call=None,beacon_get=None)->dict:
    el=safe_url(execution_url)
    cl=safe_url(beacon_url)
    if (type(require_finality) is not bool
            or expected_genesis is not None and
            (type(expected_genesis) is not str or
             not HASH.fullmatch(expected_genesis) or int(expected_genesis,16)==0)
            or validator_pubkey is not None and
            (type(validator_pubkey) is not str or not PUB.fullmatch(validator_pubkey))):
        raise HealthError("invalid pinned genesis, validator BLS key or finality policy")
    execution_call=execution_call or (lambda method,params:_request(el,method,params))
    beacon_get=beacon_get or (lambda path:_request(cl+path))
    chain=execution_call("eth_chainId",[])
    if chain!=hex(CHAIN):
        raise HealthError("wrong chain ID, would risk Anvil/QBFT conflict")
    genesis=execution_call("eth_getBlockByNumber",["0x0",False])
    if (type(genesis) is not dict or type(genesis.get("hash")) is not str
            or not HASH.fullmatch(genesis["hash"])
            or int(genesis["hash"],16)==0):
        raise HealthError("missing validated execution genesis")
    ghash=genesis["hash"].lower()
    if expected_genesis is not None and ghash!=expected_genesis.lower():
        raise HealthError("genesis differs from pinned owner-independent manifest")
    height=execution_call("eth_blockNumber",[])
    if (type(height) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+\Z",height)
            or int(height,16)==0):
        raise HealthError("execution chain has not produced any block")
    beacon_genesis=beacon_get("/eth/v1/beacon/genesis")
    bg=beacon_genesis.get("data") if type(beacon_genesis) is dict else None
    if (type(bg) is not dict or
            not re.fullmatch(r"[0-9]+\Z",str(bg.get("genesis_time","")))
            or not isinstance(bg.get("genesis_validators_root"),str)
            or not HASH.fullmatch(bg["genesis_validators_root"])):
        raise HealthError("invalid beacon genesis")
    header=beacon_get("/eth/v1/beacon/headers/head")
    hd=header.get("data") if type(header) is dict else None
    msg=hd.get("header",{}).get("message",{}) if isinstance(hd,dict) else {}
    slot=msg.get("slot")
    if (type(slot) is not str or not slot.isdecimal()
            or int(slot)<1):
        raise HealthError("Beacon client has no valid head slot")
    check=beacon_get("/eth/v1/beacon/states/head/finality_checkpoints")
    fc=check.get("data") if type(check) is dict else None
    fin=fc.get("finalized") if type(fc) is dict else None
    if (type(fin) is not dict or type(fin.get("epoch")) is not str
            or not fin["epoch"].isdecimal() or type(fin.get("root")) is not str
            or not HASH.fullmatch(fin["root"])):
        raise HealthError("invalid consensus finality data")
    final_epoch=int(fin["epoch"])
    finalized=final_epoch>=1 and fin["root"].lower()!=ZERO
    if require_finality and not finalized:
        raise HealthError("PoS chain has not finalized an epoch yet")
    membership=None
    if validator_pubkey is not None:
        v=beacon_get("/eth/v1/beacon/states/head/validators/"+validator_pubkey)
        data=v.get("data") if type(v) is dict else None
        if type(data) is not dict or type(data.get("status")) is not str:
            raise HealthError("validator not found in actual Beacon registry")
        status=data["status"]
        # Do NOT confuse pending inclusion or BLS key possession with
        # active block-proposal and attestation eligibility.
        membership={
            "validatorPubkey":validator_pubkey,
            "observedBeaconStatus":status,
            "activeConsensusValidatorObserved":status.startswith("active_"),
            "activationDoesNotDependOnSSEAdministrator":True,
            "physicalIndependenceProved":False,
            "stakingDepositVerifiedByThisTool":False,
        }
    return {
        "schema":"SSE_OWN_POS_NETWORK_OBSERVED_V1",
        "chainId":CHAIN,"executionGenesisHash":ghash,
        "executionGenesisPinned":expected_genesis is not None,
        "executionBlockHeight":int(height,16),
        "beaconGenesisValidatorsRoot":bg["genesis_validators_root"].lower(),
        "beaconHeadSlot":int(slot),
        "finalizedEpoch":final_epoch,"finalityObserved":finalized,
        "validatorMembership":membership,
        "ethereumMainnetUsed":False,"realEthSpent":False,
        "sseAdministratorValidatorApprovalNeeded":False,
        "externalPeerReachabilityVerified":False,
        "physicalHostIndependenceVerified":False,
        "testEthHasRealEconomicSybilResistance":False,
        "ethereumTransactionsSent":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only own Ethereum PoS chain / Beacon role checker")
    p.add_argument("--execution-url",required=True)
    p.add_argument("--beacon-url",required=True)
    p.add_argument("--expected-genesis")
    p.add_argument("--validator-pubkey")
    p.add_argument("--require-finality",action="store_true")
    a=p.parse_args(argv)
    try:
        result=observe(execution_url=a.execution_url,beacon_url=a.beacon_url,
                       expected_genesis=a.expected_genesis,
                       validator_pubkey=a.validator_pubkey,
                       require_finality=a.require_finality)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (HealthError,ValueError,TypeError,OSError) as exc:
        print("SSE_POS_HEALTH_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
