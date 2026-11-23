#!/usr/bin/env python3
"""R228: V2-only EIP-712 payload builder and public-signature verifier.

Domain and struct must EXACTLY match SSEAdaptiveMarketV2 (provider response,
bilateral allocation) or SSEAdaptiveVoteLedger (monitor vote). V1
typed_evidence.Domain is intentionally NOT reused: its SSESettlement domain
is incompatible. No private keys, signing, wallet unlocking, on-chain votes,
physical SLA verification, or automatic transaction submission.

Can verify a provided PUBLIC signature using eth-account, with no secret.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from sse_challenge import keccak256

CHAIN=31340
HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")
SIG=re.compile(r"0x[0-9a-fA-F]{130}\Z")
ZERO="0x"+"00"*32
DOMAIN_FIELDS=[
    {"name":"name","type":"string"},
    {"name":"version","type":"string"},
    {"name":"chainId","type":"uint256"},
    {"name":"verifyingContract","type":"address"},
]
LAYOUTS={
    "provider-response":(
        "ProviderResponse","SSEAdaptiveMarketV2",
        [("leaseId","uint256"),("epochId","uint256"),
         ("requestHash","bytes32"),("responseHash","bytes32")]),
    "monitor-vote":(
        "MonitorVote","SSEAdaptiveCommitteeVotes",
        [("leaseId","uint256"),("epochId","uint256"),
         ("requestHash","bytes32"),("outcome","uint8"),
         ("responseHash","bytes32"),("evidenceHash","bytes32")]),
    "residual-allocation":(
        "ResidualAllocation","SSEAdaptiveMarketV2",
        [("leaseId","uint256"),("epochId","uint256"),
         ("consumerShare","uint256"),("providerShare","uint256"),
         ("nonce","uint256"),("expiry","uint256")]),
}


class Refused(ValueError):
    pass


def checked_addr(value):
    if type(value) is not str or not ADDRESS.fullmatch(value) or int(value,16)==0:
        raise Refused("nonzero Ethereum contract/signer address required")
    return value.lower()


def checked_hash(value, name, *, nonzero=True):
    if type(value) is not str or not HASH.fullmatch(value):
        raise Refused("bad V2 bytes32 "+name)
    if nonzero and int(value,16)==0:
        raise Refused("zero hash forbidden for "+name)
    return value.lower()


def validate_message(kind, message):
    if kind not in LAYOUTS or type(message) is not dict:
        raise Refused("unknown V2 EIP-712 type")
    _,_,layout=LAYOUTS[kind]
    if set(message)!={name for name,_ in layout}:
        raise Refused("V2 signed fields do not match deployed Solidity")
    checked={}
    for name,field in layout:
        value=message[name]
        if field=="bytes32":
            checked[name]=checked_hash(value,name,nonzero=(
                name!="responseHash" or kind!="monitor-vote"))
        elif field in ("uint8","uint256"):
            bits=8 if field=="uint8" else 256
            if type(value) is not int or not 0<=value<2**bits:
                raise Refused("invalid unsigned "+name)
            checked[name]=value
        else:
            raise Refused("unexpected typed-data field")
    if checked["leaseId"]==0:
        raise Refused("zero lease ID cannot be signed")
    if kind=="monitor-vote":
        if checked["outcome"] not in (1,2):
            raise Refused("monitor vote must be Success=1 or Failure=2")
        if checked["outcome"]==1 and checked["responseHash"]==ZERO:
            raise Refused("Success needs authenticated response hash")
        if checked["outcome"]==2 and checked["responseHash"]!=ZERO:
            raise Refused("Failure must sign zero response hash")
    if kind=="residual-allocation":
        if checked["expiry"]==0 or checked["consumerShare"]+checked["providerShare"]==0:
            raise Refused("invalid residual allocation terms")
        if checked["consumerShare"]+checked["providerShare"]>=2**256:
            raise Refused("residual sum overflows Solidity uint256")
    return checked


def typed_data(kind, message, market, ledger):
    checked=validate_message(kind,message)
    market,ledger=checked_addr(market),checked_addr(ledger)
    if market==ledger:
        raise Refused("market and vote ledger must differ")
    primary,name,layout=LAYOUTS[kind]
    verifying=ledger if kind=="monitor-vote" else market
    return {
        "types":{
            "EIP712Domain":DOMAIN_FIELDS,
            primary:[{"name":k,"type":t} for k,t in layout],
        },
        "primaryType":primary,
        "domain":{
            "name":name,"version":"1","chainId":CHAIN,
            "verifyingContract":verifying
        },
        "message":checked,
    }


def recover_public_signer(kind,message,market,ledger,signature):
    if type(signature) is not str or not SIG.fullmatch(signature) or int(signature[-2:],16) not in (27,28):
        raise Refused("noncanonical 65-byte Ethereum EIP-712 signature")
    # Dependency is loaded only when verifying, not for source-only plans.
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise Refused("eth-account is required for public EIP-712 recovery") from exc
    envelope=typed_data(kind,message,market,ledger)
    try:
        recovered=Account.recover_message(
            encode_typed_data(full_message=envelope),signature=signature)
    except (ValueError,TypeError,OverflowError) as exc:
        raise Refused("unable to recover signed V2 EIP-712 message") from exc
    return checked_addr(recovered)


def verify_public_signer(kind,message,market,ledger,signature,expected):
    return recover_public_signer(kind,message,market,ledger,signature)==checked_addr(expected)


def evidence_commitment(observation):
    """Content-address an ACTUALLY COLLECTED monitor observation envelope.

    The function does not collect or authenticate measurements and it refuses
    to fabricate a failure/outcome. The raw observation must be archived by
    the source monitor for any substantive SLA evaluation.
    """
    if type(observation) is not dict or set(observation)!={
        "leaseId","epochId","monitor","observedAtUtc",
        "endpoint","method","responseSha256","latencyMs","httpStatus",
        "rawObservationSha256","source"
    }:
        raise Refused("missing measured observation/attribution fields")
    if type(observation["leaseId"]) is not int or not 1<=observation["leaseId"]<2**256:
        raise Refused("invalid lease scope")
    if type(observation["epochId"]) is not int or not 0<=observation["epochId"]<2**256:
        raise Refused("invalid epoch scope")
    checked_addr(observation["monitor"])
    for key in ("responseSha256","rawObservationSha256"):
        if (type(observation[key]) is not str or
            not re.fullmatch(r"[0-9a-f]{64}",observation[key])):
            raise Refused("expected lowercase observed SHA256")
    if type(observation["latencyMs"]) is not int or not 0<=observation["latencyMs"]<=3_600_000:
        raise Refused("invalid measured latency")
    if (type(observation["httpStatus"]) is not int or
        not 100<=observation["httpStatus"]<=599):
        raise Refused("invalid observed HTTP status")
    for field in ("observedAtUtc","endpoint","method","source"):
        value=observation[field]
        if type(value) is not str or not 1<=len(value)<=512:
            raise Refused("invalid observation context")
    # No outcome or on-chain vote is synthesized from a digest.
    raw=json.dumps(observation,sort_keys=True,separators=(",",":"),
                   ensure_ascii=True,allow_nan=False).encode("ascii")
    return "0x"+keccak256(b"SSE_V2_MONITOR_EVIDENCE_V1\x00"+raw).hex()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--type",required=True,choices=sorted(LAYOUTS))
    p.add_argument("--message-json",required=True,help="public typed-data fields only")
    p.add_argument("--market",required=True)
    p.add_argument("--ledger",required=True)
    p.add_argument("--signature",help="optional PUBLIC Ethereum EIP-712 signature")
    p.add_argument("--expected-signer",help="optional PUBLIC expected EOA address")
    a=p.parse_args(argv)
    try:
        if bool(a.signature)!=bool(a.expected_signer):
            raise Refused("signature and expected signer required together")
        m=json.loads(a.message_json)
        data=typed_data(a.type,m,a.market,a.ledger)
        verified=(verify_public_signer(a.type,m,a.market,a.ledger,
                                      a.signature,a.expected_signer)
                  if a.signature else None)
        print(json.dumps({
            "schema":"SSE_R228_V2_PUBLIC_TYPED_DATA_V1",
            "typedData":data,
            "expectedSignerMatchesProvidedSignature":verified,
            "signingKeyAccessed":False,"transactionSubmitted":False,
            "remotePhysicalSlaVerified":False,
        },sort_keys=True,indent=2))
        return 0 if verified is not False else 2
    except (Refused,ValueError,TypeError,KeyError,OverflowError) as exc:
        print("R228_V2_TYPED_DATA_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
