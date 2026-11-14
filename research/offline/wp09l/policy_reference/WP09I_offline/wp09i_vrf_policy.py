"""WP-09I: offline, provider-bound VRF *consumer policy* reference.

This intentionally does NOT implement/forge VRF cryptographic proofs. It models
an authenticated callback from a coordinator that verified a standardized VRF
proof on chain (e.g. Chainlink VRF v2.5). Mock caller identifiers in tests are
NOT authentication outside a smart contract. Do not deploy this Python class.

No automatic randomness reroll, no assignment cancellation-for-reroll, no
fallback to blockhash, no seed chosen from a quorum/receipt subset.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final
from keccak import keccak256

DOMAIN: Final[bytes] = keccak256(b"SSE-WP09I-COORDINATOR-BOUND-ENTROPY-V1")
UINT256 = 1 << 256


def word(x: int) -> bytes:
    if type(x) is not int or not 0 <= x < UINT256:
        raise ValueError("expected uint256")
    return x.to_bytes(32, "big")


def addr(x: str) -> bytes:
    if not isinstance(x, str) or len(x) != 42 or not x.startswith("0x"):
        raise ValueError("expected 20-byte EVM address")
    try:
        raw = bytes.fromhex(x[2:])
    except ValueError as exc:
        raise ValueError("invalid address") from exc
    if raw == bytes(20):
        raise ValueError("address cannot be zero")
    return raw


def bytes32(x: bytes) -> bytes:
    if not isinstance(x, bytes) or len(x) != 32 or x == bytes(32):
        raise ValueError("nonzero bytes32 required")
    return x


class Phase(str, Enum):
    REQUESTED = "requested"
    READY = "ready"
    APPLIED = "applied"
    EXPIRED = "expired"


class Decision(str, Enum):
    STORED = "stored"
    DUPLICATE_IGNORED = "duplicate_ignored"
    LATE_IGNORED = "late_ignored"
    UNKNOWN_IGNORED = "unknown_ignored"


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    version: int
    chain_id: int
    coordinator: str
    key_hash: bytes
    subscription_id: int
    confirmations: int
    callback_gas_limit: int
    native_payment: bool

    def __post_init__(self) -> None:
        if self.version <= 0 or self.chain_id <= 0 or self.subscription_id <= 0:
            raise ValueError("invalid profile identity")
        addr(self.coordinator)
        bytes32(self.key_hash)
        if not 1 <= self.confirmations <= 200:
            raise ValueError("invalid confirmations; network bounds must ALSO be verified")
        if not 10_000 <= self.callback_gas_limit <= 2_500_000:
            raise ValueError("invalid callback gas budget; check network coordinator limits")
        if type(self.native_payment) is not bool:
            raise ValueError("invalid payment mode")


@dataclass
class Request:
    lease_id: int
    vrf_id: int
    profile_version: int
    snapshot_root: bytes
    snapshot_count: int
    request_block: int
    opened_at: int
    deadline: int
    digest: bytes
    phase: Phase = Phase.REQUESTED
    raw_word: int | None = None
    applied_seed: int | None = None
    # Stores ignored callback count for reproducible event audit, not fees.
    ignored_callbacks: int = 0


@dataclass
class VRFPolicy:
    """Single consumer, multi-profile, immutable per-request provenance.

    A coordinator may own outstanding requests after future requests move to
    another profile. Rotation NEVER changes existing request provenance.
    """
    chain_id: int
    consumer_contract: str
    settlement_contract: str
    governance_contract: str
    profiles: dict[int, Profile]
    active_version: int
    requests: dict[tuple[str, int], Request] = field(default_factory=dict)
    lease_to_vrf: dict[int, tuple[str, int]] = field(default_factory=dict)
    disabled_for_new: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        addr(self.consumer_contract)
        addr(self.settlement_contract)
        addr(self.governance_contract)
        if self.chain_id <= 0 or self.active_version not in self.profiles:
            raise ValueError("invalid policy environment")
        for key, profile in self.profiles.items():
            if key != profile.version or profile.chain_id != self.chain_id:
                raise ValueError("profile/chain mismatch")

    def rotate_future_requests(self, new_profile: Profile, *, caller: str) -> None:
        """Deploy/configuration-level rotation: no on-chain admin API implied.

        New profile MUST have independently audited authenticated coordinator,
        key hash, subscription and chain. In-flight requests pin old profile.
        """
        if caller.lower() != self.governance_contract.lower():
            raise PolicyError("only governance can rotate a profile")
        if new_profile.chain_id != self.chain_id or new_profile.version in self.profiles:
            raise PolicyError("duplicate or wrong-chain profile")
        self.profiles[new_profile.version] = new_profile
        self.disabled_for_new.add(self.active_version)
        self.active_version = new_profile.version

    def decommission_profile(self, version: int, *, caller: str) -> None:
        if caller.lower() != self.governance_contract.lower():
            raise PolicyError("only governance can retire a profile")
        if version == self.active_version:
            raise PolicyError("cannot retire active profile")
        if any(r.profile_version == version and r.phase in (Phase.REQUESTED, Phase.READY)
               for r in self.requests.values()):
            raise PolicyError("coordinator still has in-flight requests")
        self.disabled_for_new.add(version)
        # Keep immutable profile details for historical callback authentication.

    def issue_request(self, *, caller: str, lease_id: int, coordinator_request_id: int,
                      root: bytes, count: int, request_block: int,
                      opened_at: int, deadline: int, provider_version: int | None = None) -> Request:
        if caller.lower() != self.settlement_contract.lower():
            raise PolicyError("only bound settlement can initiate")
        if type(lease_id) is not int or lease_id <= 0 or lease_id in self.lease_to_vrf:
            raise PolicyError("same lease cannot request randomness twice, even after expiry")
        if type(coordinator_request_id) is not int or coordinator_request_id <= 0:
            raise PolicyError("invalid coordinator request ID")
        if provider_version is not None and provider_version != self.active_version:
            raise PolicyError("caller cannot pick old or future coordinator profile")
        profile = self.profiles[self.active_version]
        if profile.version in self.disabled_for_new:
            raise PolicyError("profile is disabled")
        key = (profile.coordinator.lower(), coordinator_request_id)
        if key in self.requests:
            raise PolicyError("coordinator request ID replay for same coordinator")
        bytes32(root)
        if type(count) is not int or count < 4 or count > (1 << 20):
            raise PolicyError("invalid global candidate count")
        if (type(request_block) is not int or request_block < 0 or
                type(opened_at) is not int or type(deadline) is not int or
                opened_at < 0 or deadline <= opened_at):
            raise PolicyError("invalid clock bounds")
        # ABI-equivalent word encoding (all parameters are fixed-width).
        digest = keccak256(DOMAIN + word(self.chain_id) + addr(self.consumer_contract).rjust(32, b'\0')
                           + word(lease_id) + word(coordinator_request_id) + root
                           + word(count) + word(request_block) + word(opened_at)
                           + word(deadline) + word(profile.version) + profile.key_hash
                           + addr(profile.coordinator).rjust(32, b'\0'))
        record = Request(lease_id, coordinator_request_id, profile.version, root,
                         count, request_block, opened_at, deadline, digest)
        self.requests[key] = record
        self.lease_to_vrf[lease_id] = key
        return record

    def coordinator_callback(self, *, caller: str, coordinator_request_id: int,
                             random_words: tuple[int, ...], now: int) -> Decision:
        """Mock of a VERIFIED coordinator callback; must be authenticated ON-CHAIN.

        Deliberately non-throwing for valid-authority duplicate/late callbacks,
        so a production callback can store only and return without a revert.
        """
        if type(now) is not int or now < 0:
            raise PolicyError("invalid clock")
        if caller.lower() not in {p.coordinator.lower() for p in self.profiles.values()}:
            raise PolicyError("untrusted coordinator caller")
        record = self.requests.get((caller.lower(), coordinator_request_id))
        if record is None:
            return Decision.UNKNOWN_IGNORED
        if record.phase in (Phase.APPLIED, Phase.EXPIRED):
            record.ignored_callbacks += 1
            return Decision.LATE_IGNORED
        if record.phase == Phase.READY:
            record.ignored_callbacks += 1
            return Decision.DUPLICATE_IGNORED
        if now > record.deadline:
            # Delayed coordinator output must NOT silently resurrect a lease.
            record.phase = Phase.EXPIRED
            record.ignored_callbacks += 1
            return Decision.LATE_IGNORED
        if (type(random_words) is not tuple or len(random_words) != 1 or
                type(random_words[0]) is not int or not 0 <= random_words[0] < UINT256):
            raise PolicyError("one uint256 randomness word required")
        record.raw_word = random_words[0]
        record.phase = Phase.READY
        return Decision.STORED

    def apply_seed(self, *, lease_id: int, now: int) -> int:
        key = self.lease_to_vrf.get(lease_id)
        record = self.requests.get(key) if key is not None else None
        if record is None or record.phase != Phase.READY:
            raise PolicyError("randomness not ready")
        if now < record.opened_at or now > record.deadline:
            raise PolicyError("cannot apply randomness after deadline")
        assert record.raw_word is not None
        seed = int.from_bytes(keccak256(DOMAIN + record.digest + word(record.raw_word)), "big")
        record.applied_seed = seed
        record.phase = Phase.APPLIED
        return seed

    def expire(self, *, lease_id: int, now: int) -> None:
        key = self.lease_to_vrf.get(lease_id)
        record = self.requests.get(key) if key is not None else None
        if record is None or record.phase not in (Phase.REQUESTED, Phase.READY) or now <= record.deadline:
            raise PolicyError("cannot expire request")
        record.phase = Phase.EXPIRED
        # Preserve request ID and audit digest; no second oracle request.
        record.raw_word = None

    def progress(self) -> dict[str, int]:
        return {p.value: sum(r.phase == p for r in self.requests.values()) for p in Phase}
