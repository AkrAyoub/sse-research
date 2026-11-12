"""WP-13: V2 lease/pool authorization at one pinned EIP-1898 block hash.

Only an RPC-assumption-bound RAW observation verifier. It does not verify
Ethereum state Merkle proofs, physical HTTP delivery, a fair VRF, or entitlement
to SSELeaseControllerV2 escrow. Never convert this result to QualifiedFact.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from sse_challenge import keccak256
from sse_chain_read import (
    ChainReadError, _address, _call, _hex_integer, _words, decode_struct,
)
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext, verify_observation

HEX_BYTES = re.compile(r"0x(?:[0-9a-fA-F]{2})*\Z")
HEX_HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
ZERO_ADDRESS = "0x" + "00" * 20
ZERO_HASH = "0x" + "00" * 32

# Ordered according to Solidity V2 public getLease(uint256) ABI tuple.
V2_LEASE_FIELDS = (
    ("consumer", "address"), ("provider", "address"),
    ("endpointHash", "bytes32"), ("profileHash", "bytes32"),
    ("slaPolicyHash", "bytes32"), ("assignmentId", "uint256"),
    ("escrow", "uint256"), ("fee", "uint256"), ("maxEpochs", "uint256"),
    ("exposureBudget", "uint256"), ("nextEpochId", "uint256"),
    ("pending", "uint256"), ("uncommitted", "uint256"),
    ("consumerCredited", "uint256"), ("providerCredited", "uint256"),
    ("unusedRefunded", "uint256"), ("epochWindow", "uint64"),
    ("acceptanceDeadline", "uint64"), ("state", "uint8"),
)
V2_EPOCH_FIELDS = (
    ("requestHash", "bytes32"), ("fee", "uint256"), ("deadline", "uint64"),
    ("providerShare", "uint256"), ("consumerShare", "uint256"),
    ("nonce", "uint256"), ("admitted", "bool"), ("allocated", "bool"),
)
V2_TICKET_FIELDS = (
    ("joined", "bool"), ("paid", "bool"), ("everSelected", "bool"),
    ("confirmed", "bool"), ("noShow", "bool"),
)
V2_ASSIGNMENT_FIELDS = (
    ("size", "uint8"), ("quorum", "uint8"), ("reserves", "uint8"),
    ("consumer", "address"), ("provider", "address"),
)


class V2AuthorityError(ChainReadError):
    """Fail-closed RPC-bound authorization error, NOT an evidence verdict."""


def _canonical_hash(value: str, label: str) -> str:
    if type(value) is not str or not HEX_HASH.fullmatch(value):
        raise V2AuthorityError(f"{label}: expected bytes32 hex")
    normalized = value.lower()
    if normalized == ZERO_HASH:
        raise V2AuthorityError(f"{label}: zero bytes32 not allowed")
    return normalized


def _validated_address(value: str, label: str) -> str:
    try:
        address = _address(value)
    except ChainReadError as exc:
        raise V2AuthorityError(f"{label}: invalid Ethereum address") from exc
    if address == ZERO_ADDRESS:
        raise V2AuthorityError(f"{label}: zero Ethereum address")
    return address


def _rpc(rpc, method: str, args: list):
    if not callable(getattr(rpc, "request", None)):
        raise V2AuthorityError("an explicit RPC request() client is required")
    try:
        return rpc.request(method, args)
    except Exception as exc:
        raise V2AuthorityError(f"RPC {method} failed closed") from exc


def _call_at(rpc, contract: str, signature: str, args: tuple[int, ...], pinned: dict):
    try:
        return _call(rpc, contract, signature, args, pinned)
    except (ChainReadError, ValueError, OverflowError, TypeError) as exc:
        raise V2AuthorityError(f"invalid pinned eth_call for {signature}") from exc


def _decode_at(rpc, contract: str, signature: str, args: tuple[int, ...],
               pinned: dict, fields: tuple) -> dict:
    try:
        return decode_struct(_call_at(rpc, contract, signature, args, pinned), fields)
    except ChainReadError as exc:
        raise V2AuthorityError(f"invalid V2 ABI structure for {signature}") from exc


def _uint_at(rpc, contract: str, signature: str, args: tuple[int, ...], pinned: dict) -> int:
    try:
        return int(_words(_call_at(rpc, contract, signature, args, pinned), 1)[0], 16)
    except (ChainReadError, TypeError, ValueError) as exc:
        raise V2AuthorityError(f"invalid V2 scalar for {signature}") from exc


def _address_at(rpc, contract: str, signature: str, args: tuple[int, ...], pinned: dict) -> str:
    result = _decode_at(rpc, contract, signature, args, pinned, (("value", "address"),))
    return _validated_address(result["value"], signature)


def _runtime_fingerprint(rpc, contract: str, expected: str, pinned: dict) -> None:
    code = _rpc(rpc, "eth_getCode", [contract, pinned])
    if type(code) is not str or not HEX_BYTES.fullmatch(code) or len(code) <= 2:
        raise V2AuthorityError("missing or malformed runtime contract code")
    actual = "0x" + keccak256(bytes.fromhex(code[2:])).hex()
    if actual != expected:
        raise V2AuthorityError("runtime code fingerprint differs from independent trust anchor")


def _v2_domain_separator(chain_id: int, controller: str) -> str:
    # SSELeaseControllerV2 inherits EIP712("SSELeaseControllerV2", "2").
    fields = (
        keccak256(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
        keccak256(b"SSELeaseControllerV2"),
        keccak256(b"2"),
        chain_id.to_bytes(32, "big"),
        int(controller, 16).to_bytes(32, "big"),
    )
    return "0x" + keccak256(b"".join(fields)).hex()


@dataclass(frozen=True)
class V2AuthoritySpec:
    scope: EvidenceScope
    pool: str
    endpoint: str
    controller_code_hash: str
    pool_code_hash: str
    block_tag: str = "finalized"
    allow_unfinalized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScope):
            raise V2AuthorityError("V2 EvidenceScope required")
        _validated_address(self.scope.settlement, "controller")
        _validated_address(self.pool, "pool")
        _canonical_hash(self.controller_code_hash, "controller_code_hash")
        _canonical_hash(self.pool_code_hash, "pool_code_hash")
        if type(self.endpoint) is not str or not self.endpoint.startswith("http://127.0.0.1:"):
            raise V2AuthorityError("WP13 only accepts an exact numeric IPv4 loopback endpoint")
        from signed_probe import validate_endpoint
        from urllib.parse import urlsplit
        try:
            # validate_endpoint returns the actual /v1/challenge request URL,
            # whereas the funded lease commits to the canonical service ROOT.
            validate_endpoint(self.endpoint)
            parsed = urlsplit(self.endpoint)
            if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or
                    parsed.netloc != f"127.0.0.1:{parsed.port}" or
                    parsed.path != "" or parsed.query or parsed.fragment):
                raise V2AuthorityError("noncanonical numeric loopback service root")
        except (ValueError, TypeError) as exc:
            raise V2AuthorityError("invalid loopback service root") from exc
        if type(self.allow_unfinalized) is not bool or self.block_tag not in ("finalized", "safe", "latest"):
            raise V2AuthorityError("invalid chain block tag or opt-in")
        if self.block_tag != "finalized" and not self.allow_unfinalized:
            raise V2AuthorityError("safe/latest requires explicit opt-in")


@dataclass(frozen=True)
class V2AuthoritySnapshot:
    scope: EvidenceScope
    controller: str
    pool: str
    provider: str
    consumer: str
    assignment_id: int
    monitors: tuple[str, ...]
    quorum: int
    reserves: int
    endpoint: str
    chain_id: int
    block_number: int
    block_hash: str
    block_timestamp: int
    epoch_deadline: int
    pool_service_deadline: int
    requested_tag: str
    controller_code_hash: str
    pool_code_hash: str

    def context(self) -> VerificationContext:
        return VerificationContext(self.scope, frozenset(self.monitors))

    def fields(self) -> dict:
        return {
            "schema": "sse-v2-rpc-authority-reference-v1",
            "chainId": self.chain_id, "controller": self.controller,
            "pool": self.pool, "leaseId": self.scope.lease_id,
            "epochId": self.scope.epoch_id,
            "provider": self.provider, "consumer": self.consumer,
            "assignmentId": self.assignment_id, "committee": list(self.monitors),
            "quorum": self.quorum, "reserves": self.reserves,
            "requestHash": self.scope.request_hash,
            "slaPolicyHash": self.scope.sla_policy_hash,
            "resourceProfileHash": self.scope.resource_profile_hash,
            "endpoint": self.endpoint,
            "blockNumber": self.block_number, "blockHash": self.block_hash,
            "blockTimestamp": self.block_timestamp, "requestedTag": self.requested_tag,
            "epochDeadline": self.epoch_deadline,
            "poolServiceDeadline": self.pool_service_deadline,
            "controllerCodeHash": self.controller_code_hash,
            "poolCodeHash": self.pool_code_hash,
            "notice": "RPC_ASSUMPTION_BOUND_RAW_OBSERVATION_NOT_CONSUMER_DELIVERY",
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.fields(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")

    def commitment(self) -> str:
        return "0x" + keccak256(b"SSE_V2_AUTHORITY_REFERENCE_V1\x00" + self.canonical_bytes()).hex()


def read_v2_authority(rpc, spec: V2AuthoritySpec, *,
                      historical_anchor: tuple[int, str] | None = None) -> V2AuthoritySnapshot:
    """Reconstruct a LIVE V2 epoch and selected committee at ONE block.

    The optional historical anchor permits re-verifying an archived observation
    after a committee changes or an epoch closes. It must still be canonical
    according to the caller-trusted RPC, and no more recent than its claimed
    finalized/safe/latest head. This is NOT a consensus state proof.
    Every contract read uses EIP-1898 {blockHash,requireCanonical:true}.
    """
    if not isinstance(spec, V2AuthoritySpec):
        raise V2AuthorityError("expected explicit V2 authority specification")
    s = spec.scope.normalized()
    controller = _validated_address(s.settlement, "controller")
    pool = _validated_address(spec.pool, "pool")
    controller_hash = _canonical_hash(spec.controller_code_hash, "controller_code_hash")
    pool_hash = _canonical_hash(spec.pool_code_hash, "pool_code_hash")

    chain_id = _hex_integer(_rpc(rpc, "eth_chainId", []))
    if chain_id != s.chain_id:
        raise V2AuthorityError("wrong chain ID for signed observation scope")
    tagged = _rpc(rpc, "eth_getBlockByNumber", [spec.block_tag, False])
    if type(tagged) is not dict:
        raise V2AuthorityError("missing selected finality-tagged block")
    tagged_number = _hex_integer(tagged.get("number"))
    tagged_hash = _canonical_hash(tagged.get("hash"), "tagged block hash")
    if historical_anchor is None:
        block = tagged
    else:
        if (type(historical_anchor) is not tuple or len(historical_anchor) != 2 or
                type(historical_anchor[0]) is not int or historical_anchor[0] < 1):
            raise V2AuthorityError("historical anchor requires exact positive height and block hash")
        historical_number, historical_hash = historical_anchor
        historical_hash = _canonical_hash(historical_hash, "historical block hash")
        if historical_number > tagged_number:
            raise V2AuthorityError("archived block is newer than permitted chain finality tag")
        block = _rpc(rpc, "eth_getBlockByNumber", [hex(historical_number), False])
        if (type(block) is not dict or
                _hex_integer(block.get("number")) != historical_number or
                _canonical_hash(block.get("hash"), "historical chain block") != historical_hash):
            raise V2AuthorityError("archived block is missing or no longer canonical")
        if historical_number == tagged_number and historical_hash != tagged_hash:
            raise V2AuthorityError("historical anchor conflicts with selected tagged head")
    block_hash = _canonical_hash(block.get("hash"), "block hash")
    number = _hex_integer(block.get("number"))
    timestamp = _hex_integer(block.get("timestamp"))
    if number < 1:
        raise V2AuthorityError("cannot authorize an uninitialized genesis state")
    pinned = {"blockHash": block_hash, "requireCanonical": True}

    _runtime_fingerprint(rpc, controller, controller_hash, pinned)
    _runtime_fingerprint(rpc, pool, pool_hash, pinned)

    claimed_domain = "0x" + _words(_call_at(rpc, controller, "domainSeparator()", (), pinned), 1)[0]
    if claimed_domain != _v2_domain_separator(chain_id, controller):
        raise V2AuthorityError("wrong V2 controller EIP-712 domain")
    if _address_at(rpc, controller, "pool()", (), pinned) != pool:
        raise V2AuthorityError("controller bound to a different pool")
    if _address_at(rpc, pool, "controller()", (), pinned) != controller:
        raise V2AuthorityError("pool bound to a different controller")
    next_id = _uint_at(rpc, controller, "nextLeaseId()", (), pinned)
    if s.lease_id >= next_id:
        raise V2AuthorityError("lease ID not allocated")

    lease = _decode_at(rpc, controller, "getLease(uint256)", (s.lease_id,),
                       pinned, V2_LEASE_FIELDS)
    consumer, provider = lease["consumer"], lease["provider"]
    if consumer == ZERO_ADDRESS or provider == ZERO_ADDRESS or consumer == provider:
        raise V2AuthorityError("uninitialized or malformed consumer/provider")
    if (lease["profileHash"] != s.resource_profile_hash or
            lease["slaPolicyHash"] != s.sla_policy_hash):
        raise V2AuthorityError("lease SLA/resource commitments differ from signed observation scope")
    endpoint_hash = "0x" + keccak256(spec.endpoint.encode("utf-8")).hex()
    if lease["endpointHash"] != endpoint_hash:
        raise V2AuthorityError("service endpoint differs from funded lease commitment")
    if lease["state"] != 2:
        raise V2AuthorityError("lease is not Live")
    assignment = lease["assignmentId"]
    if assignment == 0:
        raise V2AuthorityError("missing V2 pool assignment")
    if (lease["fee"] == 0 or lease["maxEpochs"] == 0 or lease["maxEpochs"] > 64 or
            lease["nextEpochId"] > lease["maxEpochs"] or
            lease["pending"] > lease["exposureBudget"] or
            lease["exposureBudget"] < lease["fee"]):
        raise V2AuthorityError("V2 lease escrow/epoch bounds invalid")
    conserved = (lease["uncommitted"] + lease["pending"] + lease["consumerCredited"]
                 + lease["providerCredited"] + lease["unusedRefunded"])
    if conserved != lease["escrow"]:
        raise V2AuthorityError("funded V2 lease principal does not conserve")

    if _uint_at(rpc, pool, "status(uint256)", (assignment,), pinned) != 5:
        raise V2AuthorityError("assignment is not Active")
    assignment_terms = _decode_at(rpc, pool, "assignmentTerms(uint256)",
                                  (assignment,), pinned, V2_ASSIGNMENT_FIELDS)
    k, q, reserves = assignment_terms["size"], assignment_terms["quorum"], assignment_terms["reserves"]
    if (k < 3 or k > 16 or q <= k // 2 or q > k or
            reserves > 16 - k or assignment_terms["consumer"] != consumer or
            assignment_terms["provider"] != provider):
        raise V2AuthorityError("V2 committee size/threshold/parties mismatch")
    if (_uint_at(rpc, pool, "selectedCount(uint256)", (assignment,), pinned) != k or
            _uint_at(rpc, pool, "confirmedCount(uint256)", (assignment,), pinned) != k):
        raise V2AuthorityError("selected committee is not fully confirmed")
    service_end = _uint_at(rpc, pool, "serviceDeadline(uint256)", (assignment,), pinned)
    if service_end <= timestamp:
        raise V2AuthorityError("committee service lifetime has ended")
    members: list[str] = []
    for i in range(k):
        member = _address_at(rpc, pool, "seatAt(uint256,uint256)", (assignment, i), pinned)
        if member in (consumer, provider) or member in members:
            raise V2AuthorityError("repeated or interested committee participant")
        ticket = _decode_at(rpc, pool, "tickets(uint256,address)",
                            (assignment, int(member, 16)), pinned, V2_TICKET_FIELDS)
        if not (ticket["joined"] and ticket["paid"] and ticket["everSelected"]
                and ticket["confirmed"]) or ticket["noShow"]:
            raise V2AuthorityError("selected monitor not confirmed with active ticket")
        members.append(member)

    if s.epoch_id >= lease["nextEpochId"]:
        raise V2AuthorityError("epoch not admitted")
    epoch = _decode_at(rpc, controller, "getEpoch(uint256,uint256)",
                       (s.lease_id, s.epoch_id), pinned, V2_EPOCH_FIELDS)
    if (not epoch["admitted"] or epoch["allocated"] or
            epoch["requestHash"] != s.request_hash or epoch["fee"] != lease["fee"] or
            lease["pending"] < epoch["fee"] or epoch["deadline"] > service_end or
            timestamp > epoch["deadline"]):
        raise V2AuthorityError("wrong, resolved or expired V2 epoch")

    # Catch observable height replacement; not an independent finality proof.
    again = _rpc(rpc, "eth_getBlockByNumber", [hex(number), False])
    if (type(again) is not dict or
            _canonical_hash(again.get("hash"), "recheck block hash") != block_hash or
            _hex_integer(again.get("number")) != number):
        raise V2AuthorityError("selected block changed during inspection")

    return V2AuthoritySnapshot(
        scope=s, controller=controller, pool=pool, provider=provider,
        consumer=consumer, assignment_id=assignment, monitors=tuple(members),
        quorum=q, reserves=reserves, endpoint=spec.endpoint,
        chain_id=chain_id, block_number=number, block_hash=block_hash,
        block_timestamp=timestamp, epoch_deadline=epoch["deadline"],
        pool_service_deadline=service_end, requested_tag=spec.block_tag,
        controller_code_hash=controller_hash, pool_code_hash=pool_hash,
    )


def verify_v2_observation(rpc, spec: V2AuthoritySpec, envelope: dict):
    """Verify chain-scoped signed RAW observation only."""
    snapshot = read_v2_authority(rpc, spec)
    return snapshot, verify_observation(envelope, snapshot.context())


def capture_v2_response(rpc, spec: V2AuthoritySpec, monitor_private_key: str,
                        archive, *, nonce: str | None = None, timeout: float = 2.0):
    """Read chain-derived provider/monitor authority, then reuse WP08B transport.

    WARNING: WP08B ProviderResponse uses the LEGACY off-chain V1
    'SSESettlement' EIP-712 provider-response namespace, with V2 controller as
    verifyingContract. This is NOT SSELeaseControllerV2's on-chain EIP712
    'SSELeaseControllerV2' namespace and cannot be used for an on-chain payout.

    The snapshot is returned but NOT atomically stored with the evidence yet.
    These reads precede HTTP and do not prove signer membership at receive time.
    """
    from typed_evidence import Domain
    from sse_http_signed_delivery_v1 import capture_response
    snapshot = read_v2_authority(rpc, spec)
    signed_domain = Domain(snapshot.chain_id, snapshot.controller)
    result = capture_response(
        snapshot.endpoint, signed_domain, snapshot.provider, snapshot.scope,
        monitor_private_key, snapshot.context(), archive, nonce=nonce,
        timeout=timeout,
    )
    return snapshot, result
