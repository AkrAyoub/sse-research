#!/usr/bin/env python3
"""R265: native VM4707 actual new role-EOA TEST ETH funding quote ONLY.

Public three recipient addresses are from actual owner R264 VM4707 wallet
creation logs. Read-only localhost native RPC, no wallet access, secret
imports, signing, broadcast, retries, contract deploy or Docker/Beacon.
The fixed amounts are EXPLICIT RESEARCH BOOTSTRAP PROPOSALS, NOT spending
authorization and NOT meaningful economic Sybil deterrence. User must
separately approve EVERY subsequent actual funding transfer.
"""
from __future__ import annotations

import argparse
import json
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as actual_rpc
from sse_pos_r260_v2_readonly_finalized_deployment_audit import (
    RPC, CHAIN, GENESIS, TX_HASH, APP,
    APPROVED_MARKET_ADDRESS as MARKET,
    quantity,
)

# Fixed, modest, owner-reviewable suggestions, no native TX authorization.
# Monitor must be able to bond >= 0.001 TEST ETH, with gas margin.
# Consumer must be able to fund actual lease escrow later.
RECIPIENTS = (
    ("consumer", "0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f", 10**16),
    ("monitor-1", "0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147", 5*10**15),
    ("monitor-2", "0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8", 5*10**15),
)
LEDGER="0x6635849b77f037fab611736612d7d3493dc650ff"
ORIGINAL_FUNDER="0x13fb73aace8A11Be2899D047635A757a224Ce00B"
GAS_PER_TRANSFER=21000
GAS_PRICE_CAP_WEI=1000
EXPECTED_FUNDER_PENDING_NONCE=1
BOND_WEI=10**15


class Refused(ValueError):
    pass


def quote(url,*,transport=actual_rpc):
    if url!=RPC:
        raise Refused("only actual local VM4707 original-chain RPC")
    ask=lambda method,params:transport(url,method,params)
    if quantity(ask("eth_chainId",[]),"chainId")!=CHAIN:
        raise Refused("not chain31340")
    genesis=ask("eth_getBlockByNumber",["0x0",False])
    if type(genesis) is not dict or str(genesis.get("hash","")).lower()!=GENESIS:
        raise Refused("original execution genesis mismatch")
    receipt=ask("eth_getTransactionReceipt",[TX_HASH])
    if (type(receipt) is not dict or
        str(receipt.get("transactionHash","")).lower()!=TX_HASH or
        quantity(receipt.get("status"),"market deploy status")!=1 or
        str(receipt.get("contractAddress","")).lower()!=MARKET.lower()):
        raise Refused("original V2 market creation not present/successful")
    included=quantity(receipt.get("blockNumber"),"deployment block")
    canonical=ask("eth_getBlockByNumber",[hex(included),False])
    if (type(canonical) is not dict or
        str(canonical.get("hash","")).lower()!=
        str(receipt.get("blockHash","")).lower()):
        raise Refused("V2 deployment is not canonical")
    final=ask("eth_getBlockByNumber",["finalized",False])
    if type(final) is not dict:
        raise Refused("finalized execution height not available")
    final_height=quantity(final.get("number"),"finalized number")

    nonce=quantity(ask("eth_getTransactionCount",[APP,"pending"]),
                   "app pending nonce")
    if nonce!=EXPECTED_FUNDER_PENDING_NONCE:
        raise Refused("app-only EOA has new pending nonce; funding proposal must be reviewed")
    if ask("eth_getCode",[APP,"latest"])!="0x":
        raise Refused("app-only funded source unexpectedly contains contract code")

    gas_price=quantity(ask("eth_gasPrice",[]),"node gasPrice")
    head=ask("eth_getBlockByNumber",["latest",False])
    if type(head) is not dict:
        raise Refused("missing latest block")
    base=head.get("baseFeePerGas")
    if (gas_price<=0 or gas_price>GAS_PRICE_CAP_WEI or
        (base is not None and quantity(base,"basefee")>GAS_PRICE_CAP_WEI)):
        raise Refused("native current price/basefee exceeds proposed maximum")
    if quantity(head.get("gasLimit"),"block gas limit")<GAS_PER_TRANSFER:
        raise Refused("native block gas limit inadequate")
    seen={APP.lower(),MARKET.lower(),LEDGER.lower(),ORIGINAL_FUNDER.lower()}
    proposals=[]
    for role,address,value in RECIPIENTS:
        if address.lower() in seen:
            raise Refused("duplicate or prohibited EOA destination")
        seen.add(address.lower())
        if not (isinstance(value,int) and 0<value<10**18):
            raise Refused("invalid fixed research allocation")
        if (role.startswith("monitor-") and value<=BOND_WEI):
            raise Refused("monitor proposal cannot cover minimum bond+gas")
        if ask("eth_getCode",[address,"latest"])!="0x":
            raise Refused(role+" has deployed code, not empty app EOA")
        balance=quantity(ask("eth_getBalance",[address,"latest"]),role+" balance")
        pending=quantity(ask("eth_getTransactionCount",[address,"pending"]),
                         role+" pending nonce")
        if balance!=0 or pending!=0:
            raise Refused(role+" has existing balance/nonce; stop duplicate funding plan")
        query={"from":APP,"to":address,"value":hex(value),"data":"0x"}
        estimate=quantity(ask("eth_estimateGas",[query]),role+" native gas estimate")
        if estimate!=GAS_PER_TRANSFER:
            raise Refused(role+" basic EOA transfer gas is not exactly 21000")
        proposals.append({
            "role":role,"publicRecipientAddress":address,
            "observedCurrentBalanceWei":"0",
            "observedPendingNonce":0,
            "suggestedTransferValueWei":str(value),
            "suggestedTransferTestEth":str(value/10**18),
            "gasLimit":GAS_PER_TRANSFER,
            "observedGasEstimate":estimate,
            "maximumFixedGasPriceWei":GAS_PRICE_CAP_WEI,
            "maximumGasFeeWei":str(GAS_PER_TRANSFER*GAS_PRICE_CAP_WEI),
            "maximumTotalDebitWei":str(value+GAS_PER_TRANSFER*GAS_PRICE_CAP_WEI),
            "transactionAuthorized":False,
        })
    balance=quantity(ask("eth_getBalance",[APP,"latest"]),"app source balance")
    total_value=sum(v for _,_,v in RECIPIENTS)
    total_fee=GAS_PER_TRANSFER*GAS_PRICE_CAP_WEI*len(RECIPIENTS)
    if balance<total_value+total_fee:
        raise Refused("real funded app wallet cannot cover entire proposed role bootstrap")
    return {
        "schema":"SSE_R265_THREE_REAL_ROLE_WALLETS_FUNDING_PREVIEW_ONLY_V1",
        "chainId":CHAIN,"originalGenesisVerified":True,
        "realMarketCreationCanonical":True,
        "realMarketDeploymentFinalized":final_height>=included,
        "deploymentBlock":included,
        "finalizedExecutionBlock":final_height,
        "sourceApplicationEOA":APP,
        "sourceIsNotOriginalGenesisOrValidator":True,
        "sourcePendingNonce":nonce,
        "sourceLatestBalanceWei":str(balance),
        "maximumProposedGasPriceWei":GAS_PRICE_CAP_WEI,
        "proposedRecipients":proposals,
        "proposedTotalNativeTestEthTransferWei":str(total_value),
        "proposedMaximumCumulativeGasFeesWei":str(total_fee),
        "proposedMaximumCombinedDebitWei":str(total_value+total_fee),
        "originalNativeMarketMinimumMonitorBondWei":str(BOND_WEI),
        "proposalOnlyNotEconomicSecurity":True,
        "fundingSpendsAuthorized":False,
        "keystoresRead":False,
        "signedOrBroadcastTransactions":False,
        "physicalMonitorIndependenceProved":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rpc",required=True,choices=(RPC,))
    args=p.parse_args(argv)
    try:
        print(json.dumps(quote(args.rpc),sort_keys=True,indent=2))
        print("R265_REAL_VM4707_THREE_ROLE_FUNDING_QUOTE_ONLY_NO_SEND=true")
        return 0
    except (Refused,ValueError,TypeError,KeyError,OSError) as exc:
        print("R265_REAL_ROLE_FUNDING_QUOTE_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
