#!/usr/bin/env python3
"""R257: GATED owner-local one-time native chain31340 V2 create transaction.

DEFAULT: public/read-only quote and finalized R255 funding verification.
--send is a distinct owner-approved operation: interactive TTY confirmation,
private locally encrypted app-only keystore, fixed 1e15 TEST-ETH-wei monitor
bond, fixed legacy gas price<=1000 wei and limit<=8342601, nonce0, original
genesis, canonical finalized funding, fixed SHA-pinned compiled ABI/initcode,
one-shot attempt marker BEFORE one raw transaction RPC call.

IMPORTANT: Staging this tool in GitHub is NOT consent to broadcast. No
transaction is sent unless the owner separately authorizes deployment and
runs --send with a typed local confirmation. Never use Genesis/BLS keys.
"""
from __future__ import annotations

import argparse
from getpass import getpass, getuser
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import rpc as rpc_transport
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r255_v2_funding_finalized_audit import verify as verify_funding, Pending as FundingPending
from sse_pos_r256_v2_readonly_native_deployment_quote import (
    RPC, APP, CHAIN, GENESIS, pin_artifacts,
    q, quote as quote_deployment,
)
from sse_pos_r247_v2_compiled_abi_parity import load_artifact

BOND_WEI = 10**15  # unapproved scenario until owner separately authorizes immutable policy
GAS_LIMIT = 8_342_601
GAS_PRICE_WEI = 1_000
MAX_FEE_WEI = GAS_LIMIT * GAS_PRICE_WEI
EXPECTED_NONCE = 0
CONFIRM = "DEPLOY-ONE-V2-CHAIN31340-BOND-0.001-TEST-ETH"
ROLE = "adaptive-v2-deployer"
KEY_NAME = ROLE + ".keystore.json"
MARKER_NAME = ".r257-one-time-v2-contract-deployment-attempted"


class Refused(ValueError):
    pass


def create_address(owner):
    """CREATE address for source EOA nonce0 via exact RLP [20-byte addr,0]."""
    from eth_utils import keccak, to_checksum_address
    raw=bytes.fromhex(owner[2:])
    if len(raw)!=20:
        raise Refused("invalid app create source address")
    return to_checksum_address(keccak(b"\xd6\x94"+raw+b"\x80")[-20:])


def check_git(expected_sha):
    root=Path(__file__).resolve().parents[1]
    if (type(expected_sha) is not str or len(expected_sha)!=40 or
        any(c not in "0123456789abcdef" for c in expected_sha)):
        raise Refused("exact 40-digit immutable Git commit SHA required")
    try:
        actual=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,
                                       text=True,timeout=4).strip()
        dirty=subprocess.check_output(["git","status","--porcelain",
                                       "--untracked-files=no"],cwd=root,
                                       text=True,timeout=4).strip()
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise Refused("cannot verify pinned local Git source") from exc
    if actual!=expected_sha or dirty:
        raise Refused("checked-out source SHA mismatch or tracked source edits")
    return root


def owner_private_paths():
    home=Path.home()
    folder=home/".local"/"share"/"sse-v2-app-only"
    return folder/KEY_NAME, folder/MARKER_NAME


def preflight(market,ledger,*,transport=rpc_transport,quote_fn=quote_deployment,
              funding_fn=verify_funding):
    # First independently prove the exact owner-authorized funding is FINAL.
    report=funding_fn(RPC,transport=transport)
    if (report.get("fundingTxCanonicalAndFinalizedVerified") is not True or
        report.get("recipientBalanceWeiAtFinalized") is None or
        q(hex(int(report["recipientBalanceWeiAtFinalized"])), "funded balance") < 10**18 or
        report.get("sourceNonceAtFinalized",0) < 1):
        raise Refused("exact canonical finalized R255 funding not attested")

    offer=quote_fn(RPC,market,ledger,BOND_WEI,transport=transport)
    if (offer.get("chainId") != CHAIN or
        offer.get("originalExecutionGenesisVerified") is not True or
        offer.get("marketCompilerAbiMatchedR249") is not True or
        offer.get("ledgerCompilerAbiMatchedR249") is not True or
        offer.get("deploymentSigner", "").lower() != APP.lower() or
        offer.get("quoteOnlyNoPrivateKeysNoTransactionNoDeployment") is not True or
        offer.get("minimumBondWeiQuoteScenarioOnly") != str(BOND_WEI)):
        raise Refused("compiled native V2 gas quote does not match authorized immutable scenario")

    estimated=offer["actualNodeEstimatedConstructorGas"]
    padded=offer["paddedGasLimitScenario"]
    node_price=int(offer["actualNodeGasPriceWei"])
    base=offer["actualNodeBaseFeeWeiPerGas"]
    if (type(estimated) is not int or type(padded) is not int or
        not 0 < estimated <= padded <= GAS_LIMIT or
        not 0 < node_price <= GAS_PRICE_WEI or
        (base is not None and int(base)>GAS_PRICE_WEI) or
        int(offer["balanceWeiAtFinalized"]) < 10**18 or
        int(offer["currentBalanceWeiAtLatest"]) < 10**18 or
        MAX_FEE_WEI > int(offer["balanceWeiAtFinalized"])):
        raise Refused("real finalized app funds or gas policy exceed fixed single-deployment cap")

    latest_nonce=q(transport(RPC,"eth_getTransactionCount",[APP,"latest"]),"latest app nonce")
    pending_nonce=q(transport(RPC,"eth_getTransactionCount",[APP,"pending"]),"pending app nonce")
    if latest_nonce!=EXPECTED_NONCE or pending_nonce!=EXPECTED_NONCE:
        raise Refused("app account has pending/sent transaction; refuse duplicate deployment")

    address=create_address(APP)
    if transport(RPC,"eth_getCode",[address,"latest"])!="0x":
        raise Refused("predicted new deployment address already has contract code")
    code=pin_artifacts(market,ledger,BOND_WEI)
    return {
        "schema":"SSE_R257_V2_SINGLE_CREATE_OWNER_REVIEW_V1",
        "chainId":CHAIN,
        "originalExecutionGenesisHash":GENESIS,
        "r255FundingCanonicalAndFinalized":True,
        "fundingTransactionHash":report["transactionHash"],
        "deployer":APP,
        "deployerPendingNonce":EXPECTED_NONCE,
        "predictedMarketCreateAddress":address,
        "constructorBondWei":str(BOND_WEI),
        "constructorBondExperimentOnlyNotSybilSecurity":True,
        "transactionValueWei":"0",
        "gasLimit":GAS_LIMIT,
        "gasPriceWei":GAS_PRICE_WEI,
        "maximumTransactionGasFeeWei":str(MAX_FEE_WEI),
        "nodeActualGasEstimate":estimated,
        "nodeQuoteGasPriceWei":str(node_price),
        "currentFinalizedBalanceWei":offer["balanceWeiAtFinalized"],
        "initcodeSha256":hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),
        "initcode":code,  # PUBLIC contract initcode, but avoid printing it in TTY
        "signedOrBroadcast":False,
        "separateOwnerApprovalStillRequired":True,
    }


def public_intent(intent):
    return {k:v for k,v in intent.items() if k!="initcode"}


def consume_one_shot_marker(path):
    # Non-symlink create-exclusively; NO marker deletion on RPC errors.
    flags=os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path,flags,0o600)
        with os.fdopen(fd,"w",encoding="ascii") as stream:
            stream.write("R257 one-time deployment attempt consumed. DO NOT RE-RUN.\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise Refused("one-time deploy authorization already attempted; inspect chain before any next action") from exc


def send_once(market,ledger,keystore,marker,*,transport=rpc_transport,
              preflight_fn=preflight,confirm=input,password_prompt=getpass,
              tty=True):
    if tty and (not sys.stdin.isatty() or not sys.stderr.isatty()):
        raise Refused("owner terminal required for live deployment")
    if (os.geteuid()==0 or getuser()!="ayoubakrvm4707" or
        keystore!=owner_private_paths()[0] or marker!=owner_private_paths()[1]):
        raise Refused("live deploy requires VM4707 nonroot application-only private wallet")
    if marker.exists() or marker.is_symlink():
        raise Refused("previous deployment attempt marker found; NEVER retry automatically")
    intent=preflight_fn(market,ledger,transport=transport)
    print("R257_DEPLOYMENT_INTENT_NOT_YET_AUTHORIZED="+
          json.dumps(public_intent(intent),sort_keys=True),flush=True)
    if confirm("Type "+CONFIRM+" to authorize EXACTLY ONE V2 contract creation: ")!=CONFIRM:
        raise Refused("owner did not authorize this one specific immutable V2 deployment")
    document=safe_keystore(keystore)
    password=password_prompt("VM4707 ENCRYPTED APPLICATION wallet password (hidden): ")
    if not password:
        raise Refused("encrypted application wallet password missing")
    try:
        from eth_account import Account
        private=Account.decrypt(document,password)
    except (ImportError,ValueError,TypeError,KeyError) as exc:
        raise Refused("app-only encrypted wallet unlock failed") from exc
    try:
        account=Account.from_key(private)
        if account.address.lower()!=APP.lower():
            raise Refused("encrypted app EOA public identity does not match actual funded deployer")
        # A fresh read-only preflight protects against a stale quote after
        # owner approval. Refuse if any fixed tx property or code changes.
        renewed=preflight_fn(market,ledger,transport=transport)
        keys=("deployer","deployerPendingNonce","predictedMarketCreateAddress",
              "constructorBondWei","gasLimit","gasPriceWei","initcodeSha256")
        if any(renewed[k]!=intent[k] for k in keys):
            raise Refused("live deployment intent changed after approval")
        tx={
            "chainId":CHAIN,
            "nonce":EXPECTED_NONCE,
            "gas":GAS_LIMIT,
            "gasPrice":GAS_PRICE_WEI,
            "to":"",  # Empty destination is Ethereum CREATE, not a call to another wallet.
            "value":0,
            "data":bytes.fromhex(renewed["initcode"][2:]),
        }
        signed=Account.sign_transaction(tx,private)
        raw="0x"+bytes(signed.raw_transaction).hex()
        txhash="0x"+bytes(signed.hash).hex()
        if Account.recover_transaction(raw).lower()!=APP.lower():
            raise Refused("offline signed deployment tx does not recover intended app-only EOA")
        # NON-RETRIABLE boundary. If RPC fails after this line, investigate
        # txhash and chain nonce/receipt. Never delete this marker casually.
        consume_one_shot_marker(marker)
        print("R257_ONE_TIME_DEPLOYMENT_ATTEMPT_CONSUMED=true",flush=True)
        print("R257_PRECOMPUTED_PUBLIC_DEPLOYMENT_TX_HASH="+txhash,flush=True)
        returned=transport(RPC,"eth_sendRawTransaction",[raw])
        if type(returned) is not str or returned.lower()!=txhash.lower():
            raise Refused("RPC acknowledgement hash differs from locally signed one; do not resend")
        return {
            "schema":"SSE_R257_SUBMITTED_ONE_NATIVE_V2_CREATION_V1",
            "chainId":CHAIN,"source":APP,"nonce":EXPECTED_NONCE,
            "transactionHash":txhash,
            "expectedMarketCreateAddress":renewed["predictedMarketCreateAddress"],
            "constructorBondWei":str(BOND_WEI),
            "gasLimit":GAS_LIMIT,"gasPriceWei":GAS_PRICE_WEI,
            "maximumGasFeeWei":str(MAX_FEE_WEI),
            "oneRawSignedTransactionSubmitted":True,
            "finalizedDeploymentVerified":False,
            "privateKeyOrPasswordPrinted":False,
        }
    finally:
        del private,password


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-sha",required=True,
                   help="exact pinned Git commit; refuse dirty/mismatched source")
    p.add_argument("--rpc",choices=(RPC,),required=True)
    p.add_argument("--send",action="store_true",
                   help="only after distinct owner authorization of immutable bond/gas cap")
    a=p.parse_args(argv)
    try:
        root=check_git(a.source_sha)
        m=load_artifact(root/"out/SSEAdaptiveMarketV2.sol/SSEAdaptiveMarketV2.json")
        l=load_artifact(root/"out/SSEAdaptiveVoteLedger.sol/SSEAdaptiveVoteLedger.json")
        if not a.send:
            # This is the ONLY mode to use until separate deployment approval.
            intent=preflight(m,l)
            print(json.dumps(public_intent(intent),indent=2,sort_keys=True))
            print("R257_REAL_V2_DEPLOYMENT_PREVIEW_ONLY_NO_TRANSACTION=true")
            return 0
        key,marker=owner_private_paths()
        output=send_once(m,l,key,marker)
        print(json.dumps(output,indent=2,sort_keys=True))
        print("R257_ONE_SIGNED_DEPLOYMENT_SUBMITTED_NOT_YET_FINALIZED=true")
        return 0
    except FundingPending as exc:
        print("R257_DEPLOYMENT_REFUSED_FUNDING_NOT_FINAL: "+str(exc),file=sys.stderr)
        return 3
    except (Refused,OSError,ValueError,TypeError,KeyError,ImportError,
            subprocess.SubprocessError) as exc:
        print("R257_DEPLOYMENT_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
