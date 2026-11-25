#!/usr/bin/env python3
"""R237: explicit owner-approved local V2 EIP-712 signature, NO TRANSACTION.

Two separate operations:
(1) default dry-run builds ONLY PUBLIC EIP-712 signing intent;
(2) --sign verifies R206 original-chain finalized V2 deployment, reads one
    owner-owned encrypted app EOA UTC-V3 keystore, prompts hidden password and
    fresh explicit authorization via controlling TTY, signs locally, and
    prints ONLY PUBLIC signature/address/context.

No private key, password, ciphertext or wallet JSON may be pasted into chat,
CLI arguments, env vars, GitHub, log files or returned output. Never reuses
the original genesis EOA/consensus BLS validator/Engine JWT. This tool cannot
create wallets, transfer TEST ETH or submit EVM transactions.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import stat
import sys

from sse_pos_r228_v2_typed_data import (
    Refused as TypedRefused, checked_addr,typed_data,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,verify,
)
from sse_pos_r229_v2_finalized_lease_snapshot import (
    Refused as LeaseRefused, inspect as inspect_finalized_lease,
)

ORIGINAL_GENESIS_EOA="0x13fb73aace8a11be2899d047635a757a224ce00b"
MIN_SIZE=150
MAX_SIZE=16384
ROLE_TYPES={
    "provider":"provider-response",
    "monitor":"monitor-vote",
    "consumer":"residual-allocation",
}
CONFIRM="AUTHORIZE-V2-LOCAL-TYPED-SIGNATURE"


class Refused(ValueError):
    pass


def safe_keystore(path):
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink() or ".." in path.parts:
        raise Refused("encrypted app keystore must be absolute, owner-local and non-symlink")
    folder=path.parent
    if folder.is_symlink() or not folder.is_dir() or not path.is_file():
        raise Refused("app keystore or safe directory missing")
    uid=os.geteuid()
    dstat=folder.stat()
    st=path.stat()
    if (uid==0 or st.st_uid!=uid or dstat.st_uid!=uid or
        stat.S_IMODE(dstat.st_mode)!=0o700 or
        stat.S_IMODE(st.st_mode)!=0o600 or
        not MIN_SIZE<=st.st_size<=MAX_SIZE):
        raise Refused("app EOA must be nonroot owner-only 0700 dir / 0600 bounded file")
    raw=path.read_bytes()
    try:
        document=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise Refused("keystore is not a valid encrypted JSON object") from exc
    if (type(document) is not dict or
        type(document.get("version")) is not int or document["version"]!=3 or
        ("crypto" in document)==("Crypto" in document) or
        not {"id","version"} <= set(document) or
        set(document) - {"id","version","address","crypto","Crypto"}):
        raise Refused("expected encrypted Ethereum UTC-V3 keystore")
    envelope=document.get("crypto",document.get("Crypto"))
    if (type(envelope) is not dict or not all(k in envelope for k in (
            "cipher","ciphertext","cipherparams","kdf","kdfparams","mac"
    )) or type(envelope["ciphertext"]) is not str or
        not envelope["ciphertext"]):
        raise Refused("missing encrypted UTC-V3 envelope fields")
    return document


def public_intent(kind,message,market,ledger,expected,role):
    if role not in ROLE_TYPES or (kind!=ROLE_TYPES[role] and
       not (kind=="residual-allocation" and role=="provider")):
        raise Refused("wrong wallet role for signed V2 message type")
    expected=checked_addr(expected)
    if expected==ORIGINAL_GENESIS_EOA:
        raise Refused("refuse use of chain31340 original genesis owner EOA")
    t=typed_data(kind,message,market,ledger)
    return {
        "schema":"SSE_R237_V2_APPROVED_PUBLIC_SIGNING_INTENT_V1",
        "role":role,"expectedSigner":expected,
        "kind":kind,"typedData":t,
        "genesisEoaForbidden":True,
        "privateKeyRead":False,"transactionSignedOrSubmitted":False,
        "physicalSlaProven":False,
    }


def verify_public_role_state(intent,snapshot):
    """Authorize the EOA against actual R229 finalized lease and committee.

    EOA role controls alone cannot establish physical independence or
    objective SLA truth. Finalized state may lag latest head; the actual
    contract remains the ultimate authorization at submission time.
    """
    role=intent["role"]
    kind=intent["kind"]
    signer=intent["expectedSigner"]
    lease=snapshot["lease"]
    epoch=snapshot["epoch"]
    if type(epoch) is not dict or not epoch["market"]["exists"]:
        raise Refused("no actual finalized target epoch to sign")
    typed_message=intent["typedData"]["message"]
    if (kind in ("provider-response","monitor-vote") and
        typed_message["requestHash"]!=epoch["market"]["requestHash"]):
        raise Refused("EIP712 request commitment differs from finalized epoch")
    if (kind=="monitor-vote" and typed_message["outcome"]==1 and
        typed_message["responseHash"]!=epoch["ledger"]["responseHash"]):
        raise Refused("Success EIP712 signed response is not the authenticated provider hash")
    if kind=="provider-response":
        if (role!="provider" or signer!=lease["provider"] or
            lease["phase"]!=4 or lease["providerAccepted"] is not True or
            snapshot["committee"]["ready"] is not True or
            epoch["ledger"]["responseAuthenticated"] is True or
            epoch["ledger"]["monitoringSealed"] is True):
            raise Refused("not the actual active unsent provider response owner")
    elif kind=="monitor-vote":
        if (role!="monitor" or signer not in snapshot["selectedMonitors"] or
            snapshot["committee"]["ready"] is not True or
            lease["phase"]!=4 or epoch["ledger"]["monitoringSealed"] is True):
            raise Refused("monitor not eligible in actual finalized committee")
        if (intent["typedData"]["message"]["outcome"]==1 and
            epoch["ledger"]["responseAuthenticated"] is not True):
            raise Refused("signed Success cannot precede authenticated provider response")
    elif kind=="residual-allocation":
        if (signer!=lease["consumer"] and signer!=lease["provider"] or
            role=="consumer" and signer!=lease["consumer"] or
            role=="provider" and signer!=lease["provider"] or
            epoch["ledger"]["monitoringSealed"] is not True or
            epoch["ledger"]["outcome"]!=0 or epoch["market"]["resolved"] is True or
            intent["typedData"]["message"]["consumerShare"]+
            intent["typedData"]["message"]["providerShare"]!=epoch["market"]["feeWei"] or
            intent["typedData"]["message"]["nonce"]!=epoch["market"]["nonce"]):
            raise Refused("bilateral fee share not authorized for unresolved finalized epoch")
    else:
        raise Refused("unknown V2 role evidence type")
    return True


def sign_authorized(intent,keystore,manifest,rpc_url,*,confirm,get_password,
                    expected_tty=True,transport=None,canonical_confirmations=None):
    if expected_tty and (not sys.stdin.isatty() or not sys.stderr.isatty()):
        raise Refused("interactive controlling terminal required for encrypted app signer")
    if checked_addr(manifest["market"]["address"])!=intent["typedData"]["domain"]["verifyingContract"].lower() and intent["kind"]!="monitor-vote":
        raise Refused("typed-data market not equal finalized manifest")
    if (checked_addr(manifest["ledger"]["address"])!=
        intent["typedData"]["domain"]["verifyingContract"].lower() and
        intent["kind"]=="monitor-vote"):
        raise Refused("typed-data ledger not equal finalized manifest")
    verified=(verify(manifest,rpc_url,transport=transport)
              if transport is not None else verify(manifest,rpc_url))
    if verified["deploymentReceiptSuccessfulAndFinalized"] is not True:
        raise Refused("finalized real market runtime not verified")
    if transport is None:
        snapshot=inspect_finalized_lease(
            manifest,rpc_url,intent["typedData"]["message"]["leaseId"],
            intent["typedData"]["message"]["epochId"],attestation=verified)
    else:
        snapshot=inspect_finalized_lease(
            manifest,rpc_url,intent["typedData"]["message"]["leaseId"],
            intent["typedData"]["message"]["epochId"],
            transport=transport,attestation=verified)
    if canonical_confirmations is not None:
        if intent['kind'] != 'residual-allocation':
            raise Refused('canonical signing presently limited to bilateral residual allocation')
        from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical
        from sse_pos_r206_adaptive_v2_deployment_audit import rpc
        ask=transport or rpc
        message=intent['typedData']['message']
        snapshot=inspect_canonical(manifest,rpc_url,message['leaseId'],message['epochId'],confirmations=canonical_confirmations,transport=ask)
    verify_public_role_state(intent,snapshot)
    document=safe_keystore(keystore)
    print("R237_PUBLIC_TYPED_INTENT="+json.dumps({
        "kind":intent["kind"],"role":intent["role"],
        "expectedSigner":intent["expectedSigner"],
        "chainId":31340,
        "market":manifest["market"]["address"],
        "ledger":manifest["ledger"]["address"],
        "deploymentTxHash":manifest["deploymentTxHash"],
        "transactionSignedOrSubmitted":False,
        "message":intent["typedData"]["message"],
        "leaseStateAssurance":"FINALIZED" if canonical_confirmations is None else "PROVISIONAL_CANONICAL",
    },sort_keys=True),flush=True)
    response=confirm("Type "+CONFIRM+" to sign ONLY this public typed data: ")
    if response!=CONFIRM:
        raise Refused("explicit typed-data signing not authorized")
    secret=get_password("Local encrypted app EOA password (hidden): ")
    if not secret:
        raise Refused("empty app-wallet password")
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise Refused("missing pinned eth-account offline signer dependency") from exc
    if canonical_confirmations is not None:
        fresh=inspect_canonical(manifest,rpc_url,message["leaseId"],message["epochId"],transport=ask)
        verify_public_role_state(intent,fresh)
        if ask(rpc_url,"eth_getBlockByNumber",[hex(snapshot["observedExecutionHeight"]),False])["hash"].lower()!=snapshot["observedExecutionHash"]:
            raise Refused("approved canonical anchor reorganized")
        head=ask(rpc_url,"eth_getBlockByNumber",["latest",False])
        if int(head["timestamp"],16)>=message["expiry"]:
            raise Refused("residual signature expiry reached")
    try:
        raw_key=Account.decrypt(document,secret)
    except (ValueError,TypeError,KeyError) as exc:
        raise Refused("cannot unlock this encrypted app-only wallet") from exc
    # Do not print, serialize, persist or transfer decrypted key.
    try:
        account=Account.from_key(raw_key)
        if account.address.lower()!=intent["expectedSigner"]:
            raise Refused("encrypted app wallet does not match public expected signer")
        typed=intent["typedData"]
        signed=Account.sign_message(
            encode_typed_data(full_message=typed),private_key=raw_key)
        return {
            "schema":"SSE_R237_V2_PUBLIC_SIGNED_TYPED_DATA_V1",
            "kind":intent["kind"],"role":intent["role"],
            "signer":account.address,
            "signature":"0x"+bytes(signed.signature).hex(),
            "chainId":31340,
            "signingDomain":typed["domain"],
            "finalizedRuntimeVerified":True,
            "leaseStateFinalized":canonical_confirmations is None,
            "passwordPrinted":False,"privateKeyPrinted":False,
            "blockchainTransactionSignedOrSubmitted":False,
            "physicalSlaProven":False,
        }
    finally:
        del raw_key,secret


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind",required=True,choices=(
        "provider-response","monitor-vote","residual-allocation"))
    p.add_argument("--role",required=True,choices=sorted(ROLE_TYPES))
    p.add_argument("--message-json",required=True,help="PUBLIC type fields ONLY")
    p.add_argument("--market",required=True)
    p.add_argument("--ledger",required=True)
    p.add_argument("--expected-signer",required=True)
    p.add_argument("--sign",action="store_true",
                   help="requires local keystore, actual R206 finalized deployment and TTY approval")
    p.add_argument("--keystore",type=Path,
                   help="owner-only separate encrypted application EOA; no validator wallet")
    p.add_argument("--manifest",type=Path)
    p.add_argument("--rpc",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--canonical-confirmations",type=int,help="explicit provisional residual signing; reorg risk remains")
    a=p.parse_args(argv)
    try:
        message=json.loads(a.message_json)
        intent=public_intent(a.kind,message,a.market,a.ledger,a.expected_signer,a.role)
        if not a.sign:
            if a.keystore is not None or a.rpc or a.manifest or a.canonical_confirmations is not None:
                raise Refused("dry-run must not accept keystore or RPC inputs")
            print(json.dumps(intent,sort_keys=True,indent=2))
            return 0
        if a.keystore is None or not a.manifest or not a.rpc:
            raise Refused("explicit signed mode requires private app keystore and R206 manifest/RPC")
        manifest=load_manifest(a.manifest)
        result=sign_authorized(intent,a.keystore,manifest,a.rpc,
                               confirm=input,get_password=getpass,canonical_confirmations=a.canonical_confirmations)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,TypedRefused,AuditRefused,LeaseRefused,OSError,
            TypeError,ValueError,KeyError,UnicodeError) as exc:
        print("R237_V2_SIGNING_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
