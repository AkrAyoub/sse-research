"""Authenticated V1 challenge responder for monitor probes of active market leases.

This is an auxiliary *availability/attribution probe*, NOT proof of
consumer delivery, Docker CPU consumption, independently qualified SLA
correctness or an on-chain success vote. The client sends the exact active
lease/epoch request hash; the provider signs only the existing Solidity V1
ProviderResponse commitment, with no arbitrary message-signing API.
"""
from __future__ import annotations

from sse_challenge import expected_response_hash
from sse_sla_manifest import compare_to_lease
from typed_evidence import Domain, typed_message


class ChallengeError(ValueError):
    pass


def signed_challenge(payload, inspection, policy, endpoint, provider_signer):
    if type(payload) is not dict or set(payload) != {"leaseId","epochId","requestHash"}:
        raise ChallengeError("only the exact admitted challenge is accepted")
    if (type(payload["leaseId"]) is not int or type(payload["epochId"]) is not int
            or payload["leaseId"] < 1 or payload["epochId"] < 0):
        raise ChallengeError("invalid challenge indices")
    compare_to_lease(policy, inspection, endpoint=endpoint)
    lease, epoch = inspection["lease"], inspection["epoch"]
    if (payload["leaseId"] != inspection["leaseId"] or
            payload["epochId"] != inspection["epochId"] or
            payload["requestHash"] != epoch.get("requestHash") or
            epoch.get("responseHash") != expected_response_hash(payload["requestHash"])):
        raise ChallengeError("challenge does not match admitted chain epoch")
    if provider_signer.address.lower() != lease["provider"].lower():
        raise ChallengeError("this VM is not the selected winning provider")
    if (lease.get("monitorConfirmations") != 4 or
            type(lease.get("monitors")) is not list or
            len(set(lease["monitors"])) != 4 or
            epoch.get("monitoringSealed") is not False or
            epoch.get("evidenceClosed") is not False or
            type(inspection.get("blockTimestamp")) is not int or
            type(epoch.get("monitoringClose")) is not int or
            inspection["blockTimestamp"] > epoch["monitoringClose"]):
        raise ChallengeError("monitoring not confirmed or observation window closed")
    response = {**payload, "responseHash": epoch["responseHash"]}
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    signature = Account.sign_message(
        encode_typed_data(full_message=typed_message(
            Domain(policy["chainId"],policy["settlement"]), "ProviderResponse",response)),
        private_key=provider_signer.key)
    return {**response, "providerSignature":"0x"+bytes(signature.signature).hex()}
