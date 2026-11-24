#!/usr/bin/env python3
"""R260: actual first V2 contract CREATE receipt/finality/code verification.

READ-ONLY original chain31340 RPC. NO keys, signing, retries, sends, Docker
or validator operations. Verifies one exact owner-authorized nonce0 contract
CREATE, market+internally-created vote ledger, compiler-bytecode equivalence
outside Solc-declared immutable patch slots, and produces a public R206
manifest ONLY after the genuine canonical successful receipt is finalized.
The manifest can be independently rechecked on VM4706 using R206.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import (
    rpc as rpc_transport, verify as r206_verify,
    selector, _read_address as read_address,
)
from sse_pos_r247_v2_compiled_abi_parity import load_artifact
from sse_pos_r256_v2_readonly_native_deployment_quote import (
    pin_artifacts, EXPECTED_MARKET_RUNTIME_BYTES,
    EXPECTED_LEDGER_RUNTIME_BYTES,
)
from sse_pos_r257_vm4707_one_time_v2_deployment import (
    APPROVED_INITCODE_SHA256, APPROVED_MARKET_ADDRESS,
    APP, CHAIN, GENESIS, BOND_WEI, GAS_LIMIT, GAS_PRICE_WEI,
    MAX_FEE_WEI, create_address,
)
from sse_pos_r255_v2_funding_finalized_audit import (
    TX_HASH as FUNDING_TX_HASH,
    SOURCE as ORIGINAL_FUNDING_SOURCE,
    DESTINATION as ORIGINAL_FUNDING_DESTINATION,
    VALUE_WEI as FUNDING_VALUE_WEI,
    GAS_LIMIT as FUNDING_GAS_LIMIT,
    GAS_PRICE_CAP_WEI as FUNDING_GAS_PRICE_CAP_WEI,
)

RPC = "http://127.0.0.1:28545"
TX_HASH = "0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6"
HEX32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEXB = re.compile(r"0x(?:[0-9a-fA-F]{2})+\Z")
HEXQ = re.compile(r"0x[0-9a-fA-F]+\Z")


class Refused(ValueError):
    pass


class Pending(Exception):
    def __init__(self, stage, **numbers):
        super().__init__(stage)
        self.stage = stage
        self.numbers = numbers


def quantity(x, name):
    if type(x) is not str or not HEXQ.fullmatch(x):
        raise Refused("malformed RPC quantity " + name)
    return int(x,16)


def hash32(x, name):
    if type(x) is not str or not HEX32.fullmatch(x):
        raise Refused("malformed 32-byte hash " + name)
    return x.lower()


def require_address(x, name):
    if type(x) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{40}",x):
        raise Refused("malformed address "+name)
    return x.lower()


def verify_compiler_runtime(artifact, onchain_hex, expected_len, name):
    """Compare *all nonimmutable bytes* against Solc's actual compiled code.

    Solc intentionally leaves immutableReferences placeholders in its
    deployedBytecode.object. Enforce that only the compiler-reported
    immutable slots differ, and let R206 check concrete getter values
    and both immutable contract links on the actual finalized chain.
    """
    envelope=artifact.get("deployedBytecode")
    if type(envelope) is not dict or type(envelope.get("object")) is not str:
        raise Refused(name+" compiled deployed runtime not present")
    expected=envelope["object"]
    if (not HEXB.fullmatch(expected) or type(onchain_hex) is not str or
        not HEXB.fullmatch(onchain_hex)):
        raise Refused(name+" compiler/onchain runtime hex missing")
    compiled=bytes.fromhex(expected[2:])
    actual=bytes.fromhex(onchain_hex[2:])
    if len(compiled)!=expected_len or len(actual)!=expected_len:
        raise Refused(name+" runtime byte length does not match R249 compiled length")
    immutables=envelope.get("immutableReferences",{})
    if type(immutables) is not dict:
        raise Refused(name+" Solc immutable reference map missing")
    mask=bytearray(len(compiled))
    slots=[]
    for ident,entries in immutables.items():
        if (type(ident) is not str or not ident.isdecimal() or
            type(entries) is not list or not entries):
            raise Refused(name+" malformed compiler immutable identifier")
        for slot in entries:
            if (type(slot) is not dict or set(slot)!={"start","length"} or
                type(slot["start"]) is not int or type(slot["length"]) is not int):
                raise Refused(name+" malformed compiler immutable slot")
            start,length=slot["start"],slot["length"]
            if length!=32 or start<0 or start+length>len(compiled):
                raise Refused(name+" unbounded/nonword compiler immutable slot")
            if any(mask[start:start+length]):
                raise Refused(name+" compiler immutable slots overlap")
            mask[start:start+length]=b"\x01"*length
            slots.append(actual[start:start+length])
    if not slots:
        raise Refused(name+" expected constructor-set immutables absent")
    if any(compiled[i]!=actual[i] for i in range(len(compiled)) if not mask[i]):
        raise Refused(name+" ONCHAIN RUNTIME DIFFERS FROM SOLC OUTSIDE IMMUTABLE SLOTS")
    return {"runtimeSha256":hashlib.sha256(actual).hexdigest(),
            "onChainRuntimeBytes":len(actual),
            "unmodifiedCompiledNonImmutableBytesVerified":True,
            "solcImmutablePatchSlots":len(slots),
            "immutableValues":slots}


def require_slot_value(runtime, value, label):
    slot=int(value).to_bytes(32,"big")
    if slot not in runtime["immutableValues"]:
        raise Refused(label+" not found in actual Solc immutable patch slots")


def verify_original_funding_history(rpc_url, *,transport=rpc_transport):
    """Original finalized 1 TEST ETH incoming transfer; no current balance test.

    Recipient legitimately spends some of the 1 TEST ETH on deployment
    gas. R255's original balance>=1e18 test is intentionally unsuitable
    after that expenditure. Prove original transfer from its immutable
    historical transaction, canonical receipt and finalized ancestry.
    """
    ask=lambda method,params:transport(rpc_url,method,params)
    tx=ask("eth_getTransactionByHash",[FUNDING_TX_HASH])
    receipt=ask("eth_getTransactionReceipt",[FUNDING_TX_HASH])
    if type(tx) is not dict or type(receipt) is not dict:
        raise Refused("original funding transaction/receipt missing from node")
    if (hash32(tx.get("hash"),"funding tx hash") != FUNDING_TX_HASH or
        require_address(tx.get("from"),"original source")!=ORIGINAL_FUNDING_SOURCE.lower() or
        require_address(tx.get("to"),"funding destination")!=APP.lower() or
        APP.lower()!=ORIGINAL_FUNDING_DESTINATION.lower() or
        quantity(tx.get("value"),"funding value")!=FUNDING_VALUE_WEI or
        quantity(tx.get("nonce"),"funding nonce")!=0 or
        quantity(tx.get("gas"),"funding gas")!=FUNDING_GAS_LIMIT or
        quantity(tx.get("gasPrice"),"funding gasPrice")>FUNDING_GAS_PRICE_CAP_WEI or
        tx.get("input")!="0x" or
        hash32(receipt.get("transactionHash"),"funding receipt hash")!=FUNDING_TX_HASH or
        quantity(receipt.get("status"),"funding receipt status")!=1 or
        quantity(receipt.get("gasUsed"),"funding gas used")!=FUNDING_GAS_LIMIT):
        raise Refused("original authorized 1 TEST ETH funding was not actually transferred")
    if (require_address(receipt.get("from"),"receipt funding source")!=
        ORIGINAL_FUNDING_SOURCE.lower() or
        require_address(receipt.get("to"),"receipt funding destination")!=APP.lower()):
        raise Refused("original funding receipt counterparties mismatch")
    inclusion=quantity(receipt.get("blockNumber"),"original funding block")
    canonical=ask("eth_getBlockByNumber",[hex(inclusion),False])
    if (inclusion<=0 or type(canonical) is not dict or
        hash32(canonical.get("hash"),"original funding canonical hash")!=
        hash32(receipt.get("blockHash"),"original funding receipt blockHash")):
        raise Refused("original funding transaction is no longer canonical")
    final=ask("eth_getBlockByNumber",["finalized",False])
    if type(final) is not dict:
        raise Refused("original funding cannot be finalized without finalized block")
    final_number=quantity(final.get("number"),"funding finalization height")
    if final_number<inclusion:
        raise Pending("FUNDING_INCLUDED_BUT_NOT_FINALIZED_NO_RESENDS",
                      includedFundingBlock=inclusion,finalizedExecutionBlock=final_number)
    return {"fundingTransactionHash":FUNDING_TX_HASH,
            "fundingIncludedBlock":inclusion,
            "fundingTransferFinalized":True}


def verify(rpc_url, market_artifact, ledger_artifact, *,transport=rpc_transport,
           r206_fn=r206_verify, funding_fn=verify_original_funding_history):
    if rpc_url != RPC:
        raise Refused("only approved local VM4707 native RPC allowed")
    initcode=pin_artifacts(market_artifact,ledger_artifact,BOND_WEI)
    if hashlib.sha256(bytes.fromhex(initcode[2:])).hexdigest()!=APPROVED_INITCODE_SHA256:
        raise Refused("locally compiled initcode differs from exactly authorized R259 SHA256")
    expected_market=create_address(APP)
    if expected_market.lower()!=APPROVED_MARKET_ADDRESS.lower():
        raise Refused("actual approved CREATE nonce0 address differs")

    ask=lambda method, params: transport(rpc_url, method, params)
    if quantity(ask("eth_chainId",[]),"chain ID")!=CHAIN:
        raise Refused("not native chain31340")
    genesis=ask("eth_getBlockByNumber",["0x0",False])
    if type(genesis) is not dict or hash32(genesis.get("hash"),"genesis")!=GENESIS:
        raise Refused("original execution genesis mismatch")

    # Funding stays valid even after the app EOA has paid deployment gas.
    funding=funding_fn(rpc_url,transport=transport)
    if (funding.get("fundingTransferFinalized") is not True or
        funding.get("fundingTransactionHash")!=FUNDING_TX_HASH):
        raise Refused("original historical native funding not canonical and finalized")

    tx=ask("eth_getTransactionByHash",[TX_HASH])
    if tx is None:
        raise Pending("SUBMITTED_DEPLOYMENT_TX_NOT_VISIBLE_DO_NOT_RESEND")
    if type(tx) is not dict:
        raise Refused("malformed deployment transaction")
    data=tx.get("input")
    if (hash32(tx.get("hash"),"tx hash")!=TX_HASH or
        require_address(tx.get("from"),"tx from")!=APP.lower() or
        tx.get("to") is not None or
        quantity(tx.get("nonce"),"nonce")!=0 or
        quantity(tx.get("value"),"value")!=0 or
        quantity(tx.get("gas"),"gas")!=GAS_LIMIT or
        quantity(tx.get("gasPrice"),"gasPrice")!=GAS_PRICE_WEI or
        type(data) is not str or not HEXB.fullmatch(data) or
        hashlib.sha256(bytes.fromhex(data[2:])).hexdigest()!=APPROVED_INITCODE_SHA256 or
        data.lower()!=initcode.lower()):
        raise Refused("mined/pending deployment tx differs from EXACT owner authorized CREATE")
    if tx.get("type") is not None and quantity(tx["type"],"type")!=0:
        raise Refused("unexpected EIP-1559/typed transaction rather than fixed legacy create")
    if tx.get("chainId") is not None and quantity(tx["chainId"],"tx chain id")!=CHAIN:
        raise Refused("transaction signed for wrong chain")

    receipt=ask("eth_getTransactionReceipt",[TX_HASH])
    if receipt is None:
        raise Pending("DEPLOYMENT_TX_KNOWN_BUT_RECEIPT_MISSING_DO_NOT_RESEND")
    if type(receipt) is not dict:
        raise Refused("malformed deployment receipt")
    if (hash32(receipt.get("transactionHash"),"receipt transactionHash")!=TX_HASH or
        require_address(receipt.get("from"),"receipt from")!=APP.lower() or
        receipt.get("to") is not None or
        quantity(receipt.get("status"),"status")!=1 or
        require_address(receipt.get("contractAddress"),"contract address")!=
        APPROVED_MARKET_ADDRESS.lower()):
        raise Refused("deployment receipt reverted or contract address unexpected")
    gas_used=quantity(receipt.get("gasUsed"),"gasUsed")
    paid_price=quantity(receipt.get("effectiveGasPrice",tx["gasPrice"]),"effectiveGasPrice")
    if not 0<gas_used<=GAS_LIMIT or not 0<paid_price<=GAS_PRICE_WEI:
        raise Refused("actual gas spent exceeds owner-authorized deployment fee")
    included=quantity(receipt.get("blockNumber"),"included block")
    if included<=0:
        raise Refused("invalid inclusion block")
    included_hash=hash32(receipt.get("blockHash"),"receipt blockHash")
    if tx.get("blockHash") is not None and hash32(tx["blockHash"],"tx blockHash")!=included_hash:
        raise Refused("transaction and receipt disagree on block")
    canonical=ask("eth_getBlockByNumber",[hex(included),False])
    if (type(canonical) is not dict or
        hash32(canonical.get("hash"),"canonical hash")!=included_hash):
        raise Refused("receipt no longer on actual canonical chain")
    finalized=ask("eth_getBlockByNumber",["finalized",False])
    if type(finalized) is not dict:
        raise Refused("native execution finality unavailable")
    finalized_height=quantity(finalized.get("number"),"finalized height")
    if finalized_height<included:
        raise Pending("SUCCESSFUL_CANONICAL_DEPLOYMENT_RECEIPT_PENDING_FINALITY_DO_NOT_RESEND",
                      includedBlock=included,finalizedExecutionBlock=finalized_height,
                      actualGasUsed=gas_used)
    finalized_hash=hash32(finalized.get("hash"),"finalized hash")
    at=hex(finalized_height)
    votes=ask("eth_call",[{"to":APPROVED_MARKET_ADDRESS,"data":selector("votes()")},at])
    ledger=read_address(votes)
    if ledger==APPROVED_MARKET_ADDRESS.lower() or int(ledger,16)==0:
        raise Refused("vote ledger not a separate live contract")
    ledger_settlement=read_address(ask("eth_call",[
        {"to":ledger,"data":selector("settlement()")},at]))
    real_bond=quantity(ask("eth_call",[
        {"to":APPROVED_MARKET_ADDRESS,"data":selector("minimumBond()")},at]),
        "minimumBond()")
    if ledger_settlement!=APPROVED_MARKET_ADDRESS.lower() or real_bond!=BOND_WEI:
        raise Refused("immutable market+ledger link or onchain bond differs from approval")
    market_code=ask("eth_getCode",[APPROVED_MARKET_ADDRESS,at])
    ledger_code=ask("eth_getCode",[ledger,at])
    m_rt=verify_compiler_runtime(market_artifact,market_code,
                                 EXPECTED_MARKET_RUNTIME_BYTES,"market")
    l_rt=verify_compiler_runtime(ledger_artifact,ledger_code,
                                 EXPECTED_LEDGER_RUNTIME_BYTES,"ledger")
    require_slot_value(m_rt,int(ledger,16),"market.votes")
    require_slot_value(m_rt,BOND_WEI,"market.minimumBond")
    require_slot_value(l_rt,int(APPROVED_MARKET_ADDRESS,16),"ledger.settlement")

    manifest={
        "schema":"SSE_R206_ADAPTIVE_MARKET_V2_DEPLOYMENT_V1",
        "chainId":CHAIN,
        "executionGenesisHash":GENESIS,
        "deployer":APP,
        "deploymentTxHash":TX_HASH,
        "minimumBondWei":str(BOND_WEI),
        "market":{"address":APPROVED_MARKET_ADDRESS,
                  "runtimeSha256":m_rt["runtimeSha256"]},
        "ledger":{"address":ledger,"runtimeSha256":l_rt["runtimeSha256"]},
    }
    result=r206_fn(manifest,rpc_url,transport=transport)
    if result.get("deploymentReceiptSuccessfulAndFinalized") is not True:
        raise Refused("full R206 finalized market+ledger audit did not pass")
    return {
        "schema":"SSE_R260_REAL_FINALIZED_NATIVE_V2_DEPLOYMENT_V1",
        "status":"REAL_MARKET_AND_VOTE_LEDGER_CONTRACTS_FINALIZED",
        "deploymentTransactionHash":TX_HASH,
        "chainId":CHAIN,
        "originalGenesisVerified":True,
        "originalFundingTransactionHash":FUNDING_TX_HASH,
        "originalFundingVerifiedAsCanonicalAndFinalizedAtHistoricalBlock":True,
        "approvedConstructorInitcodeSha256":APPROVED_INITCODE_SHA256,
        "deployerAppEOA":APP,
        "nonce":0,
        "exactTransactionValueWei":"0",
        "actualGasUsed":gas_used,
        "actualGasPriceWei":paid_price,
        "actualFeePaidWei":str(gas_used*paid_price),
        "maximumFeeApprovedWei":str(MAX_FEE_WEI),
        "deploymentIncludedBlock":included,
        "finalizedExecutionBlock":finalized_height,
        "finalizedExecutionBlockHash":finalized_hash,
        "SolcNonImmutableRuntimeBytesVerifiedForBothContracts":True,
        "SolcMarketImmutableSlots":m_rt["solcImmutablePatchSlots"],
        "SolcLedgerImmutableSlots":l_rt["solcImmutablePatchSlots"],
        "immutableMarketLedgerMutualLinksAndMonitorBondVerified":True,
        "r206FinalizedAuditPassed":True,
        "manifest":manifest,
        "keysReadOrTransactionsSent":False,
        "genuinePhysicalSlaProven":False,
        "unbiasedVrfProven":False,
    }


def write_manifest(path, manifest):
    if not isinstance(path,Path) or not path.is_absolute() or path.parent.is_symlink():
        raise Refused("manifest output must be absolute, parent non-symlink")
    if not path.parent.is_dir():
        raise Refused("manifest parent directory missing")
    data=(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode()
    if len(data)>8192:
        raise Refused("public manifest exceeds safe bound")
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path,flags,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError as exc:
        raise Refused("existing manifest file; do not overwrite evidence") from exc


def main(argv=None):
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc",choices=(RPC,),required=True)
    parser.add_argument("--manifest-out",type=Path,default=None,
                        help="write only public R206 manifest, CREATE-ONLY after actual full finalized proof")
    args=parser.parse_args(argv)
    try:
        m=load_artifact(root/"out/SSEAdaptiveMarketV2.sol/SSEAdaptiveMarketV2.json")
        l=load_artifact(root/"out/SSEAdaptiveVoteLedger.sol/SSEAdaptiveVoteLedger.json")
        result=verify(args.rpc,m,l)
        if args.manifest_out:
            write_manifest(args.manifest_out,result["manifest"])
        print(json.dumps(result,indent=2,sort_keys=True))
        print("R260_REAL_NATIVE_V2_MARKET_AND_LEDGER_FINALIZED_AND_R206_VERIFIED=true")
        return 0
    except Pending as exc:
        print("R260_NOT_FINAL_YET_DO_NOT_RESEND="+json.dumps({
            "stage":exc.stage,**exc.numbers},sort_keys=True),file=sys.stderr)
        return 3
    except (Refused,ValueError,TypeError,KeyError,ImportError,OSError) as exc:
        print("R260_DEPLOYMENT_AUDIT_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
