"""WP-07 provisional, non-production evidence policy reference (stdlib only).

This model distinguishes raw claims from externally QUALIFIED facts.  A caller
can construct QualifiedFact directly: this module DOES NOT verify signatures,
real-world facts, trusted timestamps, EVM finality, or evidence provenance.
Only R4's future trusted boundary may supply such facts in production.

Two *different contracts* are modeled:
  PHYSICAL_DELIVERY: N/F/S and conditional trust in off-chain certificates.
  CHAIN_PUBLICATION: F/S (no N), where success means a valid response was
                     canonically INCLUDED on chain by a defined deadline.
The latter does not prove compute resources, remote delivery, or cloud SLA QoS.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional

from sse_formal_reference import ALL_WORLDS, SLA, World, Bounds, evaluate

VERSION = 'R1-EVIDENCE-POLICY-DRAFT-1'


class PolicyError(ValueError):
    pass


class ConflictingClaims(PolicyError):
    pass


class PolicyMode(str, Enum):
    PHYSICAL_DELIVERY = 'PHYSICAL_DELIVERY'
    CHAIN_PUBLICATION = 'CHAIN_PUBLICATION'


class Assumption(str, Enum):
    RECEIPT_CERT_SOUND = 'RECEIPT_CERT_SOUND'
    FULFILLMENT_CERT_SOUND = 'FULFILLMENT_CERT_SOUND'
    NONFULFILLMENT_CERT_SOUND = 'NONFULFILLMENT_CERT_SOUND'
    CANONICAL_CHAIN_COMPLETE = 'CANONICAL_CHAIN_COMPLETE'


class RawKind(str, Enum):
    PROVIDER_SIGNED_ACK = 'PROVIDER_SIGNED_ACK'
    PROVIDER_SIGNED_RESPONSE = 'PROVIDER_SIGNED_RESPONSE'
    MONITOR_SUCCESS = 'MONITOR_SUCCESS'
    MONITOR_TIMEOUT = 'MONITOR_TIMEOUT'
    CONSUMER_CLAIM = 'CONSUMER_CLAIM'


class FactKind(str, Enum):
    PHYSICAL_RECEIPT = 'PHYSICAL_RECEIPT'
    PHYSICAL_FULFILLMENT = 'PHYSICAL_FULFILLMENT'
    PHYSICAL_NONFULFILLMENT = 'PHYSICAL_NONFULFILLMENT'


_FACT_ASSUMPTION = {
    FactKind.PHYSICAL_RECEIPT: Assumption.RECEIPT_CERT_SOUND,
    FactKind.PHYSICAL_FULFILLMENT: Assumption.FULFILLMENT_CERT_SOUND,
    FactKind.PHYSICAL_NONFULFILLMENT: Assumption.NONFULFILLMENT_CERT_SOUND,
}
_FACT_WORLDS = {
    FactKind.PHYSICAL_RECEIPT: frozenset((World.F, World.S)),
    FactKind.PHYSICAL_FULFILLMENT: frozenset((World.S,)),
    FactKind.PHYSICAL_NONFULFILLMENT: frozenset((World.N, World.F)),
}


def _integer(value: int, name: str, at_least: int = 0) -> None:
    if type(value) is not int or value < at_least:
        raise PolicyError(f'{name} must be integer >= {at_least}')


@dataclass(frozen=True)
class Binding:
    lease_id: int
    epoch_id: int
    sla_hash: str

    def __post_init__(self):
        _integer(self.lease_id, 'lease_id', 1)
        _integer(self.epoch_id, 'epoch_id')
        if not (type(self.sla_hash) is str and len(self.sla_hash) == 66 and
                self.sla_hash.startswith('0x') and
                all(c in '0123456789abcdef' for c in self.sla_hash[2:])):
            raise PolicyError('sla_hash must be canonical lowercase bytes32 hex')


@dataclass(frozen=True)
class PolicyManifest:
    binding: Binding
    mode: PolicyMode
    admission_time: int
    deadline: int
    assumptions: FrozenSet[Assumption] = frozenset()
    version: str = VERSION

    def __post_init__(self):
        if self.version != VERSION:
            raise PolicyError('unsupported evidence policy version')
        if not isinstance(self.mode, PolicyMode):
            raise PolicyError('unsupported service policy mode')
        _integer(self.admission_time, 'admission_time')
        _integer(self.deadline, 'deadline')
        if self.deadline <= self.admission_time:
            raise PolicyError('deadline must be after admission')
        if not isinstance(self.assumptions, frozenset) or not all(
                isinstance(a, Assumption) for a in self.assumptions):
            raise PolicyError('assumptions must be a frozenset of known Assumption values')
        if self.mode == PolicyMode.PHYSICAL_DELIVERY:
            if Assumption.CANONICAL_CHAIN_COMPLETE in self.assumptions:
                raise PolicyError('chain-finality assumption belongs to chain policy')
        elif self.assumptions - {Assumption.CANONICAL_CHAIN_COMPLETE}:
            raise PolicyError('off-chain certificates are not chain-publication proofs')


@dataclass(frozen=True)
class TimeInterval:
    lower: int
    upper: int

    def __post_init__(self):
        _integer(self.lower, 'lower')
        _integer(self.upper, 'upper')
        if self.lower > self.upper:
            raise PolicyError('inverted timing interval')

    def is_certainly_timely(self, deadline: int) -> bool:
        return self.upper <= deadline

    def is_certainly_late(self, deadline: int) -> bool:
        return self.lower > deadline


@dataclass(frozen=True)
class RawObservation:
    binding: Binding
    evidence_id: str
    kind: RawKind
    signer: str

    def __post_init__(self):
        if not isinstance(self.kind, RawKind) or not self.evidence_id or not self.signer:
            raise PolicyError('invalid raw report')


@dataclass(frozen=True)
class QualifiedFact:
    binding: Binding
    evidence_id: str
    kind: FactKind
    assumption: Assumption
    verifier_reference: str
    event_time: Optional[TimeInterval] = None

    def __post_init__(self):
        if (not isinstance(self.kind, FactKind) or
                not isinstance(self.assumption, Assumption) or
                type(self.evidence_id) is not str or not self.evidence_id or
                type(self.verifier_reference) is not str or not self.verifier_reference):
            raise PolicyError('invalid qualified fact')
        if self.event_time is not None and not isinstance(self.event_time, TimeInterval):
            raise PolicyError('invalid time interval')


@dataclass(frozen=True)
class PolicyDecision:
    histories: FrozenSet[World]
    funds: Bounds
    accepted_fact_ids: FrozenSet[str]
    raw_report_count: int


@dataclass(frozen=True)
class PhysicalPolicyState:
    """Transactional refinements; neither votes nor unsigned claims exclude worlds.

    A qualified fact is only an *assumed* certificate in this prototype. The
    policy's whitelist must NOT be interpreted as cryptographic verification.
    """
    manifest: PolicyManifest
    sla: SLA
    histories: FrozenSet[World] = ALL_WORLDS
    raw: tuple[RawObservation, ...] = ()
    facts: tuple[QualifiedFact, ...] = ()

    def __post_init__(self):
        if self.manifest.mode != PolicyMode.PHYSICAL_DELIVERY:
            raise PolicyError('physical interpreter requires a delivery manifest')
        if not self.histories or not self.histories.issubset(ALL_WORLDS):
            raise PolicyError('invalid current history set')

    def _same_scope(self, binding: Binding) -> None:
        if binding != self.manifest.binding:
            raise PolicyError('lease/epoch/SLA commitment mismatch')

    def with_raw(self, item: RawObservation) -> 'PhysicalPolicyState':
        self._same_scope(item.binding)
        for old in (*self.raw, *self.facts):
            if old.evidence_id == item.evidence_id:
                if old == item:
                    return self
                raise PolicyError('evidence ID reused with different payload')
        return PhysicalPolicyState(self.manifest, self.sla, self.histories,
                                   self.raw + (item,), self.facts)

    def with_fact(self, item: QualifiedFact, observed_at: int) -> 'PhysicalPolicyState':
        self._same_scope(item.binding)
        _integer(observed_at, 'observed_at')
        if observed_at < self.manifest.admission_time:
            raise PolicyError('cannot use facts before the epoch exists')
        for old in (*self.raw, *self.facts):
            if old.evidence_id == item.evidence_id:
                if old == item:
                    return self
                raise PolicyError('evidence ID reused with different payload')
        required = _FACT_ASSUMPTION[item.kind]
        if item.assumption != required or required not in self.manifest.assumptions:
            raise PolicyError('claim not authorized by explicit trust assumptions')
        # Fulfillment means the RESULT REACHED the consumer by the SLA deadline.
        # Correctness/provenance alone is not sufficient for this service profile.
        if item.kind == FactKind.PHYSICAL_FULFILLMENT:
            if item.event_time is None:
                raise PolicyError('consumer delivery requires a time interval')
            if not item.event_time.is_certainly_timely(self.manifest.deadline):
                # Keep the report for audit, but DO NOT eliminate any histories.
                restriction = ALL_WORLDS
            elif item.event_time.lower < self.manifest.admission_time:
                raise PolicyError('delivery cannot precede admission')
            else:
                restriction = _FACT_WORLDS[item.kind]
        elif item.kind == FactKind.PHYSICAL_NONFULFILLMENT:
            # A full-epoch nonfulfillment certificate only becomes meaningful
            # once the service's contractual completion deadline has passed.
            restriction = (_FACT_WORLDS[item.kind] if
                           observed_at > self.manifest.deadline else ALL_WORLDS)
        else:
            restriction = _FACT_WORLDS[item.kind]
        refined = self.histories & restriction
        if not refined:
            raise ConflictingClaims('assumption-qualified evidence conflicts: halt, no payout')
        return PhysicalPolicyState(self.manifest, self.sla, refined,
                                   self.raw, self.facts + (item,))

    def decision(self) -> PolicyDecision:
        return PolicyDecision(self.histories, evaluate(self.sla, self.histories),
                              frozenset(x.evidence_id for x in self.facts), len(self.raw))


@dataclass(frozen=True)
class ChainSnapshot:
    """Externally SUPPLIED canonical-chain view; NO RPC or consensus verification.

    finalized_through is the latest included chain timestamp through which
    absence/completeness is assumed. A valid response's inclusion time is
    canonical and checked for the agreed challenge by an external verifier.
    A snapshot is NOT trustworthy merely because Python constructs it.
    """
    binding: Binding
    finalized_through: int
    valid_response_included_at: Optional[int] = None

    def __post_init__(self):
        _integer(self.finalized_through, 'finalized_through')
        if self.valid_response_included_at is not None:
            _integer(self.valid_response_included_at, 'valid_response_included_at')


@dataclass(frozen=True)
class ChainPolicyState:
    """Alternative ON-CHAIN PUBLICATION contract: only F/S, no physical N.

    The consumer purchases on-chain publication by a fixed deadline, not
    remote compute resources or timely consumer receipt. Finality is assumed.
    """
    manifest: PolicyManifest
    sla: SLA
    histories: FrozenSet[World] = frozenset((World.F, World.S))
    finalized_until: int = 0

    def __post_init__(self):
        if self.manifest.mode != PolicyMode.CHAIN_PUBLICATION:
            raise PolicyError('chain interpreter needs a publication manifest')
        if self.histories not in (frozenset((World.F, World.S)),
                                  frozenset((World.F,)), frozenset((World.S,))):
            raise PolicyError('invalid chain publication outcome set')

    def advance(self, snap: ChainSnapshot) -> 'ChainPolicyState':
        if snap.binding != self.manifest.binding:
            raise PolicyError('chain evidence scoped to wrong epoch/SLA')
        if Assumption.CANONICAL_CHAIN_COMPLETE not in self.manifest.assumptions:
            raise PolicyError('canonical-chain completeness not assumed')
        if snap.finalized_through < self.finalized_until:
            raise PolicyError('canonical-finality regression')
        inclusion = snap.valid_response_included_at
        if inclusion is not None and inclusion < self.manifest.admission_time:
            raise PolicyError('response predates contractual epoch')
        if inclusion is not None and inclusion > snap.finalized_through:
            # A pending transaction cannot authorize irreversible payment.
            eligible = frozenset((World.F, World.S))
        elif inclusion is not None and inclusion <= self.manifest.deadline:
            eligible = frozenset((World.S,))
        elif snap.finalized_through >= self.manifest.deadline:
            eligible = frozenset((World.F,))
        else:
            eligible = frozenset((World.F, World.S))
        refined = self.histories & eligible
        if not refined:
            raise ConflictingClaims('conflicting canonical snapshots: do not reverse payouts')
        return ChainPolicyState(self.manifest, self.sla, refined, snap.finalized_through)

    def decision(self) -> PolicyDecision:
        return PolicyDecision(self.histories, evaluate(self.sla, self.histories),
                              frozenset(), 0)
