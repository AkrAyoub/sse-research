#!/usr/bin/env python3
"""SSE V4 candidate off-chain encoders: termsHash and EIP-712 digests.

SOURCE-ONLY (2026-11-27): never executed. Mirrors, byte for byte by static
review, SSEAdaptiveMarketV4._recordLease (termsHash), the provider response
and acknowledgment digests, and the V4 vote ledger vote digest. Owner must
validate parity against a compiled contract (DEFERRED_RUNTIME_VALIDATION
DRV-V4-PARITY) before any agent signs with these helpers.
"""
from eth_abi import encode
from sse_challenge import keccak256

REQUEST_TUPLE = "(address,uint8,uint32,uint32,uint16,uint16,uint16,uint64,bytes32,bytes32,bytes32,uint256,uint256,uint256)"
BID_TUPLE = "(address,bool,uint32,uint64,uint256,bytes32,bytes32)"
TERMS_TUPLE = "(uint64,uint64,uint64,uint64,uint64,uint64,uint256,uint256,bool,bool)"

REQUEST_FIELDS = ("consumer", "status", "fixedEpochs", "maxEpochs", "seats", "standbys", "faultTolerance",
                  "biddingClose", "profileHash", "policyHash", "artifactCommitment", "maxEpochFee",
                  "perReportReward", "awardedBid")
BID_FIELDS = ("provider", "withdrawn", "epochs", "expiry", "epochFee", "endpointHash", "offerHash")
TERMS_FIELDS = ("acceptSeconds", "confirmationRoundSeconds", "responseSeconds", "monitoringSeconds",
                "evidenceSeconds", "idleSeconds", "reservationFee", "exposureBudget",
                "conditionalQuorumPolicy", "responseAdmitsReceipt")
STATUS_AWARDED = 2

EIP712_DOMAIN_TYPEHASH = keccak256(
    b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
RESPONSE_TYPEHASH = keccak256(
    b"ProviderResponse(uint256 leaseId,uint256 epochId,bytes32 requestHash,bytes32 responseHash)")
ACK_TYPEHASH = keccak256(b"ProviderAck(uint256 leaseId,uint256 epochId,bytes32 requestHash)")
VOTE_TYPEHASH = keccak256(
    b"MonitorVote(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint8 outcome,bytes32 responseHash,bytes32 evidenceHash)")
MARKET_NAME = "SSEAdaptiveMarketV4"
LEDGER_NAME = "SSEAdaptiveCommitteeVotesV4Candidate"


def _b32(v):
    if isinstance(v, str):
        v = bytes.fromhex(v[2:] if v.startswith("0x") else v)
    if not isinstance(v, (bytes, bytearray)) or len(v) != 32:
        raise ValueError("bytes32 required")
    return bytes(v)


def _tuple(d, fields):
    missing = [f for f in fields if f not in d]
    if missing:
        raise ValueError("missing fields: " + ",".join(missing))
    out = []
    for f in fields:
        v = d[f]
        if f.endswith("Hash") or f == "artifactCommitment":
            v = _b32(v)
        out.append(v)
    return tuple(out)


def terms_hash(chain_id, market, lease_id, bid_index, request, bid, terms):
    """`request` must be the board record AFTER award (status=2, awardedBid=bid_index)."""
    if request.get("status") != STATUS_AWARDED or request.get("awardedBid") != bid_index:
        raise ValueError("request must be the awarded board record")
    data = encode(["uint256", "address", "uint256", "uint256", REQUEST_TUPLE, BID_TUPLE, TERMS_TUPLE],
                  [chain_id, market, lease_id, bid_index, _tuple(request, REQUEST_FIELDS),
                   _tuple(bid, BID_FIELDS), _tuple(terms, TERMS_FIELDS)])
    return keccak256(data)


def domain_separator(name, chain_id, verifying_contract, version="1"):
    return keccak256(encode(["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [EIP712_DOMAIN_TYPEHASH, keccak256(name.encode()), keccak256(version.encode()),
         chain_id, verifying_contract]))


def typed_digest(domain, struct_hash):
    return keccak256(b"\x19\x01" + _b32(domain) + _b32(struct_hash))


def response_digest(domain, lease_id, epoch_id, request_hash, response_hash):
    return typed_digest(domain, keccak256(encode(["bytes32", "uint256", "uint256", "bytes32", "bytes32"],
        [RESPONSE_TYPEHASH, lease_id, epoch_id, _b32(request_hash), _b32(response_hash)])))


def ack_digest(domain, lease_id, epoch_id, request_hash):
    return typed_digest(domain, keccak256(encode(["bytes32", "uint256", "uint256", "bytes32"],
        [ACK_TYPEHASH, lease_id, epoch_id, _b32(request_hash)])))


def vote_digest(ledger_domain, lease_id, epoch_id, request_hash, outcome, response_hash, evidence_hash):
    if outcome not in (1, 2):
        raise ValueError("outcome must be 1 (Success) or 2 (Failure)")
    resp = _b32(response_hash) if outcome == 1 else b"\x00" * 32
    return typed_digest(ledger_domain, keccak256(encode(
        ["bytes32", "uint256", "uint256", "bytes32", "uint8", "bytes32", "bytes32"],
        [VOTE_TYPEHASH, lease_id, epoch_id, _b32(request_hash), outcome, resp, _b32(evidence_hash)])))


# Bilateral residual allocation; consent does not refine the history mask.
ALLOCATION_TYPEHASH = keccak256(
    b"ResidualAgreement(uint256 leaseId,uint256 epochId,bytes32 requestHash,uint256 unresolvedAmount,uint256 providerShare,uint256 consumerShare,uint256 nonce,uint256 expiry)")


def allocation_digest(domain, lease_id, epoch_id, request_hash, allocation):
    if _b32(domain) == bytes(32) or _b32(request_hash) == bytes(32) or type(lease_id) is not int or lease_id <= 0:
        raise ValueError("invalid allocation context")
    fields = ("unresolvedAmount", "providerShare", "consumerShare", "nonce", "expiry")
    values = [allocation[k] for k in fields]
    if any(type(v) is not int or not 0 <= v < 2**256 for v in values):
        raise ValueError("invalid allocation integer")
    residual, provider, consumer, nonce, expiry = values
    if residual == 0 or provider + consumer != residual:
        raise ValueError("allocation must conserve the exact residual")
    return typed_digest(domain, keccak256(encode(
        ["bytes32", "uint256", "uint256", "bytes32"] + ["uint256"] * 5,
        [ALLOCATION_TYPEHASH, lease_id, epoch_id, _b32(request_hash)] + values)))
