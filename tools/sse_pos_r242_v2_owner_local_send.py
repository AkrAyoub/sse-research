#!/usr/bin/env python3
"""R242: deliberately opt-in V2 native TEST ETH app-role transaction sender.

Default: R206-verified, original-chain READ-ONLY R239 estimate/balance quote.
ONLY --send + owner-local encrypted *separate application* UTC-V3 EOA,
correct public address, interactive TTY, explicit typed authorization and
bounded total wei can transmit ONE signed raw tx. Never touches original
chain31340 genesis owner wallet, validator/BLS signing, JWT or Docker.
Prints only public tx hash/receipt and canonical inclusion/finality status,
never private key, password, keystore JSON or raw signed tx bytes.

**SOURCE-ONLY UNTIL LIVE VM GATES PASS AND OWNER EXPLICITLY APPROVES.**
"""
from __future__ import annotations

import argparse
import fcntl
import os
import stat
from contextlib import contextmanager
from getpass import getpass
import json
from pathlib import Path
import sys
import time

from sse_pos_r226_adaptive_v2_transaction_planner import (
    Refused as PlannerRefused, build as build_plan,
    verify_funded_bid,
)
from sse_pos_r237_v2_approved_local_eip712_sign import (
    Refused as WalletRefused, safe_keystore, ORIGINAL_GENESIS_EOA,
)
from sse_pos_r239_v2_real_gas_quote import (
    Refused as QuoteRefused, quote, number as rpc_number,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,
    rpc as rpc_transport,verify as verify_deployment,
)

from sse_pos_r351_transaction_journal import record_intent, reconcile

AUTHORIZE="AUTHORIZE-ONE-V2-CHAIN31340-TRANSACTION"
MAX_RECEIPT_POLLS=24


class Refused(ValueError):
    pass


def readonly_quote(manifest,rpc_url,action,role,params,from_address,max_wei,
                   *,transport=rpc_transport):
    proof=verify_deployment(manifest,rpc_url,transport=transport)
    plan=build_plan(action,role,params,manifest["market"]["address"],
                    manifest["ledger"]["address"])
    if action=="fund":
        verify_funded_bid(plan,params,manifest,rpc_url,transport=transport)
    if action=="monitor-register" and plan.value_wei<int(manifest["minimumBondWei"]):
        raise Refused("monitor registration below immutable real minimum bond")
    offer=quote(plan,from_address,manifest,rpc_url,
                max_total_wei=max_wei,attestation=proof,transport=transport)
    return plan,offer


@contextmanager
def journal_lock(root,sender):
    root=Path(root)
    if not root.is_absolute():
        raise Refused("absolute journal path required")
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.geteuid() or root.stat().st_mode & 0o077:
        raise Refused("owner-private journal directory required")
    if len(sender)!=42 or not sender.startswith("0x") or any(c not in "0123456789abcdef" for c in sender[2:]):
        raise Refused("invalid journal sender")
    fd=os.open(root/(sender+".lock"),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode & 0o077:
            raise Refused("unsafe wallet lock")
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Refused("another local journaled wallet operation is active") from exc
        yield root
    finally:
        os.close(fd)


def submit_once(plan,offer,manifest,rpc_url,app_keystore,*,confirm,get_password,
                transport=rpc_transport,tty=True,sleep=time.sleep,journal_dir=None):
    if journal_dir is None:
        return _submit_once(plan,offer,manifest,rpc_url,app_keystore,confirm=confirm,
                            get_password=get_password,transport=transport,tty=tty,sleep=sleep)
    sender=offer["applicationSignerPublic"].lower()
    with journal_lock(journal_dir,sender) as root:
        for path in sorted(root.glob(sender+"-*.json")):
            if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
                raise Refused("unsafe prior journal entry")
            entry=json.loads(path.read_text())
            if entry.get("sender")!=sender or path.name!=sender+"-"+str(entry.get("nonce"))+".json":
                raise Refused("prior journal identity mismatch")
            result=reconcile(entry,manifest,rpc_url,transport=transport)
            if result["status"] not in ("CANONICAL_SUCCESS","CANONICAL_REVERTED","FINALIZED_SUCCESS","FINALIZED_REVERTED"):
                raise Refused("unresolved prior transaction: "+entry["transactionHash"])
            if (entry["target"].lower()==plan.target.lower() and entry["calldata"].lower()==plan.calldata.lower()
                    and entry["valueWei"]==plan.value_wei and not result["terminal"]):
                raise Refused("identical provisional action already recorded")
        return _submit_once(plan,offer,manifest,rpc_url,app_keystore,confirm=confirm,
                            get_password=get_password,transport=transport,tty=tty,sleep=sleep,journal_dir=root)


def _submit_once(plan,offer,manifest,rpc_url,app_keystore,*,confirm,get_password,
                transport=rpc_transport,tty=True,sleep=time.sleep,journal_dir=None):
    if tty and (not sys.stdin.isatty() or not sys.stderr.isatty()):
        raise Refused("owner-interactive terminal required for any signed transaction")
    if (offer.get("transactionSignedOrSubmitted") is not False or
        offer.get("originalGenesisR206Verified") is not True or
        offer.get("realRpcEthEstimateGasCalled") is not True or
        offer["action"]!=plan.action or offer["target"]!=plan.target or
        offer["calldata"]!=plan.calldata or
        int(offer["valueWei"])!=plan.value_wei):
        raise Refused("signed transaction differs from approved real RPC quote")
    sender=offer["applicationSignerPublic"].lower()
    if sender==ORIGINAL_GENESIS_EOA:
        raise Refused("refuse original chain genesis owner EOA")
    print("R242_PUBLIC_TRANSACTION_AUTHORIZATION="+json.dumps({
        "chainId":31340,
        "deployerMarket":manifest["market"]["address"],
        "action":plan.action,"role":plan.role,"from":sender,
        "to":plan.target,
        "data":plan.calldata,"valueWei":offer["valueWei"],
        "maxQuotedBudgetWei":offer["estimatedUpperBudgetWei"],
        "userMaxTotalSpendWei":offer["ownerMaxTotalSpendWei"],
        "transactionSignedOrSubmitted":False,
    },sort_keys=True),flush=True)
    response=confirm("Type "+AUTHORIZE+" to sign and broadcast EXACTLY ONE native V2 transaction: ")
    if response!=AUTHORIZE:
        raise Refused("owner did not authorize this exact V2 transaction")
    keystore=safe_keystore(app_keystore)
    password=get_password("Separate local APPLICATION EOA password (hidden): ")
    if not password:
        raise Refused("encrypted app wallet password required")
    try:
        from eth_account import Account
        from eth_utils import to_checksum_address
    except ImportError as exc:
        raise Refused("pinned eth-account unavailable for explicitly approved signer") from exc
    try:
        private=Account.decrypt(keystore,password)
    except (ValueError,TypeError,KeyError) as exc:
        raise Refused("separate encrypted app wallet unlock refused") from exc
    try:
        account=Account.from_key(private)
        if account.address.lower()!=sender:
            raise Refused("local app key public address does not match reviewed quote")
        # Fresh pending nonce. This code cannot protect against a parallel
        # signer using the SAME app EOA; real operation requires one owner.
        nonce=rpc_number(transport(rpc_url,"eth_getTransactionCount",
                                   [sender,"pending"]),"pending nonce")
        gas=int(offer["paddedGasLimit"])
        price=int(offer["observedGasPriceWei"])
        if (gas<=0 or price<=0 or
            gas*price+plan.value_wei>int(offer["ownerMaxTotalSpendWei"])):
            raise Refused("operator maximum spend exceeded at submission")
        # Re-estimate immediately after owner confirmation to fail closed
        # when the transaction phase/nonce state has moved.
        query={
            "from":sender,"to":plan.target,"value":hex(plan.value_wei),
            "data":plan.calldata,
        }
        renewed=rpc_number(transport(rpc_url,"eth_estimateGas",[query]),
                           "fresh live gas estimate")
        if renewed>gas:
            raise Refused("fresh node gas estimate exceeds approved padded limit")
        tx={
            "chainId":31340,"nonce":nonce,"gas":gas,
            "gasPrice":price,"to":to_checksum_address(plan.target),
            "value":plan.value_wei,"data":plan.calldata
        }
        signed=account.sign_transaction(tx)
        txhash="0x"+bytes(signed.hash).hex()
        if journal_dir is not None:
            intent=record_intent(journal_dir,manifest,sender,nonce,txhash,plan.action,plan.target,plan.calldata,plan.value_wei)
            print("R351_DURABLE_INTENT="+str(intent),flush=True)
        # Single explicit send; no automatic retry or rebroadcast.
        returned=transport(rpc_url,"eth_sendRawTransaction",[
            "0x"+bytes(signed.raw_transaction).hex()])
        if type(returned) is not str or returned.lower()!=txhash.lower():
            raise Refused("node did not acknowledge expected signed tx hash")
    finally:
        del private,password
    output={
        "schema":"SSE_R242_V2_PUBLIC_OWNER_AUTHORIZED_NATIVE_TX_V1",
        "chainId":31340,"from":sender,"to":plan.target,
        "action":plan.action,"role":plan.role,
        "transactionHash":txhash,
        "actualOriginalChainTransactionSubmitted":True,
        "separateApplicationKeyUsed":True,
        "privateKeyOrPasswordPrinted":False,
        "validatorOrDockerChanged":False,
        "physicalSlaVerified":False,
    }
    for _ in range(MAX_RECEIPT_POLLS):
        result=transport(rpc_url,"eth_getTransactionReceipt",[txhash])
        if result is None:
            sleep(1)
            continue
        if (type(result) is not dict or
            type(result.get("transactionHash")) is not str or
            result["transactionHash"].lower()!=txhash.lower()):
            raise Refused("receipt tx hash does not match locally signed transaction")
        if rpc_number(result.get("status"),"receipt status")!=1:
            raise Refused("native V2 transaction reverted; transactionHash="+txhash)
        height=rpc_number(result.get("blockNumber"),"receipt inclusion height")
        block=transport(rpc_url,"eth_getBlockByNumber",[hex(height),False])
        if (type(block) is not dict or
            type(block.get("hash")) is not str or
            type(result.get("blockHash")) is not str or
            block["hash"].lower()!=result["blockHash"].lower()):
            raise Refused("noncanonical transaction inclusion; txHash="+txhash)
        output.update({"receiptSuccessful":True,"includedBlock":height,
                       "gasUsed":rpc_number(result.get("gasUsed"),"receipt gas used")})
        finalized=transport(rpc_url,"eth_getBlockByNumber",["finalized",False])
        if (type(finalized) is dict and
            rpc_number(finalized.get("number"),"finalized block")>=height):
            output["executionFinalized"]=True
        else:
            output["executionFinalized"]=False
        # Beacon consensus finality should be checked independently with
        # a current R141 capture from each genuinely separate VM.
        output["beaconFinalityCrossHostVerified"]=False
        return output
    output["receiptSuccessful"]=None
    output["executionFinalized"]=False
    output["beaconFinalityCrossHostVerified"]=False
    return output


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",required=True,choices=(
        "http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--action",required=True)
    p.add_argument("--role",required=True)
    p.add_argument("--params-json",required=True,help="PUBLIC V2 action arguments only")
    p.add_argument("--from-address",required=True,
                   help="separate app-only EOA address, not the original genesis wallet")
    p.add_argument("--max-total-wei",type=int,required=True)
    p.add_argument("--send",action="store_true",
                   help="owner-only interactive APPROVED actual native transaction")
    p.add_argument("--keystore",type=Path,
                   help="private encrypted application V3 EOA, --send only")
    p.add_argument("--journal-dir",type=Path,help="owner-private durable intent journal; defaults to local application journal in send mode")
    a=p.parse_args(argv)
    try:
        if a.journal_dir is not None and not a.send:
            raise Refused("journal option requires send mode")
        if bool(a.send)!=bool(a.keystore):
            raise Refused("--send and encrypted application keystore required together")
        manifest=load_manifest(a.manifest)
        params=json.loads(a.params_json)
        plan,offer=readonly_quote(manifest,a.rpc,a.action,a.role,params,
                                  a.from_address,a.max_total_wei)
        if not a.send:
            print(json.dumps({
                **offer,
                "approvalRequiredBeforeAnyTransaction":True,
                "applicationWalletRead":False,
            },sort_keys=True,indent=2))
            return 0
        result=submit_once(plan,offer,manifest,a.rpc,a.keystore,
                           confirm=input,get_password=getpass,
                           journal_dir=a.journal_dir or (Path.home()/".local/share/sse-transaction-journal"))
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,PlannerRefused,WalletRefused,QuoteRefused,AuditRefused,
            TypeError,ValueError,OverflowError,OSError,KeyError) as exc:
        print("R242_REAL_V2_OWNER_TRANSACTION_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
