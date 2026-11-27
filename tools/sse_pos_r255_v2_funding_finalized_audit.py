#!/usr/bin/env python3
"""R255: verify ONE actual owner-authorized native TEST ETH funding transfer.

NO key access, wallet unlock, transaction, signing, Docker, or node mutation.
Checks the exact R254 public tx on original chain31340 against finalized
execution state; returns PENDING separately, never claims success pre-finality.
Use separately on native VM4706 (18545) and VM4707 (28545) local RPCs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as local_rpc

CHAIN = 31340
GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
SOURCE = "0x13fb73aace8A11Be2899D047635A757a224Ce00B"
DESTINATION = "0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0"
TX_HASH = "0x07e3ff069936936b3daf17efc5cb484c1712e93dc6bd6040c55a5fae1b8d2a90"
VALUE_WEI = 10**18
GAS_LIMIT = 21_000
GAS_PRICE_CAP_WEI = 1_000
RPC_CHOICES = ("http://127.0.0.1:18545", "http://127.0.0.1:28545")
HEX_HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEX_Q = re.compile(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)\Z")


class Refused(ValueError):
    pass


class Pending(Exception):
    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(stage)


def quantity(value, field):
    if type(value) is not str or HEX_Q.fullmatch(value) is None:
        raise Refused("malformed RPC quantity: " + field)
    return int(value, 16)


def hash32(value, field):
    if type(value) is not str or HEX_HASH.fullmatch(value) is None:
        raise Refused("malformed hash: " + field)
    return value.lower()


def address(value, field):
    if type(value) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{40}", value):
        raise Refused("malformed address: " + field)
    return value.lower()


def verify(rpc_url, transport=local_rpc):
    if rpc_url not in RPC_CHOICES:
        raise Refused("only VM4706/VM4707 approved loopback RPCs accepted")
    ask = lambda method, params: transport(rpc_url, method, params)
    if quantity(ask("eth_chainId", []), "chainId") != CHAIN:
        raise Refused("wrong chain ID")
    genesis = ask("eth_getBlockByNumber", ["0x0", False])
    if type(genesis) is not dict or hash32(genesis.get("hash"), "genesis") != GENESIS:
        raise Refused("wrong original chain genesis")

    tx = ask("eth_getTransactionByHash", [TX_HASH])
    if tx is None:
        raise Pending("TRANSACTION_NOT_YET_VISIBLE_DO_NOT_RESEND")
    if type(tx) is not dict:
        raise Refused("invalid transaction response")
    if (hash32(tx.get("hash"), "txHash") != TX_HASH or
        address(tx.get("from"), "from") != SOURCE.lower() or
        address(tx.get("to"), "to") != DESTINATION.lower() or
        quantity(tx.get("value"), "value") != VALUE_WEI or
        quantity(tx.get("nonce"), "nonce") != 0 or
        quantity(tx.get("gas"), "gas") != GAS_LIMIT or
        quantity(tx.get("gasPrice"), "gasPrice") > GAS_PRICE_CAP_WEI or
        tx.get("input") != "0x"):
        raise Refused("observed transaction differs from owner-authorized fields")
    if tx.get("chainId") is not None and quantity(tx["chainId"], "tx chainId") != CHAIN:
        raise Refused("transaction signature chain ID mismatch")
    if tx.get("type") is not None and quantity(tx["type"], "tx type") != 0:
        raise Refused("submitted transaction is not the authorized legacy type")

    receipt = ask("eth_getTransactionReceipt", [TX_HASH])
    if receipt is None:
        raise Pending("TRANSACTION_SEEN_BUT_NO_RECEIPT_DO_NOT_RESEND")
    if type(receipt) is not dict:
        raise Refused("invalid receipt response")
    if (hash32(receipt.get("transactionHash"), "receipt txHash") != TX_HASH or
        quantity(receipt.get("status"), "receipt status") != 1 or
        address(receipt.get("from"), "receipt from") != SOURCE.lower() or
        address(receipt.get("to"), "receipt to") != DESTINATION.lower() or
        receipt.get("contractAddress") is not None):
        raise Refused("receipt not a successful exact native transfer")
    gas_used = quantity(receipt.get("gasUsed"), "gasUsed")
    if gas_used != GAS_LIMIT:
        raise Refused("unexpected transfer gas expenditure")
    actual_price = quantity(receipt.get("effectiveGasPrice", tx["gasPrice"]),
                            "effectiveGasPrice")
    if actual_price > GAS_PRICE_CAP_WEI:
        raise Refused("actual paid gas price exceeds approved cap")
    included_height = quantity(receipt.get("blockNumber"), "included block")
    receipt_hash = hash32(receipt.get("blockHash"), "included blockHash")
    if included_height <= 0:
        raise Refused("invalid included block number")
    if (tx.get("blockHash") is not None and
        hash32(tx.get("blockHash"), "tx blockHash") != receipt_hash):
        raise Refused("transaction/receipt block hash mismatch")
    canonical = ask("eth_getBlockByNumber", [hex(included_height), False])
    if type(canonical) is not dict or hash32(canonical.get("hash"), "canonical blockHash") != receipt_hash:
        raise Refused("transaction inclusion is not canonical")

    finalized = ask("eth_getBlockByNumber", ["finalized", False])
    if type(finalized) is not dict:
        raise Refused("actual finalized execution block is unavailable")
    finalized_height = quantity(finalized.get("number"), "finalized height")
    final_hash = hash32(finalized.get("hash"), "finalized blockHash")
    if finalized_height < included_height:
        raise Pending("CANONICAL_RECEIPT_PRESENT_BUT_NOT_YET_FINALIZED_DO_NOT_RESEND")

    # Pinned to the same finalized height, never pending/latest balances.
    balance = quantity(ask("eth_getBalance", [DESTINATION, hex(finalized_height)]),
                       "finalized recipient balance")
    source_nonce = quantity(ask("eth_getTransactionCount",
                                [SOURCE, hex(finalized_height)]),
                            "finalized source nonce")
    if balance < VALUE_WEI or source_nonce < 1:
        raise Refused("finalized recipient funding/source nonce inconsistent with transfer")
    return {
        "schema": "SSE_R255_NATIVE_V2_DEPLOYER_FUNDING_FINALITY_AUDIT_V1",
        "status": "REAL_NATIVE_ONE_TEST_ETH_TRANSFER_FINALIZED",
        "chainId": CHAIN,
        "originalGenesisVerified": True,
        "transactionHash": TX_HASH,
        "source": SOURCE,
        "destination": DESTINATION,
        "exactValueWei": str(VALUE_WEI),
        "actualGasUsed": gas_used,
        "actualEffectiveGasPriceWei": actual_price,
        "maximumGasPriceWeiApproved": GAS_PRICE_CAP_WEI,
        "totalActualCostWei": str(VALUE_WEI + gas_used * actual_price),
        "transactionStatusSuccess": True,
        "canonicalIncludedBlock": included_height,
        "finalizedExecutionBlock": finalized_height,
        "finalizedExecutionBlockHash": final_hash,
        "recipientBalanceWeiAtFinalized": str(balance),
        "sourceNonceAtFinalized": source_nonce,
        "fundingTxCanonicalAndFinalizedVerified": True,
        "newV2ContractsDeployedOrVerified": False,
        "privateKeysReadOrTransactionsSentByAudit": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rpc", choices=RPC_CHOICES, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(verify(args.rpc), indent=2, sort_keys=True))
        print("R255_REAL_NATIVE_V2_DEPLOYER_FUNDING_FINALIZED=true")
        return 0
    except Pending as exc:
        print("R255_FUNDING_NOT_FINAL_YET: " + exc.stage, file=sys.stderr)
        return 3
    except (Refused, ValueError, TypeError, KeyError, OSError) as exc:
        print("R255_FUNDING_AUDIT_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
