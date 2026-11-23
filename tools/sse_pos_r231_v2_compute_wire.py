#!/usr/bin/env python3
"""R231: V2 signed deterministic-compute HTTP wire integrity (NOT SLA truth).

The provider signs the EIP-712 ProviderResponse over a hash of the exact
claimed workload output, immutable lease and epoch context. This module
never holds a private key or signs. A local worker may actually execute
compute, and an outside monitor can re-compute the digest, but this is
NOT physical CPU allocation or independent cloud-service attestation.
"""
from __future__ import annotations

import json
import re

from compute_workload import compute_result, ROUNDS
from sse_challenge import keccak256
from sse_pos_r228_v2_typed_data import (
    Refused as TypedRefused, checked_addr, checked_hash, verify_public_signer,
)

HASH=re.compile(r"0x[0-9a-fA-F]{64}\Z")
DIGEST=re.compile(r"sha256:[0-9a-f]{64}\Z")
WIRE=(
    "leaseId","epochId","requestHash","profileHash","policyHash",
    "workResultDigest","workRounds",
)
PREFIX=b"SSE_V2_COMPUTE_RECEIPT_V1\x00"


class Refused(ValueError):
    pass


def validate_payload(payload):
    if type(payload) is not dict or set(payload)!=set(WIRE):
        raise Refused("V2 compute response fields do not match exact wire ABI")
    lease,epoch=payload["leaseId"],payload["epochId"]
    if (type(lease) is not int or not 1<=lease<2**256 or
        type(epoch) is not int or not 0<=epoch<2**256):
        raise Refused("bad lease/epoch")
    for name in ("requestHash","profileHash","policyHash"):
        value=payload[name]
        if checked_hash(value,name)!=value:
            raise Refused("signed hash must be canonical lowercase")
    digest=payload["workResultDigest"]
    if type(digest) is not str or not DIGEST.fullmatch(digest):
        raise Refused("wrong CPU result hash envelope")
    if type(payload["workRounds"]) is not int or payload["workRounds"]!=ROUNDS:
        raise Refused("unexpected deterministic workload rounds")
    return payload


def response_hash(payload):
    validate_payload(payload)
    data=json.dumps(payload,sort_keys=True,ensure_ascii=True,
                    allow_nan=False,separators=(",",":")).encode("ascii")
    return "0x"+keccak256(PREFIX+data).hex()


def payload_from_result(lease_id,epoch_id,request_hash,profile_hash,policy_hash,
                        result):
    if type(result) is not dict or set(result)!={
        "schema","leaseId","epochId","requestHash","rounds","resultDigest"
    }:
        raise Refused("actual Docker worker result schema missing")
    expected=compute_result(lease_id,epoch_id,request_hash)
    if result!=expected:
        raise Refused("actual worker response differs from independently computed result")
    payload={
        "leaseId":lease_id,"epochId":epoch_id,"requestHash":request_hash,
        "profileHash":profile_hash,"policyHash":policy_hash,
        "workResultDigest":result["resultDigest"],"workRounds":result["rounds"]
    }
    return validate_payload(payload)


def provider_eip712_message(payload):
    return {
        "leaseId":payload["leaseId"],"epochId":payload["epochId"],
        "requestHash":payload["requestHash"],
        "responseHash":response_hash(payload),
    }


def signed_reply(payload,signature,provider,market,ledger):
    validate_payload(payload)
    if not verify_public_signer("provider-response",
                                provider_eip712_message(payload),
                                market,ledger,signature,provider):
        raise Refused("provided signature does not authenticate V2 provider payload")
    return {
        **payload,"responseHash":response_hash(payload),
        "providerSignature":signature,
    }


def validate_signed_reply(reply, snapshot):
    if type(reply) is not dict or set(reply)!=(set(WIRE)|{
        "responseHash","providerSignature"}):
        raise Refused("provider response must be signed with exact V2 fields")
    if (type(snapshot) is not dict or
        snapshot.get("schema")!="SSE_R229_FINALIZED_V2_LEASE_READONLY_V1" or
        snapshot.get("deploymentRuntimeAndWiringAttested") is not True or
        snapshot.get("chainId")!=31340):
        raise Refused("provider cannot be checked without real original-chain lease state")
    payload={name:reply[name] for name in WIRE}
    validate_payload(payload)
    lease=snapshot["lease"]
    epoch=snapshot["epoch"]
    if type(epoch) is not dict or not epoch["market"]["exists"]:
        raise Refused("real finalized lease epoch missing")
    if (payload["leaseId"]!=snapshot["leaseId"] or
        payload["epochId"]!=snapshot["epochId"] or
        payload["requestHash"]!=epoch["market"]["requestHash"] or
        payload["profileHash"]!=lease["profileHash"] or
        payload["policyHash"]!=lease["policyHash"]):
        raise Refused("signed HTTP output is not bound to finalized lease/epoch")
    expected=compute_result(payload["leaseId"],payload["epochId"],
                            payload["requestHash"])
    if (payload["workRounds"]!=expected["rounds"] or
        payload["workResultDigest"]!=expected["resultDigest"]):
        raise Refused("wrong actual deterministic compute output digest")
    hash_found=response_hash(payload)
    if reply["responseHash"]!=hash_found:
        raise Refused("typed signed response hash does not bind supplied CPU output")
    try:
        valid=verify_public_signer("provider-response",
                                   provider_eip712_message(payload),
                                   snapshot["market"],snapshot["ledger"],
                                   reply["providerSignature"],lease["provider"])
    except (TypedRefused,ValueError,TypeError) as exc:
        raise Refused("invalid public V2 EIP-712 signature") from exc
    if not valid:
        raise Refused("provider signature not attributable to lease provider")
    return {
        "schema":"SSE_R231_V2_SIGNED_HTTP_RESULT_CHECK_V1",
        "leaseId":payload["leaseId"],"epochId":payload["epochId"],
        "responseHash":hash_found,"workResultDigest":payload["workResultDigest"],
        "providerPublicSignatureVerified":True,
        "realFinalizedLeaseAndEpochBound":True,
        "actualDockerContainerVerified":False,
        "remotePhysicalComputeProved":False,
        "objectiveSlaSuccessProved":False,
        "onChainProviderResponseAuthenticated":False,
        "transactionSignedOrSubmitted":False,
    }
