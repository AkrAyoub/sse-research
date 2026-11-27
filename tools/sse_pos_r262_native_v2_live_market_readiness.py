#!/usr/bin/env python3
"""R262: one-shot, public, READ-ONLY live native V2 market readiness.

Runs on actual VM4707 loopback Besu. No keys, sends, account creation,
funding, Docker or Beacon changes; NO POLLING. Verifies exact real
deployed runtime SHA256, current canonical receipt, market+ledger links,
Solidity compiler nonimmutable runtime byte parity and Solidity-known
immutables at latest state. Independently reports execution finality.
Also reads actual onchain monitor/request/lease counters and outstanding
native escrow/liability balances: these are real role progress, not claims
of independent physical operators or SLA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from eth_utils import keccak

from sse_pos_r206_adaptive_v2_deployment_audit import (
    rpc, selector, _read_address as read_address,
)
from sse_pos_r247_v2_compiled_abi_parity import load_artifact
from sse_pos_r260_v2_readonly_finalized_deployment_audit import (
    TX_HASH, RPC, BOND_WEI, CHAIN, GENESIS,
    APPROVED_MARKET_ADDRESS as MARKET,
    EXPECTED_MARKET_RUNTIME_BYTES as M_BYTES,
    EXPECTED_LEDGER_RUNTIME_BYTES as L_BYTES,
    verify_compiler_runtime, require_slot_value, quantity,
)

EXPECTED_MARKET_SHA256="aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261"
EXPECTED_LEDGER="0x6635849b77f037fab611736612d7d3493dc650ff"
EXPECTED_LEDGER_SHA256="3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d"

MARKET_STATE=(
    "activeMonitorCount()",
    "nextRequestId()",
    "nextLeaseId()",
    "totalServiceEscrow()",
    "totalPendingMonitorFunding()",
    "totalMonitorBonds()",
    "totalWithdrawable()",
)
LEDGER_STATE=(
    "totalUnspentReserves()",
    "totalWithdrawableCredits()",
)


class Refused(ValueError):
    pass


def uint_call(url,address,signature,*,block="latest",transport=rpc):
    if signature not in MARKET_STATE + LEDGER_STATE + ("minimumBond()",):
        raise Refused("unapproved read-only state getter")
    data="0x"+keccak(text=signature)[:4].hex()
    raw=transport(url,"eth_call",[{"to":address,"data":data},block])
    if (type(raw) is not str or len(raw)!=66 or
        not raw.startswith("0x") or
        any(ch not in "0123456789abcdefABCDEF" for ch in raw[2:])):
        raise Refused("bad ABI uint256 output for "+signature)
    return int(raw,16)


def code_sha256(raw,name):
    if (type(raw) is not str or len(raw)<4 or
        not raw.startswith("0x") or len(raw)%2 or
        any(ch not in "0123456789abcdefABCDEF" for ch in raw[2:])):
        raise Refused(name+" live runtime missing")
    return hashlib.sha256(bytes.fromhex(raw[2:])).hexdigest()


def status(m_artifact,l_artifact,*,transport=rpc):
    ask=lambda method,params:transport(RPC,method,params)
    if quantity(ask("eth_chainId",[]),"chainId")!=CHAIN:
        raise Refused("not original chain31340")
    genesis=ask("eth_getBlockByNumber",["0x0",False])
    if (type(genesis) is not dict or
        str(genesis.get("hash","")).lower()!=GENESIS):
        raise Refused("original execution genesis mismatch")
    latest=ask("eth_getBlockByNumber",["latest",False])
    final=ask("eth_getBlockByNumber",["finalized",False])
    if type(latest) is not dict or type(final) is not dict:
        raise Refused("latest/finalized block unavailable")
    head=quantity(latest.get("number"),"latest number")
    finalized=quantity(final.get("number"),"finalized number")
    if finalized>head:
        raise Refused("execution finality height ahead of head")
    receipt=ask("eth_getTransactionReceipt",[TX_HASH])
    if type(receipt) is not dict:
        raise Refused("original deployment receipt missing")
    included=quantity(receipt.get("blockNumber"),"deployment block")
    if (quantity(receipt.get("status"),"deployment status")!=1 or
        str(receipt.get("transactionHash","")).lower()!=TX_HASH or
        str(receipt.get("contractAddress","")).lower()!=MARKET.lower()):
        raise Refused("actual owner-approved deployment receipt mismatch")
    canonical=ask("eth_getBlockByNumber",[hex(included),False])
    if (type(canonical) is not dict or
        str(canonical.get("hash","")).lower()!=
            str(receipt.get("blockHash","")).lower()):
        raise Refused("deployment receipt is not on canonical chain")

    votes=read_address(ask("eth_call",[
        {"to":MARKET,"data":selector("votes()")},"latest"]))
    if votes!=EXPECTED_LEDGER:
        raise Refused("onchain market votes() != observed real ledger")
    parent=read_address(ask("eth_call",[
        {"to":votes,"data":selector("settlement()")},"latest"]))
    bond=uint_call(RPC,MARKET,"minimumBond()",transport=transport)
    if parent!=MARKET.lower() or bond!=BOND_WEI:
        raise Refused("onchain mutual immutable link/bond mismatch")

    mc=ask("eth_getCode",[MARKET,"latest"])
    lc=ask("eth_getCode",[votes,"latest"])
    if (code_sha256(mc,"market")!=EXPECTED_MARKET_SHA256 or
        code_sha256(lc,"ledger")!=EXPECTED_LEDGER_SHA256):
        raise Refused("ACTUAL LIVE runtime SHA256 differs from owner's R261 proof")
    m=verify_compiler_runtime(m_artifact,mc,M_BYTES,"market")
    l=verify_compiler_runtime(l_artifact,lc,L_BYTES,"ledger")
    require_slot_value(m,int(votes,16),"market.votes")
    require_slot_value(m,BOND_WEI,"market.minimumBond")
    require_slot_value(l,int(MARKET,16),"ledger.settlement")

    market_readings={k[:-2]:uint_call(RPC,MARKET,k,transport=transport)
                     for k in MARKET_STATE}
    ledger_readings={k[:-2]:uint_call(RPC,votes,k,transport=transport)
                     for k in LEDGER_STATE}
    if (market_readings["nextRequestId"]<1 or
        market_readings["nextLeaseId"]<1):
        raise Refused("invalid V2 live request/lease state")
    market_balance=quantity(ask("eth_getBalance",[MARKET,"latest"]),"market balance")
    ledger_balance=quantity(ask("eth_getBalance",[votes,"latest"]),"ledger balance")
    market_liability=sum(market_readings[x] for x in (
        "totalServiceEscrow","totalPendingMonitorFunding",
        "totalMonitorBonds","totalWithdrawable"))
    ledger_liability=sum(ledger_readings.values())
    if market_balance<market_liability or ledger_balance<ledger_liability:
        raise Refused("market/ledger balance does NOT cover public escrow liabilities")
    if finalized>=included:
        readiness="FINALITY_HEIGHT_COVERS_DEPLOYMENT_R260_R206_STILL_REQUIRED"
    else:
        readiness="LIVE_MARKET_READABLE_FINALITY_NOT_YET_COVERED"
    return {
        "schema":"SSE_R262_NATIVE_V2_READONLY_REAL_MARKET_PROGRESS_V1",
        "chainId":CHAIN,"originalGenesisVerified":True,
        "deploymentTransactionHash":TX_HASH,
        "deploymentReceiptSuccessfulAndCurrentlyCanonical":True,
        "deploymentBlock":included,
        "latestExecutionBlock":head,
        "finalizedExecutionBlock":finalized,
        "remainingBlocksUntilDeploymentFinality":max(0,included-finalized),
        "deploymentIncludedAtFinalizedExecutionHeight":finalized>=included,
        "formalR260R206FinalizedAuditRunByThisTool":False,
        "market":MARKET,"ledger":votes,
        "marketRuntimeSha256":m["runtimeSha256"],
        "ledgerRuntimeSha256":l["runtimeSha256"],
        "actualSolcNonimmutableCodeAndThreeKnownImmutablesMatch":True,
        "minimumMonitorBondWei":str(BOND_WEI),
        "marketState":market_readings,
        "ledgerState":ledger_readings,
        "marketBalanceWei":str(market_balance),
        "marketLiabilitiesWei":str(market_liability),
        "ledgerBalanceWei":str(ledger_balance),
        "ledgerLiabilitiesWei":str(ledger_liability),
        "rolesRealTransactionsNeededForAnE2EService":(
            ">=4 separately controlled bonded eligible monitor accounts "
            "for a fault-tolerance-one committee, plus consumer and "
            "provider EOAs and genuine resources; no addresses inferred"
        ),
        "readiness":readiness,
        "transactionsSent":False,
        "walletKeysRead":False,
        "independentPhysicalOperatorsVerified":False,
        "realResourceServiceSlaVerified":False,
    }


def main(argv=None):
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc",choices=(RPC,),required=True)
    args=parser.parse_args(argv)
    try:
        market=load_artifact(root/"out/SSEAdaptiveMarketV2.sol/SSEAdaptiveMarketV2.json")
        ledger=load_artifact(root/"out/SSEAdaptiveVoteLedger.sol/SSEAdaptiveVoteLedger.json")
        result=status(market,ledger)
        print(json.dumps(result,indent=2,sort_keys=True))
        print("R262_REAL_V2_LIVE_ROLE_READINESS_READONLY_NO_TX=true")
        return 0
    except (Refused,ValueError,TypeError,KeyError,OSError) as exc:
        print("R262_REAL_V2_READINESS_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
