#!/usr/bin/env python3
"""SSE canonical service SLA V1 for experimental HTTP and deterministic compute.

A policy hash commits to a *proposed* SLA. It cannot prove the service was
delivered or authorize Solidity V1 money releases. Marketplace submissions
must use this hash as slaPolicyHash; validators must compare the hash to the
stored chain commitment. Unsupported service kinds and unknown metrics fail
closed instead of inheriting an unrelated HTTP service interpretation.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sse_challenge import keccak256

SCHEMA = "sse-service-sla-policy-v1"
PREFIX = b"SSE_SERVICE_SLA_POLICY_V1\x00"
DIGEST = re.compile(r"0x[0-9a-f]{64}\Z")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
WORKLOAD_BY_SERVICE = {
    "http_challenge": "SSE_RESPONSE_HASH_V1",
    "deterministic_compute": "SSE_SHA256_CHAIN_8192_V1",
}
FULFILLMENT = "CONSUMER_CORRECT_RESULT_RECEIVED_V1"
EVIDENCE = "SIGNED_OBSERVATIONS_NOT_PHYSICAL_PROOFS_V1"
FAILURE = "TIMEOUT_IS_INCONCLUSIVE_V1"
RESERVATION = "DELIVERY_ONLY_ZERO_RESERVATION_V1"
FIELDS = frozenset({
    "schema", "chainId", "settlement", "serviceKind", "workloadSpec",
    "resourceProfileHash", "fulfillmentMode", "receiptCutoffMs",
    "deliveryDeadlineMs", "maxResponseLatencyMs", "probeIntervalMs",
    "probeTimeoutMs", "minProbeCount", "minSuccessBps",
    "evidencePolicy", "timeoutPolicy", "reservationPolicy",
})


class SLAError(ValueError):
    pass


def _integer(value: Any, name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise SLAError(name + " outside supported range")
    return value


def validate_policy(policy: dict) -> dict:
    if type(policy) is not dict or set(policy) != FIELDS:
        raise SLAError("SLA policy contains unknown or missing fields")
    if policy["schema"] != SCHEMA:
        raise SLAError("unsupported SLA policy version")
    _integer(policy["chainId"], "chainId", 1, (1 << 64) - 1)
    addr = policy["settlement"]
    if (type(addr) is not str or not ADDRESS.fullmatch(addr) or
            addr != addr.lower() or int(addr, 16) == 0):
        raise SLAError("settlement must be a canonical nonzero address")
    kind = policy["serviceKind"]
    if type(kind) is not str or kind not in WORKLOAD_BY_SERVICE:
        raise SLAError("SLA service type not implemented; refusing silent fallback")
    if policy["workloadSpec"] != WORKLOAD_BY_SERVICE[kind]:
        raise SLAError("SLA workload specification incompatible with service")
    if (type(policy["resourceProfileHash"]) is not str or
            not DIGEST.fullmatch(policy["resourceProfileHash"]) or
            int(policy["resourceProfileHash"], 16) == 0):
        raise SLAError("invalid committed resource profile hash")
    for field, expected in (
        ("fulfillmentMode", FULFILLMENT), ("evidencePolicy", EVIDENCE),
        ("timeoutPolicy", FAILURE), ("reservationPolicy", RESERVATION),
    ):
        if policy[field] != expected:
            raise SLAError("unsupported or unsafe " + field)
    receipt = _integer(policy["receiptCutoffMs"], "receiptCutoffMs", 100, 3600_000)
    delivery = _integer(policy["deliveryDeadlineMs"], "deliveryDeadlineMs", 100, 3600_000)
    latency = _integer(policy["maxResponseLatencyMs"], "maxResponseLatencyMs", 10, 3600_000)
    interval = _integer(policy["probeIntervalMs"], "probeIntervalMs", 100, 3600_000)
    timeout = _integer(policy["probeTimeoutMs"], "probeTimeoutMs", 10, 3600_000)
    samples = _integer(policy["minProbeCount"], "minProbeCount", 1, 10000)
    _integer(policy["minSuccessBps"], "minSuccessBps", 1, 10000)
    if not receipt <= delivery or latency > delivery:
        raise SLAError("receipt cutoff and response latency must fit delivery window")
    if timeout > delivery or timeout > interval * 4:
        raise SLAError("probe timeout must fit the approved measurement window")
    if samples > 1 + delivery // interval:
        raise SLAError("minimum samples cannot fit the agreed measurement window")
    return policy


def canonical_policy(policy: dict) -> bytes:
    validate_policy(policy)
    try:
        return json.dumps(policy, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, UnicodeError, TypeError) as exc:
        raise SLAError("SLA policy cannot be canonicalized") from exc


def policy_hash(policy: dict) -> str:
    return "0x" + keccak256(PREFIX + canonical_policy(policy)).hex()


def proposed_policy(*, service_kind: str, chain_id: int, settlement: str,
                    resource_profile_hash: str,
                    delivery_deadline_ms: int = 60000,
                    receipt_cutoff_ms: int = 10000,
                    max_response_latency_ms: int = 5000,
                    probe_interval_ms: int = 10000,
                    probe_timeout_ms: int = 3000,
                    min_probe_count: int = 3,
                    min_success_bps: int = 9900) -> dict:
    if service_kind not in WORKLOAD_BY_SERVICE:
        raise SLAError("unsupported service kind")
    policy = {
        "schema": SCHEMA, "chainId": chain_id,
        "settlement": settlement.lower(), "serviceKind": service_kind,
        "workloadSpec": WORKLOAD_BY_SERVICE[service_kind],
        "resourceProfileHash": resource_profile_hash,
        "fulfillmentMode": FULFILLMENT,
        "receiptCutoffMs": receipt_cutoff_ms,
        "deliveryDeadlineMs": delivery_deadline_ms,
        "maxResponseLatencyMs": max_response_latency_ms,
        "probeIntervalMs": probe_interval_ms,
        "probeTimeoutMs": probe_timeout_ms,
        "minProbeCount": min_probe_count,
        "minSuccessBps": min_success_bps,
        "evidencePolicy": EVIDENCE,
        "timeoutPolicy": FAILURE,
        "reservationPolicy": RESERVATION,
    }
    return validate_policy(policy)


def compare_to_lease(policy: dict, inspection: dict, *, endpoint: str | None = None) -> None:
    """Bind canonical SLA to a real, admitted lease/epoch and endpoint claim.

    The inspector must independently verify the source chain, EIP-712 domain,
    and pinned state. An arbitrary dict is NOT an authenticated chain oracle.
    """
    from sse_chain_read import ChainReadError
    validate_policy(policy)
    if type(inspection) is not dict or inspection.get("schema") != "sse-onchain-inspection-v1":
        raise SLAError("missing verified SSE chain inspection")
    if (inspection.get("chainId") != policy["chainId"] or
            inspection.get("settlementAddress") != policy["settlement"] or
            not inspection.get("domainSeparatorMatches") or
            not inspection.get("blockHashPinned")):
        raise SLAError("SLA domain or canonical block binding mismatch")
    lease = inspection.get("lease")
    epoch = inspection.get("epoch")
    if type(lease) is not dict or type(epoch) is not dict or not epoch.get("exists"):
        raise SLAError("no active admitted service epoch")
    if (lease.get("stateName") != "Active" or lease.get("slaPolicyHash") != policy_hash(policy)
            or lease.get("resourceProfileHash") != policy["resourceProfileHash"]
            or lease.get("reservationFee") != 0
            or type(lease.get("marketplaceRequestId")) is not int
            or lease["marketplaceRequestId"] < 1
            or type(lease.get("totalEscrow")) is not int
            or lease["totalEscrow"] <= 0):
        raise SLAError("lease was not an active funded marketplace-selected SLA")
    if endpoint is not None:
        if (type(endpoint) is not str or not 1 <= len(endpoint) <= 255
                or not endpoint.isascii()):
            raise SLAError("invalid committed endpoint")
        if lease.get("serviceEndpointHash") != (
                "0x" + keccak256(endpoint.encode("ascii")).hex()):
            raise SLAError("configured service endpoint not committed on chain")
