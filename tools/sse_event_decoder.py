"""Decode a limited, explicitly reviewed SSE event ABI for read-only dashboards.

Only canonical static values are decoded. The emitter address, topic0, chain
data, tx hash, block hash and raw bytes remain accessible. Decoding an event
does not attest that an off-chain observation is true or finalized.
"""
from __future__ import annotations

import re

from sse_challenge import keccak256

HEX32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
DATABYTES = re.compile(r"0x(?:[0-9a-fA-F]{2})*\Z")

# (name, [(fieldName, solidityType, indexed), ...])
# Each event signature is exact to the deployed R2/R3 settlement and board
# contracts. Never infer semantic truth from a vote or an event name.
EVENTS = [
    ("Requested", [
        ("requestId", "uint256", True), ("consumer", "address", True),
        ("profileHash", "bytes32", False), ("slaPolicyHash", "bytes32", False),
    ]),
    ("BidSubmitted", [
        ("requestId", "uint256", True), ("bidIndex", "uint256", True),
        ("provider", "address", True), ("epochFeeWei", "uint256", False),
    ]),
    ("BidChosen", [
        ("requestId", "uint256", True), ("bidIndex", "uint256", True),
        ("provider", "address", True), ("epochFeeWei", "uint256", False),
    ]),
    ("LeaseFunded", [
        ("requestId", "uint256", True), ("leaseId", "uint256", True),
        ("settlement", "address", True),
    ]),
    ("CandidateRegistered", [
        ("monitor", "address", True), ("bondWei", "uint256", False),
    ]),
    ("AssignmentRequested", [
        ("assignmentId", "uint256", True), ("consumer", "address", False),
        ("provider", "address", False), ("poolSize", "uint256", False),
    ]),
    ("CommitteeSelected", [
        ("assignmentId", "uint256", True), ("committee", "address[4]", False),
    ]),
    ("LeaseCreated", [
        ("leaseId", "uint256", True), ("consumer", "address", True),
        ("provider", "address", True), ("escrowWei", "uint256", False),
    ]),
    ("LeaseAccepted", [("leaseId", "uint256", True)]),
    ("CommitteeAssignmentRequested", [
        ("leaseId", "uint256", True), ("assignmentId", "uint256", True),
    ]),
    ("CommitteeAssigned", [
        ("leaseId", "uint256", True), ("assignmentId", "uint256", True),
    ]),
    ("CommitteeReady", [("leaseId", "uint256", True)]),
    ("EpochAdmitted", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("requestHash", "bytes32", False),
    ]),
    ("ProviderAcknowledged", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
    ]),
    ("ProviderResponseAuthenticated", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("responseHash", "bytes32", False),
    ]),
    ("MonitorVoted", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("monitor", "address", True), ("outcome", "uint8", False),
        ("evidenceHash", "bytes32", False),
    ]),
    ("MonitoringSealed", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("outcome", "uint8", False),
    ]),
    ("SettlementUpdated", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("providerLowerWei", "uint256", False),
        ("providerUpperWei", "uint256", False),
        ("unresolvedExposureWei", "uint256", False),
    ]),
    ("EpochEvidenceClosed", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("retainedWei", "uint256", False),
    ]),
    ("LeaseClosed", [
        ("leaseId", "uint256", True), ("uncommittedRefundWei", "uint256", False),
    ]),
    ("Withdrawal", [
        ("account", "address", True), ("amountWei", "uint256", False),
    ]),
    ("ResidualAgreementExecuted", [
        ("leaseId", "uint256", True), ("epochId", "uint256", True),
        ("nonce", "uint256", True), ("providerShareWei", "uint256", False),
        ("consumerShareWei", "uint256", False),
    ]),
]


def _signature(name, fields):
    return name + "(" + ",".join(t for _, t, _ in fields) + ")"


LOOKUP = {
    "0x" + keccak256(_signature(name, fields).encode("ascii")).hex():
        (name, fields)
    for name, fields in EVENTS
}


class EventDecodeError(ValueError):
    pass


def _word(raw: bytes, kind: str):
    if len(raw) != 32:
        raise EventDecodeError("noncanonical ABI event word length")
    n = int.from_bytes(raw, "big")
    if kind == "address":
        if n >> 160:
            raise EventDecodeError("noncanonical ABI address")
        return "0x" + raw[-20:].hex()
    if kind == "bytes32":
        return "0x" + raw.hex()
    if kind in ("uint256", "uint64", "uint8"):
        bits = int(kind[4:])
        if n >= 2**bits:
            raise EventDecodeError("event numeric width overflow")
        return n
    raise EventDecodeError("unsupported static ABI event type")


def decode_sse_event(event: dict) -> dict | None:
    """Return a verified-layout event interpretation, or None for unknown topic.

    Does NOT prove producer/operator honesty, chain finality, SLA performance,
    or the authenticity of off-chain evidence represented by a bytes32.
    """
    if type(event) is not dict:
        raise EventDecodeError("event must be an object")
    topics, data = event.get("topics"), event.get("data")
    if type(topics) is not list or not topics or not all(
            type(t) is str and HEX32.fullmatch(t) for t in topics):
        raise EventDecodeError("event topics must be 32-byte hex values")
    if type(data) is not str or not DATABYTES.fullmatch(data):
        raise EventDecodeError("event data must be even-length hexadecimal bytes")
    matching = LOOKUP.get(topics[0].lower())
    if matching is None:
        return None
    name, fields = matching
    indexed = [f for f in fields if f[2]]
    unindexed = [f for f in fields if not f[2]]
    count = sum(4 if t == "address[4]" else 1 for _, t, _ in unindexed)
    payload = bytes.fromhex(data[2:])
    if len(topics) != len(indexed) + 1 or len(payload) != count * 32:
        raise EventDecodeError("event topic/data counts violate known contract ABI")
    decoded = {}
    ti, di = 1, 0
    for field, kind, is_indexed in fields:
        if is_indexed:
            if kind == "address[4]":
                raise EventDecodeError("cannot decode hashed indexed arrays")
            value = _word(bytes.fromhex(topics[ti][2:]), kind)
            ti += 1
        elif kind == "address[4]":
            value = [_word(payload[di + i*32:di + (i+1)*32], "address")
                     for i in range(4)]
            di += 4*32
        else:
            value = _word(payload[di:di+32], kind)
            di += 32
        decoded[field] = value
    if "outcome" in decoded:
        decoded["outcomeLabel"] = {0: "None", 1: "Success", 2: "Failure"}.get(
            decoded["outcome"], "UNKNOWN")
    return {
        "name": name,
        "parameters": decoded,
        "interpretation": "CHAIN_EVENT_ONLY_NOT_SLA_CERTIFICATION",
        "chainFinalityVerified": False,
        "offchainEvidenceVerified": False,
    }
