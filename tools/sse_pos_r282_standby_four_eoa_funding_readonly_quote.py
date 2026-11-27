#!/usr/bin/env python3
"""R282: fixed four ACTUAL standby role EOAs, TEST ETH quote; READ-ONLY.

No keystore reads, approvals, signing, raw TX, R267 attempt marker
creation/retries, privileged Docker, native consensus or automatic grants.
No new funding authority; actual sending requires separate bounded approval
and a separately audited one-by-one one-shot sender. Monitor2 nonce3 must
first be genuinely canonical and finalized on original chain31340.
"""
from __future__ import annotations

import argparse
import json
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as local_rpc
from sse_pos_r260_v2_readonly_finalized_deployment_audit import quantity
from sse_pos_r267_vm4707_one_by_one_role_funding import (
    APP, GAS_LIMIT, GAS_PRICE, RPC,
)
from sse_pos_r276_vm4707_monitor1_funding_attempt_forensics import (
    observe as original_monitor2_exact_forensics,
)

FUNDING_AMOUNT_WEI=5_000_000_000_000_000
APPROVED_ORIGINAL_ROLE_NONCES=4
RECIPIENTS=(
    ("vm4711-monitor","0x1a89D81288522912643e15D8e06a2a7D9dc4bc08"),
    ("vm4712-monitor","0x30dc70daA83B2D4199B98Cf1b93f31f1BA80f0Aa"),
    ("vm4713-monitor","0x001f529E8d17A243078631100CA7Ad93c001Ea2d"),
    ("vm4714-provider","0x016B91ED50Ec350e600327C4287F2ED882E0Cf66"),
)
MAX_TOTAL_WEI=len(RECIPIENTS)*(FUNDING_AMOUNT_WEI+GAS_LIMIT*GAS_PRICE)

class Refused(ValueError):
    pass


def preview(*,transport=local_rpc,prior_fn=original_monitor2_exact_forensics):
    # R278 independently verifies original native genesis, known signed
    # monitor2 hash from read-only public marker, exact tx, receipt & finality.
    try:
        prior=prior_fn(role="monitor-2",transport=transport)
    except (ValueError,OSError,TypeError,KeyError) as exc:
        raise Refused("original monitor2 exact public previous-attempt audit unavailable") from exc
    if (type(prior) is not dict or prior.get("originalGenesisVerified") is not True
        or prior.get("chainId")!=31340 or
        prior.get("role")!="monitor-2"):
        raise Refused("wrong original chain or monitor2 predecessor identity")
    state=prior.get("transactionStatus")
    if state!="MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED":
        return {
            "schema":"SSE_R282_STANDBY_ROLE_FUNDING_NO_SEND_PREVIEW_V1",
            "chainId":31340,
            "status":"MONITOR2_NOT_FINALIZED_NO_STANDBY_FUNDING_QUOTE",
            "monitor2TransactionStatus":state,
            "previousMonitor2AttemptPreserved":True,
            "plannedRecipientCount":len(RECIPIENTS),
            "plannedValuePerRecipientWei":str(FUNDING_AMOUNT_WEI),
            "plannedMaximumFourTransactionDebitsWei":str(MAX_TOTAL_WEI),
            "realRpcGasBalanceAndRecipientQuoteVerified":False,
            "newStandbyFundingAuthorized":False,
            "walletOrPasswordRead":False,
            "transactionsSignedOrSent":False,
        }
    if (prior.get("sourceLatestNonce")!=APPROVED_ORIGINAL_ROLE_NONCES
        or prior.get("sourcePendingNonce")!=APPROVED_ORIGINAL_ROLE_NONCES
        or prior.get("allThreeApprovedRoleTransfersFinalized") is not True):
        raise Refused("source nonce or exact three-transfer finality changed")

    # Deny misconfigured or duplicate exact research EOA targets before RPC.
    addresses=[recipient.lower() for _,recipient in RECIPIENTS]
    if (len(set(addresses))!=len(addresses)
        or APP.lower() in addresses
        or any(len(addr)!=42 or not addr.startswith("0x")
               or any(c not in "0123456789abcdef" for c in addr[2:])
               for addr in addresses)):
        raise Refused("fixed four actual owner-created EOA addresses invalid")
    ask=lambda method,args:transport(RPC,method,args)
    if (quantity(ask("eth_getTransactionCount",[APP,"latest"]),"source latest nonce")
            !=APPROVED_ORIGINAL_ROLE_NONCES or
        quantity(ask("eth_getTransactionCount",[APP,"pending"]),"source pending nonce")
            !=APPROVED_ORIGINAL_ROLE_NONCES):
        raise Refused("source nonce changed; stop and re-review entire funding plan")
    if ask("eth_getCode",[APP,"latest"])!="0x":
        raise Refused("source account has unexpected code")
    price=quantity(ask("eth_gasPrice",[]),"actual gas price")
    head=ask("eth_getBlockByNumber",["latest",False])
    if type(head) is not dict:
        raise Refused("actual execution head missing")
    base=head.get("baseFeePerGas")
    if (price<=0 or price>GAS_PRICE or
        (base is not None and quantity(base,"base fee")>GAS_PRICE) or
        quantity(head.get("gasLimit"),"block gas limit")<GAS_LIMIT):
        raise Refused("live chain gas price/base fee or limit incompatible with quote")
    source_balance=quantity(ask("eth_getBalance",[APP,"latest"]),
                             "actual funding source latest wei")
    if source_balance<MAX_TOTAL_WEI:
        raise Refused("native app source cannot cover four grants and all capped gas")
    stages=[]
    for offset,(role,recipient) in enumerate(RECIPIENTS):
        if (ask("eth_getCode",[recipient,"latest"])!="0x" or
            quantity(ask("eth_getBalance",[recipient,"latest"]),"recipient balance")!=0 or
            quantity(ask("eth_getTransactionCount",[recipient,"pending"]),
                     "recipient pending nonce")!=0):
            raise Refused(role+" exact recipient not a clean unfunded EOA")
        estimate=quantity(ask("eth_estimateGas",[{
            "from":APP,"to":recipient,
            "value":hex(FUNDING_AMOUNT_WEI),"data":"0x"
        }]),"real simple EOA grant gas estimate")
        if estimate!=GAS_LIMIT:
            raise Refused(role+" real EOA gas estimate is not 21000")
        stages.append({
            "role":role,"recipient":recipient,
            "proposedSourceNonce":APPROVED_ORIGINAL_ROLE_NONCES+offset,
            "valueWei":str(FUNDING_AMOUNT_WEI),
            "gasLimit":GAS_LIMIT,"gasPriceCapWei":GAS_PRICE,
            "maxSingleDebitWei":str(FUNDING_AMOUNT_WEI+GAS_LIMIT*GAS_PRICE),
            "recipientRealRpcCleanAndUnfunded":True,
            "liveEstimatedGas":estimate,
        })
    return {
        "schema":"SSE_R282_STANDBY_ROLE_FUNDING_NO_SEND_PREVIEW_V1",
        "chainId":31340,"status":"READONLY_SCENARIO_QUOTE_ELIGIBLE_FOR_SEPARATE_APPROVAL",
        "source":APP,
        "exactPreviousThreeTransfersFinalized":True,
        "sourceNextNonce":APPROVED_ORIGINAL_ROLE_NONCES,
        "sourceLatestNativeBalanceWei":str(source_balance),
        "actualEthGasPriceWei":price,
        "proposedTransfers":stages,
        "maximumFourTransactionDebitsWei":str(MAX_TOTAL_WEI),
        "realRpcGasBalanceAndRecipientQuoteVerified":True,
        "newStandbyFundingAuthorized":False,
        "noNewEoaFundsSent":True,
        "walletOrPasswordRead":False,
        "transactionsSignedOrSent":False,
        "dockerOrValidatorChanged":False
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc",choices=(RPC,),required=True)
    a=parser.parse_args(argv)
    try:
        print(json.dumps(preview(),indent=2,sort_keys=True))
        print("R282_FOUR_REAL_STANDBY_ROLE_FUNDING_PLAN_READONLY_NO_SIGNING_NO_SEND=true")
        return 0
    except (Refused,ValueError,OSError,TypeError,KeyError,OverflowError) as exc:
        print("R282_FOUR_STANDBY_NATIVE_QUOTE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
