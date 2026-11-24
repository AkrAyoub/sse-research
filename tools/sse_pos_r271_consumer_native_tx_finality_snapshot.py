#!/usr/bin/env python3
"""R271: one-shot, no-poll, nonmutating owner VM4707 consumer funding finality diagnostic.

Read actual chain31340 original genesis, exact R267 owner-funded consumer nonce1
TX and current canonical receipt, recipient balances at latest/finalized,
the live execution finalized height, and local Beacon head/finalized epochs.
No keys, wallet files, signing, broadcasts, client restarts, docker changes
or provider/monitor role claims. A receipt is NOT finality.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from sse_pos_r206_adaptive_v2_deployment_audit import rpc
from sse_pos_r260_v2_readonly_finalized_deployment_audit import (
    RPC, CHAIN, GENESIS, quantity,
)
from sse_pos_r265_vm4707_three_role_wallet_funding_quote import APP
from sse_pos_r267_vm4707_one_by_one_role_funding import (
    RECIPIENTS, GAS_LIMIT, GAS_PRICE,
)

TX="0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd"
BEACON="http://127.0.0.1:25052"
BEACON_ROOT="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"


class Refused(ValueError):
    pass


def fetch_beacon(path):
    if path not in (
        "/eth/v1/beacon/genesis",
        "/eth/v1/node/syncing",
        "/eth/v1/beacon/states/head/finality_checkpoints",
    ):
        raise Refused("unapproved local Beacon endpoint")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req=urllib.request.Request(BEACON+path,headers={"Accept":"application/json"})
    with opener.open(req,timeout=8) as response:
        if response.status!=200:
            raise Refused("Beacon returned non-200")
        raw=response.read(65537)
    if len(raw)>65536:
        raise Refused("Beacon response too large")
    result=json.loads(raw)
    if type(result) is not dict or type(result.get("data")) is not dict:
        raise Refused("malformed Beacon response")
    return result["data"]


def observation(*,transport=rpc,beacon=fetch_beacon):
    call=lambda method,params:transport(RPC,method,params)
    if quantity(call("eth_chainId",[]),"chainId")!=CHAIN:
        raise Refused("wrong chain ID")
    block0=call("eth_getBlockByNumber",["0x0",False])
    if type(block0) is not dict or str(block0.get("hash","")).lower()!=GENESIS:
        raise Refused("wrong original EL genesis")
    latest=call("eth_getBlockByNumber",["latest",False])
    final=call("eth_getBlockByNumber",["finalized",False])
    if type(latest) is not dict or type(final) is not dict:
        raise Refused("EL latest/finalized unavailable")
    head_height=quantity(latest.get("number"),"latest")
    final_height=quantity(final.get("number"),"finalized")
    if final_height>head_height:
        raise Refused("finalized execution block after head")

    tx=call("eth_getTransactionByHash",[TX])
    receipt=call("eth_getTransactionReceipt",[TX])
    recipient=RECIPIENTS[0][1]
    amount=RECIPIENTS[0][2]
    included=None
    tx_status="NOT_VISIBLE"
    if tx is not None:
        if (type(tx) is not dict or
            str(tx.get("hash","")).lower()!=TX or
            str(tx.get("from","")).lower()!=APP.lower() or
            str(tx.get("to","")).lower()!=recipient.lower() or
            quantity(tx.get("value"),"tx value")!=amount or
            quantity(tx.get("nonce"),"tx nonce")!=1 or
            quantity(tx.get("gas"),"tx gas")!=GAS_LIMIT or
            quantity(tx.get("gasPrice"),"tx gas price")!=GAS_PRICE or
            tx.get("input")!="0x" or
            (tx.get("chainId") is not None and
             quantity(tx.get("chainId"),"signed tx chain")!=CHAIN)):
            raise Refused("funding TX not exact owner-authorized R267 nonce1 transfer")
        tx_status="VISIBLE_NO_RECEIPT"
    if receipt is not None:
        if tx is None or type(receipt) is not dict:
            raise Refused("receipt without corresponding valid R267 transaction")
        if (str(receipt.get("transactionHash","")).lower()!=TX or
            str(receipt.get("from","")).lower()!=APP.lower() or
            str(receipt.get("to","")).lower()!=recipient.lower() or
            receipt.get("contractAddress") is not None or
            quantity(receipt.get("gasUsed"),"gas used")!=GAS_LIMIT):
            raise Refused("consumer funding receipt fields invalid")
        if quantity(receipt.get("status"),"receipt status")!=1:
            raise Refused("consumer native funding transaction actually REVERTED")
        included=quantity(receipt.get("blockNumber"),"receipt block")
        canonical=call("eth_getBlockByNumber",[hex(included),False])
        if type(canonical) is not dict or str(canonical.get("hash","")).lower()!=str(receipt.get("blockHash","")).lower():
            raise Refused("consumer receipt is NOT on canonical chain")
        tx_status=("SUCCESSFUL_CANONICAL_FINALIZED"
                   if final_height>=included else "SUCCESSFUL_CANONICAL_NOT_YET_FINALIZED")

    genesis=beacon("/eth/v1/beacon/genesis")
    if str(genesis.get("genesis_validators_root","")).lower()!=BEACON_ROOT:
        raise Refused("wrong Beacon genesis root")
    sync=beacon("/eth/v1/node/syncing")
    checkpoints=beacon("/eth/v1/beacon/states/head/finality_checkpoints")
    if (sync.get("is_syncing") is not False or
        sync.get("is_optimistic") is not False or
        sync.get("el_offline") is not False):
        raise Refused("Beacon syncing, optimistic or EL offline")
    final_cp=checkpoints.get("finalized")
    if type(final_cp) is not dict:
        raise Refused("Beacon finalized checkpoint absent")
    beacon_head=int(sync.get("head_slot"))
    beacon_final=int(final_cp.get("epoch"))
    if beacon_final<1 or beacon_final>beacon_head//32:
        raise Refused("Beacon head/finality invalid")

    actual_latest=quantity(call("eth_getBalance",[recipient,"latest"]),"latest consumer balance")
    actual_finalized=quantity(call("eth_getBalance",[recipient,hex(final_height)]),"finalized consumer balance")
    if tx_status=="SUCCESSFUL_CANONICAL_FINALIZED" and actual_finalized<amount:
        raise Refused("finalized consumer recipient balance inconsistent with 0.01 transfer")
    return {
        "schema":"SSE_R271_VM4707_EXACT_CONSUMER_FUNDING_TX_FINALITY_ONCE_V1",
        "chainId":CHAIN,"originalGenesisVerified":True,
        "consumerFundingTransactionHash":TX,
        "consumerAddress":recipient,
        "transferAmountWei":str(amount),
        "transactionStatus":tx_status,
        "transactionIncludedBlock":included,
        "executionLatestBlock":head_height,
        "executionFinalizedBlock":final_height,
        "executionRemainingBlocksUntilTxFinality":(
            max(0,included-final_height) if included is not None else None
        ),
        "consumerLatestBalanceWei":str(actual_latest),
        "consumerFinalizedBalanceWei":str(actual_finalized),
        "beaconHeadSlot":beacon_head,
        "beaconHeadEpoch":beacon_head//32,
        "beaconFinalizedEpoch":beacon_final,
        "beaconFinalityLagEpochs":beacon_head//32-beacon_final,
        "beaconRootVerified":True,
        "monitor1CanBeFundedOnlyAfterConsumerTxFinalized":True,
        "transactionsSignedOrSent":False,
        "walletOrValidatorKeysRead":False,
        "dockerOrBeaconChanged":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc",choices=(RPC,),required=True)
    args=parser.parse_args(argv)
    try:
        print(json.dumps(observation(),sort_keys=True,indent=2))
        print("R271_REAL_NATIVE_CONSUMER_TX_AND_BEACON_FINALITY_READONLY=true")
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError,UnicodeError) as exc:
        print("R271_NATIVE_CONSUMER_FINALITY_READONLY_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
