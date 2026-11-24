#!/usr/bin/env python3
"""R276: one-shot READ-ONLY forensic check of consumed R267 Monitor 1 marker.

READS ONLY the public-transaction metadata from the existing, private,
owner-mode-0600 R267 monitor-1 attempt marker. Never opens a keystore,
prompts for a password, signs, broadcasts, retries, deletes or alters
a marker. Never assumes an absent RPC tx was never broadcast. Never
releases nonce 3 funding without exact successful finalized receipt.
"""
from __future__ import annotations

import argparse
import json
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as local_rpc
from sse_pos_r260_v2_readonly_finalized_deployment_audit import (
    CHAIN, GENESIS, RPC, quantity,
)
from sse_pos_r267_vm4707_one_by_one_role_funding import (
    APP, GAS_LIMIT, GAS_PRICE, RECIPIENTS, read_marker,
)


class Refused(ValueError):
    pass


def observe(*,transport=local_rpc,marker_reader=read_marker):
    """One owner VM4707 forensic snapshot, never any JSON-RPC mutator."""
    try:
        doc=marker_reader("monitor-1")
    except (OSError,ValueError) as exc:
        raise Refused("existing public monitor-1 attempt marker missing/invalid") from exc
    idx=1
    expected_role,recipient,value=RECIPIENTS[idx]
    expected_nonce=idx+1
    if (type(doc) is not dict or
        doc.get("role")!=expected_role or
        str(doc.get("source","")).lower()!=APP.lower() or
        str(doc.get("recipient","")).lower()!=recipient.lower() or
        doc.get("valueWei")!=str(value) or
        doc.get("nonce")!=expected_nonce or
        doc.get("gasLimit")!=GAS_LIMIT or
        doc.get("gasPriceWei")!=GAS_PRICE or
        type(doc.get("txHash")) is not str or
        not doc["txHash"].startswith("0x") or
        len(doc["txHash"])!=66):
        raise Refused("marker disagrees with exact authorized monitor1 transfer")
    txhash=doc["txHash"]
    ask=lambda method,params:transport(RPC,method,params)
    if quantity(ask("eth_chainId",[]),"actual chain id")!=CHAIN:
        raise Refused("wrong real native chain")
    genesis=ask("eth_getBlockByNumber",["0x0",False])
    if type(genesis) is not dict or str(genesis.get("hash","")).lower()!=GENESIS:
        raise Refused("wrong native execution genesis")
    final=ask("eth_getBlockByNumber",["finalized",False])
    latest=ask("eth_getBlockByNumber",["latest",False])
    if type(final) is not dict or type(latest) is not dict:
        raise Refused("finalized/latest EL block missing")
    final_height=quantity(final.get("number"),"finalized EL height")
    latest_height=quantity(latest.get("number"),"latest EL height")
    if final_height>latest_height:
        raise Refused("finalized EL ahead of latest")
    latest_nonce=quantity(ask("eth_getTransactionCount",[APP,"latest"]),
                          "source latest nonce")
    pending_nonce=quantity(ask("eth_getTransactionCount",[APP,"pending"]),
                           "source pending nonce")
    latest_balance=quantity(ask("eth_getBalance",[recipient,"latest"]),
                            "monitor1 latest balance")
    finalized_balance=quantity(ask("eth_getBalance",[recipient,hex(final_height)]),
                               "monitor1 finalized balance")

    tx=ask("eth_getTransactionByHash",[txhash])
    receipt=ask("eth_getTransactionReceipt",[txhash])
    status="MARKER_EXISTS_HASH_NOT_VISIBLE_DO_NOT_RESEND"
    height=None
    if tx is not None:
        if type(tx) is not dict:
            raise Refused("malformed actual signed monitor1 tx")
        if (str(tx.get("hash","")).lower()!=txhash.lower() or
            str(tx.get("from","")).lower()!=APP.lower() or
            str(tx.get("to","")).lower()!=recipient.lower() or
            quantity(tx.get("value"),"signed actual value")!=value or
            quantity(tx.get("nonce"),"signed nonce")!=expected_nonce or
            quantity(tx.get("gas"),"signed gas")!=GAS_LIMIT or
            quantity(tx.get("gasPrice"),"signed gas price")!=GAS_PRICE or
            tx.get("input")!="0x" or
            (tx.get("chainId") is not None and
             quantity(tx.get("chainId"),"signed chain id")!=CHAIN)):
            raise Refused("actual monitor1 transaction does NOT match immutable funding quote")
        status="MATCHING_SIGNED_TX_VISIBLE_NOT_INCLUDED"
    if receipt is not None:
        if tx is None or type(receipt) is not dict:
            raise Refused("receipt exists without matching signed transaction")
        if (str(receipt.get("transactionHash","")).lower()!=txhash.lower() or
            str(receipt.get("from","")).lower()!=APP.lower() or
            str(receipt.get("to","")).lower()!=recipient.lower() or
            receipt.get("contractAddress") is not None or
            quantity(receipt.get("gasUsed"),"actual gas used")!=GAS_LIMIT):
            raise Refused("receipt public fields differ from monitor1 exact plan")
        height=quantity(receipt.get("blockNumber"),"included EL block")
        canonical=ask("eth_getBlockByNumber",[hex(height),False])
        if (height<=0 or type(canonical) is not dict or
            str(canonical.get("hash","")).lower()!=str(receipt.get("blockHash","")).lower() or
            str(tx.get("blockHash","")).lower()!=str(receipt.get("blockHash","")).lower() or
            quantity(tx.get("blockNumber"),"tx included height")!=height):
            raise Refused("receipt is not canonical or tx/receipt block mismatched")
        if quantity(receipt.get("status"),"receipt status")==0:
            status="MATCHING_TX_CANONICAL_REVERTED_DO_NOT_RESEND"
        elif quantity(receipt.get("status"),"receipt status")==1:
            status=("MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED"
                    if height<=final_height else
                    "MATCHING_TX_SUCCESSFUL_CANONICAL_PENDING_FINALITY")
        else:
            raise Refused("unknown receipt status")
    if status=="MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED" and finalized_balance<value:
        raise Refused("funding receipt finalized but monitor1 final balance is below grant")
    return {
        "schema":"SSE_R276_VM4707_CONSUMED_MONITOR1_NONCE2_FORENSIC_READONLY_V1",
        "chainId":CHAIN,
        "originalGenesisVerified":True,
        "role":"monitor-1",
        "attemptMarkerExistsAndExact":True,
        "ownerPrivateKeystoreRead":False,
        "onlyPublicAttemptMarkerRead":True,
        "attemptAlreadyConsumedNeverResend":True,
        "recordedAttemptHash":txhash,
        "sourceEOA":APP,
        "recipient":recipient,
        "expectedNonce":expected_nonce,
        "expectedTransferValueWei":str(value),
        "gasLimit":GAS_LIMIT,
        "gasPriceWei":GAS_PRICE,
        "sourceLatestNonce":latest_nonce,
        "sourcePendingNonce":pending_nonce,
        "recipientLatestBalanceWei":str(latest_balance),
        "recipientFinalizedBalanceWei":str(finalized_balance),
        "executionHead":latest_height,
        "finalizedExecutionBlock":final_height,
        "receiptIncludedBlock":height,
        "blocksUntilReceiptFinality":(max(0,height-final_height)
                                     if height is not None else None),
        "transactionStatus":status,
        "monitor2PredecessorFinalizedEligible":status=="MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED",
        "txVisibilityIsNotProofOfWhetherAttemptBroadcast":True,
        "transactionsSignedOrSent":False,
        "walletSecretsRead":False,
        "dockerOrValidatorChanged":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rpc",required=True,choices=(RPC,))
    args=p.parse_args(argv)
    try:
        report=observe()
        print(json.dumps(report,indent=2,sort_keys=True))
        print("R276_EXACT_CONSUMED_MONITOR1_ATTEMPT_READONLY_NO_RETRY=true")
        return 0
    except (Refused,ValueError,OSError,TypeError,KeyError,OverflowError) as exc:
        print("R276_MONITOR1_PUBLIC_FORENSIC_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
