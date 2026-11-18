#!/usr/bin/env python3
"""Read-only observed monitor candidate/bond eligibility on live SSE chain.

Current SSE OpenMonitorCommittee grants vote authority ONLY by assignment.
A bonded active monitor is *globally eligible*, not necessarily authorized to
attest a particular provider/consumer lease. Requires at least two pinned RPC
views to reduce accidental misconfiguration; two URL strings alone do not
prove distinct nodes or economic independence. No stake/funding tx is sent.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from sse_qbft_readiness import rpc as chain_rpc, safe_rpc
from sse_vm_join_preflight import rpc_query as app_rpc
from sse_challenge import keccak256

HEX=re.compile(r"0x[0-9a-fA-F]+\Z")
ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")


class MonitorAuthorityError(ValueError):
    pass


def _call_data(signature: str, account: str | None = None) -> str:
    selector="0x"+keccak256(signature.encode("ascii"))[:4].hex()
    return selector + (int(account,16).to_bytes(32,"big").hex() if account else "")


def monitor_eligibility(urls, *, chain_id:int, genesis_hash:str, pool:str,
                        wallet:str, chain_call=chain_rpc, contract_call=app_rpc):
    if (type(urls) is not list or not 2<=len(urls)<=8
            or len(set(urls))!=len(urls) or any(type(u) is not str for u in urls)):
        raise MonitorAuthorityError("two or more independent trusted RPC views required")
    if (type(chain_id) is not int or chain_id!=31338
            or type(genesis_hash) is not str or not HASH.fullmatch(genesis_hash)
            or int(genesis_hash,16)==0
            or type(pool) is not str or not ADDRESS.fullmatch(pool)
            or int(pool,16)==0
            or type(wallet) is not str or not ADDRESS.fullmatch(wallet)
            or int(wallet,16)==0):
        raise MonitorAuthorityError("invalid pinned chain, committee or monitor wallet")
    observations=[]
    for url in urls:
        safe_rpc(url)
        if chain_call(url,"eth_chainId",[]) != hex(chain_id):
            raise MonitorAuthorityError("RPC not on approved chain ID")
        genesis=chain_call(url,"eth_getBlockByNumber",["0x0",False])
        if (type(genesis) is not dict or type(genesis.get("hash")) is not str
                or genesis["hash"].lower()!=genesis_hash.lower()):
            raise MonitorAuthorityError("wrong genesis for monitor evidence")
        code=contract_call(url,"eth_getCode",[pool,"latest"])
        if (type(code) is not str or not HEX.fullmatch(code) or
                len(code)<4 or int(code,16)==0):
            raise MonitorAuthorityError("OpenMonitorCommittee not deployed at given address")
        raw=contract_call(url,"eth_call",[{
            "to":pool,"data":_call_data("candidates(address)",wallet)
        },"latest"])
        minraw=contract_call(url,"eth_call",[{
            "to":pool,"data":_call_data("minimumBond()")
        },"latest"])
        if (type(raw) is not str or not HEX.fullmatch(raw)
                or len(raw)<2+6*64 or (len(raw)-2)%64!=0
                or type(minraw) is not str or not HEX.fullmatch(minraw)
                or len(minraw)!=66):
            raise MonitorAuthorityError("candidate or minimumBond contract response invalid")
        fields=[int(raw[2+i*64:2+(i+1)*64],16) for i in range(6)]
        if fields[4] not in (0,1):
            raise MonitorAuthorityError("candidate active flag is not ABI-encoded bool")
        minimum=int(minraw,16)
        if minimum<1:
            raise MonitorAuthorityError("minimum monitor bond must be positive")
        observations.append((code.lower(),fields[0],fields[4],minimum))
    if len(set(observations))!=1:
        raise MonitorAuthorityError("independent views disagree on committee state")
    _,bond,active,minimum=observations[0]
    eligible=bool(active) and bond>=minimum
    return {
        "kind":"SSE_MONITOR_CANDIDATE_CHAIN_EVIDENCE_V1",
        "chainId":chain_id,
        "genesisHash":genesis_hash.lower(),
        "committee":pool.lower(),
        "candidate":wallet.lower(),
        "observedRpcViewCount":len(urls),
        "observedBondWei":bond,
        "minimumBondWei":minimum,
        "observedCandidateActive":bool(active),
        "globallyBondEligibleObserved":eligible,
        "authorizationForAnySpecificLeaseProved":False,
        "independenceFromConsumerAndProviderProved":False,
        "selectedMonitorForLease":False,
        "walletPrivateKeyAccessed":False,
        "ethereumTransactionsSent":False,
        "physicalIndependenceProved":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Inspect public monitor registration only; no lease voting")
    p.add_argument("--rpc-url",action="append",required=True)
    p.add_argument("--genesis-hash",required=True)
    p.add_argument("--committee",required=True)
    p.add_argument("--wallet",required=True)
    a=p.parse_args(argv)
    try:
        result=monitor_eligibility(a.rpc_url,chain_id=31338,
                                   genesis_hash=a.genesis_hash,
                                   pool=a.committee,wallet=a.wallet)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (MonitorAuthorityError,ValueError,TypeError,OSError) as exc:
        print("SSE_MONITOR_ROLE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
