#!/usr/bin/env python3
"""R267: exact THREE newly-created VM4707 role EOAs: safe native TEST ETH funding.

DEFAULT --role: actual chain31340 finalized-deployment READ-ONLY funding
intent. No keys, signing or sends. --send: only after SEPARATE funding
authorization from the owner, on VM4707 nonroot interactive TTY, hidden
password for the EXISTING app-only deployer encrypted keystore, exact
public recipient/value/legacy gas/chain/nonce, per-role write-once marker
BEFORE exactly one eth_sendRawTransaction. NO automatic retries, no
background work, no nonce replacement/bumping, no original Genesis/BLS keys.
A role N is never even eligible for --send until all prior role funding txs
are ACTUALLY successful, canonical and finalized. Single-use markers are
public audit metadata in private owner files, NOT secrets.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import pwd
import stat
import sys

from sse_pos_r206_adaptive_v2_deployment_audit import (
    rpc as local_rpc, load as load_manifest, verify as verify_r206,
)
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r257_vm4707_one_time_v2_deployment import (
    check_git, owner_private_paths,
)
from sse_pos_r260_v2_readonly_finalized_deployment_audit import quantity
from sse_pos_r265_vm4707_three_role_wallet_funding_quote import (
    RECIPIENTS, RPC, CHAIN, GENESIS, APP, MARKET,
    ORIGINAL_FUNDER, GAS_PRICE_CAP_WEI as GAS_PRICE,
    GAS_PER_TRANSFER as GAS_LIMIT,
)
from sse_pos_r265_vm4707_three_role_wallet_funding_quote import (
    BOND_WEI as BOND,
)

MANIFEST="evidence/r261_vm4707_latest_state_v2_deployment_candidate.json"
OWNER="ayoubakrvm4707"
APP_KEY_NAME="adaptive-v2-deployer.keystore.json"
ATTEMPT_PREFIX=".r267-one-time-"
RAW_TX_CALL="eth_sendRawTransaction"


class Refused(ValueError):
    pass


class Pending(Exception):
    pass


def role_index(role):
    names=tuple(x[0] for x in RECIPIENTS)
    if role not in names:
        raise Refused("unknown exact R265 approved-preview role")
    return names.index(role)


def private_paths(role):
    index=role_index(role)
    key, deploy_marker=owner_private_paths()
    if key.name!=APP_KEY_NAME:
        raise Refused("unexpected VM4707 application signing-keystore name")
    marker=key.parent/(ATTEMPT_PREFIX+RECIPIENTS[index][0]+"-funding-attempted.json")
    return key,deploy_marker,marker


def require_private_owner_path(path):
    if (not isinstance(path,Path) or not path.is_absolute() or
        path.is_symlink() or not path.is_file() or path.parent.is_symlink()):
        raise Refused("existing private owner funding metadata file missing/linked")
    s=path.stat()
    if (s.st_uid!=os.geteuid() or
        stat.S_IMODE(s.st_mode)!=0o600 or
        s.st_size<=0 or s.st_size>4096):
        raise Refused("existing private marker ownership/permissions/size invalid")
    return path.read_bytes()


def read_marker(role):
    _,_,marker=private_paths(role)
    raw=require_private_owner_path(marker)
    try:
        doc=json.loads(raw)
    except (UnicodeError,ValueError) as exc:
        raise Refused("existing funding marker malformed") from exc
    expected=RECIPIENTS[role_index(role)]
    if (type(doc) is not dict or
        set(doc)!={"schema","role","source","recipient","valueWei",
                   "nonce","gasLimit","gasPriceWei","txHash"} or
        doc["schema"]!="SSE_R267_SINGLE_ROLE_FUNDING_ATTEMPT_V1" or
        doc["role"]!=role or
        str(doc["source"]).lower()!=APP.lower() or
        str(doc["recipient"]).lower()!=expected[1].lower() or
        doc["valueWei"]!=str(expected[2]) or
        type(doc["nonce"]) is not int or
        doc["nonce"]!=1+role_index(role) or
        doc["gasLimit"]!=GAS_LIMIT or doc["gasPriceWei"]!=GAS_PRICE or
        type(doc["txHash"]) is not str or
        len(doc["txHash"])!=66 or
        any(c not in "0123456789abcdef" for c in doc["txHash"][2:]) or
        not doc["txHash"].startswith("0x")):
        raise Refused("previous funding attempted marker differs from immutable plan")
    return doc


def record_marker(path,role,txhash):
    idx=role_index(role)
    source,recipient,value=APP,RECIPIENTS[idx][1],RECIPIENTS[idx][2]
    payload={
        "schema":"SSE_R267_SINGLE_ROLE_FUNDING_ATTEMPT_V1",
        "role":role,"source":source,"recipient":recipient,
        "valueWei":str(value),"nonce":1+idx,
        "gasLimit":GAS_LIMIT,"gasPriceWei":GAS_PRICE,
        "txHash":txhash,
    }
    if path!=private_paths(role)[2] or path.exists() or path.is_symlink():
        raise Refused("funding attempt marker already exists; never resend")
    data=(json.dumps(payload,sort_keys=True)+"\n").encode("ascii")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path,flags,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError as exc:
        raise Refused("funding marker created by another process; never resend") from exc
    return payload


def check_previous_role_finalized(url,role,final_height,*,transport=local_rpc,
                                   read_marker_fn=read_marker):
    """Prior consecutive app nonces must match actual canonical finalized transfers."""
    doc=read_marker_fn(role)
    ask=lambda method,params:transport(url,method,params)
    tx=ask("eth_getTransactionByHash",[doc["txHash"]])
    receipt=ask("eth_getTransactionReceipt",[doc["txHash"]])
    if tx is None or receipt is None:
        raise Pending("previous role funding TX not yet included; DO NOT RESEND")
    if type(tx) is not dict or type(receipt) is not dict:
        raise Refused("previous role tx/receipt malformed")
    if (str(tx.get("hash","")).lower()!=doc["txHash"] or
        str(tx.get("from","")).lower()!=APP.lower() or
        str(tx.get("to","")).lower()!=doc["recipient"].lower() or
        quantity(tx.get("value"),"earlier funding value")!=int(doc["valueWei"]) or
        quantity(tx.get("nonce"),"earlier funding nonce")!=doc["nonce"] or
        quantity(tx.get("gas"),"earlier funding gas limit")!=GAS_LIMIT or
        quantity(tx.get("gasPrice"),"earlier funding gas price")!=GAS_PRICE or
        tx.get("input")!="0x" or
        str(receipt.get("transactionHash","")).lower()!=doc["txHash"] or
        quantity(receipt.get("status"),"earlier receipt status")!=1 or
        str(receipt.get("from","")).lower()!=APP.lower() or
        str(receipt.get("to","")).lower()!=doc["recipient"].lower() or
        receipt.get("contractAddress") is not None or
        quantity(receipt.get("gasUsed"),"earlier gas used")!=GAS_LIMIT):
        raise Refused("previous actual role funding tx not exact or failed")
    if tx.get("chainId") is not None and quantity(tx["chainId"],"earlier chainId")!=CHAIN:
        raise Refused("previous funding signed for wrong blockchain")
    included=quantity(receipt.get("blockNumber"),"earlier receipt block")
    canonical=ask("eth_getBlockByNumber",[hex(included),False])
    if (included<=0 or type(canonical) is not dict or
        str(canonical.get("hash","")).lower()!=
        str(receipt.get("blockHash","")).lower()):
        raise Refused("previous role funding receipt no longer canonical")
    if included>final_height:
        raise Pending("previous role funding not yet finalized; DO NOT RESEND")
    remaining=quantity(ask("eth_getBalance",[doc["recipient"],"latest"]),
                       "previous recipient latest balance")
    if remaining<int(doc["valueWei"]):
        raise Refused("previous funded role wallet spent unexpectedly before next stage")
    return doc


def preflight(role,*,transport=local_rpc,verify_fn=verify_r206,
              prior_fn=check_previous_role_finalized):
    idx=role_index(role)
    key,deploy_marker,marker=private_paths(role)
    if marker.exists() or marker.is_symlink():
        raise Refused("this role already has a consumed funding attempt marker. NEVER RETRY")
    ask=lambda method,params:transport(RPC,method,params)
    # Real finalized R206 receipt + both runtime hashes + mutual getters
    # REQUIRED before real role-wallet TEST ETH movement.
    root=Path(__file__).resolve().parents[1]
    manifest=load_manifest(root/MANIFEST)
    audit=verify_fn(manifest,RPC,transport=transport)
    if (audit.get("deploymentReceiptSuccessfulAndFinalized") is not True or
        audit.get("runtimeCodeSha256Verified") is not True or
        audit.get("mutualMarketLedgerBindingsVerified") is not True or
        audit.get("chainId")!=CHAIN or
        manifest["deployer"].lower()!=APP.lower() or
        manifest["market"]["address"].lower()!=MARKET.lower() or
        manifest["minimumBondWei"]!=str(BOND)):
        raise Refused("exact original V2 contract R206 FINALIZED prerequisite is missing")
    final_height=audit["finalizedExecutionHeight"]
    if type(final_height) is not int or final_height<25339:
        raise Refused("original V2 deployment not actually finalized")

    for prior_role,_,_ in RECIPIENTS[:idx]:
        prior_fn(RPC,prior_role,final_height,transport=transport)
    nonce=quantity(ask("eth_getTransactionCount",[APP,"pending"]),"source pending nonce")
    confirmed_nonce=quantity(ask("eth_getTransactionCount",[APP,"latest"]),"source latest nonce")
    if nonce!=1+idx or confirmed_nonce!=1+idx:
        raise Refused("source has wrong pending/latest nonce for exact one-use role funding")
    if ask("eth_getCode",[APP,"latest"])!="0x":
        raise Refused("funding source unexpectedly has contract code")
    _,target,value=RECIPIENTS[idx]
    if (target.lower() in (APP.lower(),MARKET.lower(),ORIGINAL_FUNDER.lower()) or
        len(set(x[1].lower() for x in RECIPIENTS))!=len(RECIPIENTS)):
        raise Refused("invalid or duplicate fixed research funding recipient")
    if ask("eth_getCode",[target,"latest"])!="0x":
        raise Refused("recipient is contract, not the newly created EOA")
    if quantity(ask("eth_getBalance",[target,"latest"]),"recipient balance")!=0:
        raise Refused("recipient already funded/spent; do not duplicate")
    if quantity(ask("eth_getTransactionCount",[target,"pending"]),"recipient nonce")!=0:
        raise Refused("recipient account has pending tx activity; refuse funding")
    quote=quantity(ask("eth_estimateGas",[{
        "from":APP,"to":target,"value":hex(value),"data":"0x"
    }]),"real 21000 EOA transfer estimate")
    if quote!=GAS_LIMIT:
        raise Refused("node did not estimate simple transfer as exactly 21000 gas")
    price=quantity(ask("eth_gasPrice",[]),"node gas price")
    head=ask("eth_getBlockByNumber",["latest",False])
    if type(head) is not dict:
        raise Refused("head block unavailable")
    base=head.get("baseFeePerGas")
    if (price<=0 or price>GAS_PRICE or
        (base is not None and quantity(base,"base fee")>GAS_PRICE)):
        raise Refused("node gas conditions exceed exact 1000 wei/gas approved scenario")
    if quantity(head.get("gasLimit"),"block gas limit")<GAS_LIMIT:
        raise Refused("live block gas limit cannot hold native EOA transfer")
    balance=quantity(ask("eth_getBalance",[APP,"latest"]),"real APP balance")
    remaining=RECIPIENTS[idx:]
    needed=sum(v for _,_,v in remaining)+len(remaining)*GAS_LIMIT*GAS_PRICE
    if balance<needed:
        raise Refused("remaining approved-scenario funding and fees exceed actual source balance")
    return {
        "schema":"SSE_R267_ONE_EXACT_UNAUTHORIZED_ROLE_FUNDING_PREVIEW_V1",
        "role":role,"chainId":CHAIN,"originalGenesisVerified":True,
        "finalizedDeploymentR206Verified":True,
        "deploymentFinalizedBlock":audit["finalizedExecutionHeight"],
        "source":APP,"recipient":target,"sourceNonce":nonce,
        "valueWei":str(value),"gasLimit":GAS_LIMIT,
        "gasPriceWei":GAS_PRICE,
        "maximumFeeWei":str(GAS_LIMIT*GAS_PRICE),
        "maximumSingleDebitWei":str(value+GAS_LIMIT*GAS_PRICE),
        "sourceLatestBalanceWei":str(balance),
        "remainingStagesIncludingThis":len(remaining),
        "cumulativeRemainingScenarioDebitWei":str(needed),
        "recipientHasZeroBalanceZeroNonceAndNoCode":True,
        "realRpcExact21000GasEstimate":True,
        "previousRoleTransfersCanonicalAndFinalized":True,
        "transactionAuthorized":False,
        "keyOrPasswordRead":False,
        "transactionSignedOrSubmitted":False,
    }


def verify_signed_legacy_transfer(raw,role):
    """RLP-decode actually signed legacy EIP155 transfer before any broadcast."""
    import rlp
    idx=role_index(role)
    expected=RECIPIENTS[idx]
    if type(raw) is not str or not raw.startswith("0x"):
        raise Refused("invalid signed raw RLP")
    fields=rlp.decode(bytes.fromhex(raw[2:]))
    if type(fields) is not list or len(fields)!=9:
        raise Refused("signed legacy transaction has wrong RLP count")
    num=lambda x:int.from_bytes(x,"big")
    if (not all(type(x) is bytes for x in fields) or
        num(fields[0])!=idx+1 or
        num(fields[1])!=GAS_PRICE or num(fields[2])!=GAS_LIMIT or
        fields[3]!=bytes.fromhex(expected[1][2:]) or
        num(fields[4])!=expected[2] or fields[5]!=b"" or
        num(fields[6]) not in (CHAIN*2+35,CHAIN*2+36) or
        not 0<num(fields[7])<2**256 or
        not 0<num(fields[8])<2**256):
        raise Refused("signed real native EOA transfer differs from EXACT role/chain/nonce/fee/recipient")
    return True


def consent_phrase(role):
    idx=role_index(role)
    return "FUND-ONE-R267-CHAIN31340-"+role.upper()+"-NONCE"+str(idx+1)+"-EXACT-WEI"+str(RECIPIENTS[idx][2])


def send_once(role,*,transport=local_rpc,preview_fn=preflight,
              confirm=input,password_prompt=getpass,tty=True):
    if tty and (not sys.stdin.isatty() or not sys.stderr.isatty()):
        raise Refused("owner-only interactive TTY required to sign native funding")
    if os.geteuid()==0 or pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
        raise Refused("only original VM4707 nonroot app-key owner may fund roles")
    key,deploy_marker,marker=private_paths(role)
    if not deploy_marker.is_file() or deploy_marker.is_symlink():
        raise Refused("original R257 one-use deployment marker missing; refuse reused signer")
    require_private_owner_path(deploy_marker)
    if marker.exists() or marker.is_symlink():
        raise Refused("this exact role funding attempt already consumed; DO NOT RETRY")

    intent=preview_fn(role,transport=transport)
    print("R267_PUBLIC_FUNDING_INTENT_NOT_YET_AUTHORIZED="+
          json.dumps(intent,sort_keys=True),flush=True)
    phrase=consent_phrase(role)
    if confirm("Type "+phrase+" for EXACTLY ONE owner-approved role funding transfer: ")!=phrase:
        raise Refused("no exact affirmative owner consent for role funding transfer")
    document=safe_keystore(key)
    secret=password_prompt("Existing VM4707 encrypted APPLICATION deployer keystore password (hidden): ")
    if not secret:
        raise Refused("app-wallet password missing")
    try:
        from eth_account import Account
        private=Account.decrypt(document,secret)
    except (ImportError,ValueError,TypeError,KeyError) as exc:
        raise Refused("app-wallet encrypted keystore unlock refused") from exc
    try:
        signer=Account.from_key(private)
        if signer.address.lower()!=APP.lower():
            raise Refused("funding signer is not the observed funded APP-only EOA")
        fresh=preview_fn(role,transport=transport)
        immutable=("role","chainId","source","recipient","sourceNonce",
                   "valueWei","gasLimit","gasPriceWei",
                   "finalizedDeploymentR206Verified",
                   "recipientHasZeroBalanceZeroNonceAndNoCode",
                   "previousRoleTransfersCanonicalAndFinalized")
        if any(fresh[k]!=intent[k] for k in immutable):
            raise Refused("live role funding conditions changed after typed owner approval")
        idx=role_index(role)
        _,target,value=RECIPIENTS[idx]
        tx={
            "chainId":CHAIN,"nonce":1+idx,
            "gas":GAS_LIMIT,"gasPrice":GAS_PRICE,
            "to":target,"value":value,"data":b"",
        }
        signed=Account.sign_transaction(tx,private)
        raw="0x"+bytes(signed.raw_transaction).hex()
        txhash="0x"+bytes(signed.hash).hex()
        if Account.recover_transaction(raw).lower()!=APP.lower():
            raise Refused("actual raw signed funding transaction recovered wrong sender")
        verify_signed_legacy_transfer(raw,role)
        # This marker is the irreversible retry boundary. If RPC is lost,
        # inspect public hash/nonce only, NEVER delete marker/re-sign/resend.
        record_marker(marker,role,txhash)
        print("R267_ONE_TIME_"+role.upper()+"_ATTEMPT_CONSUMED=true",flush=True)
        print("R267_PRECOMPUTED_FUNDING_TRANSACTION_HASH="+txhash,flush=True)
        ack=transport(RPC,RAW_TX_CALL,[raw])  # EXACT ONE broadcast call.
        if type(ack) is not str or ack.lower()!=txhash.lower():
            raise Refused("node did not ACK locally computed hash; never resend")
        return {
            "schema":"SSE_R267_ONE_OWNER_APPROVED_NATIVE_ROLE_FUNDING_SENT_V1",
            "chainId":CHAIN,"role":role,"source":APP,"recipient":target,
            "nonce":1+idx,"valueWei":str(value),
            "gasLimit":GAS_LIMIT,"gasPriceWei":GAS_PRICE,
            "maxFeeWei":str(GAS_LIMIT*GAS_PRICE),
            "txHash":txhash,"singleRawTransactionSent":True,
            "confirmedCanonicalOrFinalized":False,
            "passwordOrPrivateKeyPrinted":False,
            "doNotRetry":True,
        }
    finally:
        del private,secret


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc",required=True,choices=(RPC,))
    parser.add_argument("--role",required=True,choices=tuple(x[0] for x in RECIPIENTS))
    parser.add_argument("--source-sha",required=True)
    parser.add_argument("--send",action="store_true",
                        help="ONE only: requires separate user funding approval + owner local TTY")
    args=parser.parse_args(argv)
    try:
        check_git(args.source_sha)
        if not args.send:
            print(json.dumps(preflight(args.role),indent=2,sort_keys=True))
            print("R267_FUNDING_PREVIEW_ONLY_NO_SIGNING_NO_BROADCAST=true")
            return 0
        result=send_once(args.role)
        print(json.dumps(result,indent=2,sort_keys=True))
        print("R267_ONE_RAW_ROLE_FUNDING_SUBMITTED_NOT_YET_FINALIZED=true")
        return 0
    except Pending as exc:
        print("R267_EARLIER_ROLE_FUNDING_PENDING_FINALITY_DO_NOT_RESEND: "+str(exc),
              file=sys.stderr)
        return 3
    except (Refused,OSError,ValueError,TypeError,KeyError,ImportError) as exc:
        print("R267_ROLE_FUNDING_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
