"""WP-08C: read-only, block-hash-pinned SSE V1 authorization.

RPC responses are CONDITIONAL INPUTS, not trustless state proofs. The supplied
provider/committee deployment fingerprints and RPC/finality assumptions must
come from a trusted configuration. This module does not qualify physical facts,
declare consumer delivery, send on-chain votes, or release escrow.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from sse_challenge import expected_response_hash, keccak256
from sse_chain_read import (
    ChainReadError, LEASE_FIELDS, EPOCH_FIELDS, decode_struct, _call,
    _address, _hex_integer, _words, _domain_separator,
)
from sse_evidence_wire_v1 import (
    EvidenceScope, VerificationContext, verify_observation,
)

ZERO_ADDRESS = "0x" + "00" * 20
ZERO_HASH = "0x" + "00" * 32
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEX_BYTES = re.compile(r"0x(?:[0-9a-fA-F]{2})*\Z")


class ChainAuthorityError(ChainReadError):
    """The supplied RPC view cannot authorize this exact signed observation."""


def _hash(value: str, field: str) -> str:
    if type(value) is not str or not HASH.fullmatch(value) or int(value[2:], 16) == 0:
        raise ChainAuthorityError(f"{field} must be a nonzero bytes32 hash")
    return value.lower()


def _address_word(data: str, field: str) -> str:
    word = _words(data, 1)[0]
    if int(word, 16) >> 160:
        raise ChainAuthorityError(f"{field} has noncanonical ABI address")
    address = "0x" + word[-40:]
    if address == ZERO_ADDRESS:
        raise ChainAuthorityError(f"{field} has zero address")
    return address


def _unsigned_word(data: str, field: str) -> int:
    try:
        return int(_words(data, 1)[0], 16)
    except (ValueError, TypeError) as exc:
        raise ChainAuthorityError(f"invalid {field}") from exc


def _rpc(rpc, method: str, params: list):
    if not hasattr(rpc, "request") or not callable(rpc.request):
        raise ChainAuthorityError("explicit RPC client with request() is required")
    try:
        return rpc.request(method, params)
    except Exception as exc:
        raise ChainAuthorityError(f"RPC {method} failed closed") from exc


def _call_at(rpc, address: str, signature: str, args: tuple[int, ...], pinned: dict) -> str:
    try:
        return _call(rpc, address, signature, args, pinned)
    except (ChainReadError, ValueError, TypeError, OverflowError) as exc:
        raise ChainAuthorityError(f"invalid pinned call: {signature}") from exc


def _read_code_hash(rpc, address: str, pinned: dict, expected: str) -> None:
    code = _rpc(rpc, "eth_getCode", [address, pinned])
    if type(code) is not str or not HEX_BYTES.fullmatch(code) or len(code) <= 2:
        raise ChainAuthorityError("missing or malformed deployed contract bytecode")
    digest = "0x" + keccak256(bytes.fromhex(code[2:])).hex()
    if digest != expected:
        raise ChainAuthorityError("deployed runtime code does not match trusted fingerprint")


@dataclass(frozen=True)
class AuthoritySpec:
    """Trust input. Code hashes MUST be known independently of this RPC view."""
    scope: EvidenceScope
    committee_contract: str
    settlement_code_hash: str
    committee_code_hash: str
    block_tag: str = "finalized"
    allow_unfinalized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EvidenceScope):
            raise ChainAuthorityError("required exact evidence scope missing")
        committee = _address(self.committee_contract)
        if committee == ZERO_ADDRESS:
            raise ChainAuthorityError("zero committee contract")
        _hash(self.settlement_code_hash, "settlement_code_hash")
        _hash(self.committee_code_hash, "committee_code_hash")
        if self.block_tag not in ("finalized", "safe", "latest"):
            raise ChainAuthorityError("unsupported chain block tag")
        if type(self.allow_unfinalized) is not bool:
            raise ChainAuthorityError("allow_unfinalized must be a boolean")
        if self.block_tag != "finalized" and not self.allow_unfinalized:
            raise ChainAuthorityError("safe/latest requires explicit unfinalized opt-in")


@dataclass(frozen=True)
class ChainAuthoritySnapshot:
    """Attribution under trusted-code + trusted-RPC/finality assumptions only."""
    scope: EvidenceScope
    committee_contract: str
    provider: str
    consumer: str
    monitors: tuple[str, str, str, str]
    assignment_id: int
    chain_id: int
    block_number: int
    block_hash: str
    block_timestamp: int
    requested_tag: str
    settlement_code_hash: str
    committee_code_hash: str

    def verification_context(self) -> VerificationContext:
        return VerificationContext(self.scope, frozenset(self.monitors))

    def fields(self) -> dict:
        return {
            "schema": "sse-chain-authority-reference-v1",
            "chainId": self.chain_id, "blockNumber": self.block_number,
            "blockHash": self.block_hash, "blockTimestamp": self.block_timestamp,
            "requestedTag": self.requested_tag,
            "settlement": self.scope.settlement.lower(),
            "committee": self.committee_contract.lower(),
            "leaseId": self.scope.lease_id, "epochId": self.scope.epoch_id,
            "requestHash": self.scope.request_hash,
            "slaPolicyHash": self.scope.sla_policy_hash,
            "resourceProfileHash": self.scope.resource_profile_hash,
            "provider": self.provider, "consumer": self.consumer,
            "monitors": list(self.monitors), "assignmentId": self.assignment_id,
            "settlementCodeHash": self.settlement_code_hash.lower(),
            "committeeCodeHash": self.committee_code_hash.lower(),
            "limitations": [
                "RPC responses are not independently authenticated Ethereum state proofs",
                "finalized is only a tag asserted by the chosen RPC",
                "selected monitor observation is not physical consumer delivery",
            ],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.fields(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")

    def commitment(self) -> str:
        return "0x" + keccak256(b"SSE_CHAIN_AUTHORITY_V1\x00" + self.canonical_bytes()).hex()


def read_chain_authority(rpc, spec: AuthoritySpec) -> ChainAuthoritySnapshot:
    """Bind V1 lease, epoch, provider, 4 confirmations and committee to ONE block.

    All state queries use EIP-1898 {blockHash,requireCanonical:true}. Unsupported
    RPCs fail closed; there is NO silent downgrade to numbered/latest eth_call.
    """
    if not isinstance(spec, AuthoritySpec):
        raise ChainAuthorityError("AuthoritySpec required")
    s = spec.scope
    chain_id = _hex_integer(_rpc(rpc, "eth_chainId", []))
    if chain_id != s.chain_id:
        raise ChainAuthorityError("chain ID differs from signed observation scope")
    block = _rpc(rpc, "eth_getBlockByNumber", [spec.block_tag, False])
    if type(block) is not dict:
        raise ChainAuthorityError("missing tagged chain block")
    number = _hex_integer(block.get("number"))
    timestamp = _hex_integer(block.get("timestamp"))
    block_hash = _hash(block.get("hash"), "block.hash")
    if number < 1:
        raise ChainAuthorityError("zero-height block is not usable for lease authorization")
    pinned = {"blockHash": block_hash, "requireCanonical": True}

    settlement = _address(s.settlement)
    committee = _address(spec.committee_contract)
    _read_code_hash(rpc, settlement, pinned, _hash(spec.settlement_code_hash, "settlement_code_hash"))
    _read_code_hash(rpc, committee, pinned, _hash(spec.committee_code_hash, "committee_code_hash"))

    domain = _call_at(rpc, settlement, "domainSeparator()", (), pinned)
    if _words(domain, 1)[0] != _domain_separator(chain_id, settlement)[2:]:
        raise ChainAuthorityError("settlement EIP-712 identity mismatch")
    real_pool = _address_word(_call_at(rpc, settlement, "committeePool()", (), pinned), "committeePool")
    if real_pool != committee:
        raise ChainAuthorityError("lease settlement points to another committee contract")
    reverse_settlement = _address_word(
        _call_at(rpc, committee, "settlement()", (), pinned), "pool.settlement")
    if reverse_settlement != settlement:
        raise ChainAuthorityError("committee not bound to this settlement")

    next_lease = _unsigned_word(
        _call_at(rpc, settlement, "nextLeaseId()", (), pinned), "nextLeaseId")
    if s.lease_id >= next_lease:
        raise ChainAuthorityError("lease does not exist")
    lease = decode_struct(_call_at(rpc, settlement, "getLease(uint256)", (s.lease_id,), pinned),
                          LEASE_FIELDS)
    provider, consumer = lease["provider"], lease["consumer"]
    if provider == ZERO_ADDRESS or consumer == ZERO_ADDRESS or provider == consumer:
        raise ChainAuthorityError("uninitialized or malformed lease parties")
    if lease["slaPolicyHash"] != s.sla_policy_hash or (
            lease["resourceProfileHash"] != s.resource_profile_hash):
        raise ChainAuthorityError("evidence SLA/resource commitments mismatch on-chain lease")
    if lease["state"] not in (2, 3) or lease["monitorConfirmations"] != 4:
        raise ChainAuthorityError("lease committee not fully confirmed and live")
    monitors = tuple(lease["monitors"])
    if (len(monitors) != 4 or len(set(monitors)) != 4
            or any(x in (ZERO_ADDRESS, consumer, provider) for x in monitors)):
        raise ChainAuthorityError("invalid selected monitor identities")
    assignment = lease["assignmentId"]
    if assignment <= 0:
        raise ChainAuthorityError("missing assignment ID")
    if _unsigned_word(_call_at(rpc, committee, "assignmentStatus(uint256)",
                               (assignment,), pinned), "assignmentStatus") != 2:
        raise ChainAuthorityError("monitor assignment is not live")
    committee_raw = _call_at(rpc, committee, "getCommittee(uint256)", (assignment,), pinned)
    committee_words = _words(committee_raw, 4)
    committee_monitors = tuple(_address_word("0x" + w, "monitor") for w in committee_words)
    if committee_monitors != monitors:
        raise ChainAuthorityError("settlement/committee selected rosters disagree")

    if s.epoch_id >= lease["nextEpochId"]:
        raise ChainAuthorityError("epoch has not been admitted")
    epoch = decode_struct(
        _call_at(rpc, settlement, "getEpoch(uint256,uint256)", (s.lease_id, s.epoch_id), pinned),
        EPOCH_FIELDS)
    if not epoch["exists"] or epoch["requestHash"] != s.request_hash:
        raise ChainAuthorityError("wrong or missing admitted epoch request")
    if epoch["responseHash"] != expected_response_hash(s.request_hash):
        raise ChainAuthorityError("contractual expected response mismatch")
    if not (epoch["responseDeadline"] <= epoch["monitoringClose"] < epoch["evidenceClose"]):
        raise ChainAuthorityError("invalid epoch window ordering")
    if epoch["monitoringSealed"] or epoch["evidenceClosed"] or timestamp > epoch["monitoringClose"]:
        raise ChainAuthorityError("monitoring already closed at selected block")

    # Spot a canonical replacement before returning; EIP-1898 itself must also be supported.
    block_again = _rpc(rpc, "eth_getBlockByNumber", [hex(number), False])
    if (type(block_again) is not dict or
            _hash(block_again.get("hash"), "rechecked block.hash") != block_hash or
            _hex_integer(block_again.get("number")) != number):
        raise ChainAuthorityError("pinned block changed or was reorganized")
    return ChainAuthoritySnapshot(
        scope=s, committee_contract=committee, provider=provider, consumer=consumer,
        monitors=monitors, assignment_id=assignment, chain_id=chain_id,
        block_number=number, block_hash=block_hash, block_timestamp=timestamp,
        requested_tag=spec.block_tag,
        settlement_code_hash=_hash(spec.settlement_code_hash, "settlement_code_hash"),
        committee_code_hash=_hash(spec.committee_code_hash, "committee_code_hash"),
    )


def verify_against_chain(rpc, spec: AuthoritySpec, envelope: object):
    """Authenticate a monitor's signed RAW statement against chain-derived identity."""
    snap = read_chain_authority(rpc, spec)
    return snap, verify_observation(envelope, snap.verification_context())


def capture_with_chain_authority(rpc, spec: AuthoritySpec, endpoint: str,
                                 monitor_private_key: str, archive, *,
                                 nonce: str | None = None, timeout: float = 2.0):
    """Research-only bridge to WP-08B; no live money or physical-fact certification.

    Persist snapshot.canonical_bytes() alongside the returned evidence ID if the
    archive will be independently audited. WP-08B SQLite does not yet atomically
    store this chain reference: that remains a separate integration gate.
    """
    from typed_evidence import Domain
    from sse_http_signed_delivery_v1 import capture_response
    snap = read_chain_authority(rpc, spec)
    saved = capture_response(
        endpoint, Domain(snap.chain_id, snap.scope.settlement),
        snap.provider, snap.scope, monitor_private_key, snap.verification_context(),
        archive, nonce=nonce, timeout=timeout)
    return snap, saved
