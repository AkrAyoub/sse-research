"""Independent, intentionally conservative R1 SSE research oracle (stdlib only).

Not a network authenticator, not a blockchain implementation, and not a proof
that a witness's statement corresponds to the physical world. The assumption
switches are explicit because the raw observations are insufficient to safely
exclude contractual histories without additional guarantees.

R1-PROVISIONAL-0: N/F/S simplified physical histories, not a final SLA policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class World(str, Enum):
    N = "N"  # request not physically received; reservation entitlement
    F = "F"  # received, contractual fulfillment not achieved
    S = "S"  # received, contractual fulfillment achieved


ALL_WORLDS: FrozenSet[World] = frozenset(World)


class InvalidModel(ValueError):
    """SLA inputs or accounting invariants are invalid."""


class InconsistentEvidence(InvalidModel):
    """Qualified claims have eliminated all candidate worlds; fail closed."""


class EvidenceRetraction(InvalidModel):
    """The purported update is not a monotone refinement of previous worlds."""


def _amount(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise InvalidModel(f"{name} must be a nonnegative integer monetary amount")


@dataclass(frozen=True)
class SLA:
    fee: int
    reservation: int

    def __post_init__(self) -> None:
        _amount(self.fee, "fee")
        _amount(self.reservation, "reservation")
        if self.fee == 0 or self.reservation > self.fee:
            raise InvalidModel("require 0 <= reservation <= fee and fee > 0")

    def entitlement(self, world: World) -> int:
        if not isinstance(world, World):
            raise InvalidModel("unknown contractual world")
        return {World.N: self.reservation, World.F: 0, World.S: self.fee}[world]


@dataclass(frozen=True)
class Observations:
    """Statements obtained externally, not assertions of physical truth.

    Votes are not automatically certificates. A certificate here means an
    external proof/attestation whose *soundness is assumed*, never established
    by this Python program. The actual certificate verifier is future R4 work.
    """

    provider_signed_ack: bool = False
    provider_signed_response: bool = False
    no_response_observed: bool = False
    failure_votes: int = 0
    success_votes: int = 0
    certified_nonfulfillment: bool = False
    certified_fulfillment: bool = False

    def __post_init__(self) -> None:
        for name in ("provider_signed_ack", "provider_signed_response", "no_response_observed",
                     "certified_nonfulfillment", "certified_fulfillment"):
            if type(getattr(self, name)) is not bool:
                raise InvalidModel(f"{name} must be bool")
        for name in ("failure_votes", "success_votes"):
            _amount(getattr(self, name), name)


@dataclass(frozen=True)
class Assumptions:
    """Explicit, potentially unrealistic trust assumptions for hypothetical proofs.

    All False is the default safe-without-external-assumptions interpretation.
    A True switch does *not* prove that the assumption holds in real cloud use.
    """

    ack_proves_physical_receipt: bool = False
    nonfulfillment_certificate_is_sound: bool = False
    fulfillment_certificate_is_sound: bool = False
    version: str = "R1-PROVISIONAL-0"

    def __post_init__(self) -> None:
        for name in ("ack_proves_physical_receipt", "nonfulfillment_certificate_is_sound",
                     "fulfillment_certificate_is_sound"):
            if type(getattr(self, name)) is not bool:
                raise InvalidModel(f"{name} must be bool")
        if self.version != "R1-PROVISIONAL-0":
            raise InvalidModel("unsupported provisional policy version")


def interpret(observations: Observations, assumptions: Assumptions = Assumptions()) -> FrozenSet[World]:
    """Return only worlds not excluded by *explicitly justified* claims.

    This is a specification oracle, *not* a decoder of Solidity's quorum rule.
    In particular, 3/4 negative monitor votes, response nonarrival, and
    signed response bytes alone eliminate no worlds under the default policy.
    """
    worlds = set(ALL_WORLDS)
    if observations.provider_signed_ack and assumptions.ack_proves_physical_receipt:
        worlds.intersection_update((World.F, World.S))
    if observations.certified_nonfulfillment and assumptions.nonfulfillment_certificate_is_sound:
        worlds.intersection_update((World.N, World.F))
    if observations.certified_fulfillment and assumptions.fulfillment_certificate_is_sound:
        worlds.intersection_update((World.S,))
    if not worlds:
        raise InconsistentEvidence("contradictory certified evidence: no admissible history")
    return frozenset(worlds)


@dataclass(frozen=True)
class Bounds:
    guaranteed_provider: int
    maximum_provider: int
    guaranteed_consumer: int
    unresolved: int


def evaluate(sla: SLA, admissible: FrozenSet[World]) -> Bounds:
    """Generic finite-history monetary evaluator; independent from bit masks."""
    if not admissible or not set(admissible).issubset(ALL_WORLDS):
        raise InvalidModel("history set must be nonempty and contain only N/F/S")
    entitlements = tuple(sla.entitlement(world) for world in admissible)
    lower = min(entitlements)
    upper = max(entitlements)
    result = Bounds(lower, upper, sla.fee - upper, upper - lower)
    if result.guaranteed_provider + result.guaranteed_consumer + result.unresolved != sla.fee:
        raise AssertionError("financial conservation failed")
    return result


def world_sound(true_world: World, admissible: FrozenSet[World]) -> bool:
    """Research diagnostic requiring an externally supplied ground-truth world."""
    if not isinstance(true_world, World):
        raise InvalidModel("ground truth must be N/F/S")
    return true_world in admissible


@dataclass(frozen=True)
class ProgressivePosition:
    """Per-epoch previously credited position. Funds credited are not revocable."""

    sla: SLA
    admissible: FrozenSet[World]
    provider_credited: int
    consumer_credited: int
    unresolved: int

    @classmethod
    def initial(cls, sla: SLA) -> "ProgressivePosition":
        b = evaluate(sla, ALL_WORLDS)
        return cls(sla, ALL_WORLDS, b.guaranteed_provider, b.guaranteed_consumer, b.unresolved)

    def refine(self, new_histories: FrozenSet[World]) -> tuple["ProgressivePosition", int, int]:
        if not new_histories or not new_histories.issubset(self.admissible):
            raise EvidenceRetraction("history refinement must be nonempty subset")
        b = evaluate(self.sla, new_histories)
        delta_provider = b.guaranteed_provider - self.provider_credited
        delta_consumer = b.guaranteed_consumer - self.consumer_credited
        if delta_provider < 0 or delta_consumer < 0 or b.unresolved > self.unresolved:
            raise InvalidModel("a credit reversal or exposure increase was attempted")
        next_position = ProgressivePosition(self.sla, new_histories, b.guaranteed_provider,
                                            b.guaranteed_consumer, b.unresolved)
        return next_position, delta_provider, delta_consumer


def admission_permitted(current_exposure: int, maximum_new_exposure: int, budget: int) -> bool:
    """Conservative admission gate: existing exposure plus worst-case increment."""
    for name, value in (("current_exposure", current_exposure),
                        ("maximum_new_exposure", maximum_new_exposure), ("budget", budget)):
        _amount(value, name)
    return current_exposure + maximum_new_exposure <= budget
