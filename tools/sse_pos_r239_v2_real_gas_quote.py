#!/usr/bin/env python3
"""R239: read-only real node fee/escrow affordability quote for V2 role txs.

Performs ACTUAL chain31340 localhost eth_estimateGas, eth_gasPrice,
eth_getBalance and latest block gas limit on a R206-finalized-attested
market/ledger deployment. NEVER creates wallet, signs/sends transactions,
funds a faucet, or substitutes simulator gas for network evidence.
Estimation and nonce are latest/pending state, not a guarantee of inclusion.
A quote is for a participant's publicly supplied application EOA only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from sse_pos_r226_adaptive_v2_transaction_planner import (
    Refused as PlannerRefused, build as build_plan,
    checked_address as checked_contract,
    verify_funded_bid,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,
    rpc as rpc_transport,verify as verify_deployment,
)

GENESIS_EOA="0x13fb73aace8a11be2899d047635a757a224ce00b"
HEXQ=re.compile(r"0x[0-9a-fA-F]+\Z")
MAX_GAS=30_000_000

class Refused(ValueError):
    pass


def number(raw,label):
    if type(raw) is not str or not HEXQ.fullmatch(raw):
        raise Refused("bad live RPC quantity for "+label)
    return int(raw,16)


def quote(plan,signer,manifest,rpc_url,*,max_total_wei,
          transport=rpc_transport,attestation=None,
          finalized_fee=None):
    signer=checked_contract(signer)
    if signer==GENESIS_EOA:
        raise Refused("original genesis EOA forbidden as application signer")
    if type(max_total_wei) is not int or not 0<max_total_wei<2**256:
        raise Refused("explicit maximum total spend in wei required")
    if (plan.target.lower() not in (
        manifest["market"]["address"].lower(),
        manifest["ledger"]["address"].lower()
    )):
        raise Refused("transaction target outside approved V2 application")
    verified=(attestation if attestation is not None else
              verify_deployment(manifest,rpc_url,transport=transport))
    if verified.get("deploymentReceiptSuccessfulAndFinalized") is not True:
        raise Refused("R206 finalized contract deployment not confirmed")
    call={
        "from":signer,"to":plan.target,
        "data":plan.calldata,"value":hex(plan.value_wei)
    }
    estimated=number(transport(rpc_url,"eth_estimateGas",[call]),"gas estimate")
    price=number(transport(rpc_url,"eth_gasPrice",[]),"gas price")
    balance=number(transport(rpc_url,"eth_getBalance",[signer,"finalized"]),"finalized balance")
    latest=transport(rpc_url,"eth_getBlockByNumber",["latest",False])
    if type(latest) is not dict:
        raise Refused("missing real latest execution block")
    block_limit=number(latest.get("gasLimit"),"latest block gas limit")
    latest_height=number(latest.get("number"),"latest execution height")
    if not 0<estimated<block_limit<=MAX_GAS or price<=0:
        raise Refused("real estimate outside live block gas/fee policy bounds")
    # Padding for dynamically increasing EVM gas paths; this is an estimate
    # and **not** an authorization to spend or a verified gas guarantee.
    gas_limit=(estimated*125+99)//100+5000
    if gas_limit>block_limit:
        raise Refused("padded gas requirement exceeds live block limit")
    total=plan.value_wei+gas_limit*price
    if total>max_total_wei:
        raise Refused("gas/value exceed explicit operator research budget")
    if total>balance:
        raise Refused("existing finalized native TEST ETH balance insufficient")
    return {
        "schema":"SSE_R239_REAL_NODE_V2_READONLY_TX_QUOTE_V1",
        "chainId":31340,
        "originalGenesisR206Verified":True,
        "applicationSignerPublic":signer,
        "action":plan.action,"target":plan.target,
        "declaredRole":plan.role,
        "calldata":plan.calldata,
        "valueWei":str(plan.value_wei),
        "observedEstimatedGas":estimated,
        "paddedGasLimit":gas_limit,
        "observedGasPriceWei":str(price),
        "estimatedUpperBudgetWei":str(total),
        "ownerMaxTotalSpendWei":str(max_total_wei),
        "actualNativeBalanceWeiAtFinalized":str(balance),
        "latestExecutionHeightObserved":latest_height,
        "r206FinalizedDeploymentBlock":verified["deploymentBlock"],
        "realRpcEthEstimateGasCalled":True,
        "blockGasLimit":block_limit,
        "notAGuaranteeOfFutureFeesOrExecution":True,
        "walletSecretAccessed":False,
        "transactionSignedOrSubmitted":False,
        "independentPhysicalSlaVerified":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--action",required=True)
    p.add_argument("--role",required=True)
    p.add_argument("--params-json",required=True,help="public action args only")
    p.add_argument("--from-address",required=True,help="public test-only APP EOA; never original genesis EOA")
    p.add_argument("--max-total-wei",type=int,required=True)
    a=p.parse_args(argv)
    try:
        m=load_manifest(a.manifest)
        params=json.loads(a.params_json)
        plan=build_plan(a.action,a.role,params,
                        m["market"]["address"],m["ledger"]["address"])
        proof=verify_deployment(m,a.rpc)
        if a.action=="fund":
            verify_funded_bid(plan,params,m,a.rpc)
        if a.action=="monitor-register" and plan.value_wei<int(m["minimumBondWei"]):
            raise Refused("monitor bond below actual on-chain immutable minimum")
        out=quote(plan,a.from_address,m,a.rpc,max_total_wei=a.max_total_wei,
                  attestation=proof)
        print(json.dumps(out,sort_keys=True,indent=2))
        return 0
    except (Refused,PlannerRefused,AuditRefused,OSError,ValueError,
            OverflowError,TypeError,KeyError) as exc:
        print("R239_REAL_NODE_V2_GAS_QUOTE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
