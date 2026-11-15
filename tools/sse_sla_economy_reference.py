"""R1/R2 *research-only* SLA economy reference: not on-chain payment authority.

Consumes externally selected admissible N/F/S histories; DOES NOT qualify
evidence, authenticate a remote service or prove truth. A future, separate
provider-collateral mechanism is modeled hypothetically, not implemented in
SSESettlement. No test-ETH economic incentive is assumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from sse_formal_reference import SLA, World, evaluate


class EconomyDraftError(ValueError):
    """Invalid proposed funding or penalty parameters."""


def _amount(value: int, name: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise EconomyDraftError(f"{name} must be an integer >= {1 if positive else 0}")


@dataclass(frozen=True)
class HypotheticalProviderCollateral:
    """Separate from SSE native service escrow and monitor security bonds.

    Failure penalty is payable ONLY in a world-sound, contractually qualified
    F history (not from an unqualified quorum or monitor timeout). This is
    a proposed policy for testing; no contract currently enforces it.
    """

    deposit_wei: int = 0
    penalty_on_proven_f_wei: int = 0

    def __post_init__(self) -> None:
        _amount(self.deposit_wei, "deposit_wei")
        _amount(self.penalty_on_proven_f_wei, "penalty_on_proven_f_wei")
        if self.penalty_on_proven_f_wei > self.deposit_wei:
            raise EconomyDraftError("failure penalty cannot exceed prefunded collateral")

    def penalty(self, history: World) -> int:
        if not isinstance(history, World):
            raise EconomyDraftError("invalid history")
        return self.penalty_on_proven_f_wei if history is World.F else 0


@dataclass(frozen=True)
class DraftAllocation:
    """Independent accounting pots; no amount is minted or double counted."""

    service_provider_wei: int
    service_consumer_wei: int
    service_held_wei: int
    collateral_consumer_wei: int
    collateral_provider_wei: int
    collateral_held_wei: int

    def conserves(self, fee: int, collateral: int) -> bool:
        return (
            self.service_provider_wei + self.service_consumer_wei
            + self.service_held_wei == fee
            and self.collateral_consumer_wei + self.collateral_provider_wei
            + self.collateral_held_wei == collateral
        )


def allocate(
    terms: SLA,
    histories: FrozenSet[World],
    collateral: HypotheticalProviderCollateral = HypotheticalProviderCollateral(),
) -> DraftAllocation:
    """Monotone guaranteed release conditional on histories being world-sound.

    The generic SSE service pot uses N -> reservation, F -> 0, S -> fee.
    A *separate* collateral pot uses N/S -> 0 penalty, F -> configured
    penalty. Guaranteed penalty = min across worlds; refundable collateral
    = deposit - max penalty; difference remains held pending resolution.
    """
    if not isinstance(terms, SLA) or not isinstance(collateral, HypotheticalProviderCollateral):
        raise EconomyDraftError("invalid terms")
    if type(histories) is not frozenset or not histories or any(
        not isinstance(h, World) for h in histories
    ):
        raise EconomyDraftError("require nonempty frozen set of N/F/S histories")
    service = evaluate(terms, histories)
    penalties = tuple(collateral.penalty(h) for h in histories)
    low, high = min(penalties), max(penalties)
    result = DraftAllocation(
        service.guaranteed_provider,
        service.guaranteed_consumer,
        service.unresolved,
        low,
        collateral.deposit_wei - high,
        high - low,
    )
    if not result.conserves(terms.fee, collateral.deposit_wei):
        raise AssertionError("fund conservation broken")
    return result


@dataclass(frozen=True)
class FundingPlan:
    """Prepaid consumer costs and off-chain gas estimate, NOT provider bond."""

    service_escrow_wei: int
    monitor_reward_budget_wei: int
    executor_reward_budget_wei: int
    vrf_prepayment_wei: int
    consumer_funding_wei: int
    estimated_consumer_gas_wei: int
    estimated_total_consumer_outlay_wei: int


def funding_plan(
    *,
    epoch_fee_wei: int,
    max_epochs: int,
    committee_size: int,
    monitor_reward_per_report_wei: int = 0,
    seal_bounty_wei: int = 0,
    settlement_bounty_wei: int = 0,
    evidence_close_bounty_wei: int = 0,
    release_bounty_wei: int = 0,
    vrf_fee_wei: int = 0,
    estimated_consumer_gas_wei: int = 0,
) -> FundingPlan:
    """Mirror existing service/reward deposit formulas, with estimated gas.

    VRF prepayment is optional; its lifecycle has separate one-time and
    quota rules in SSESettlement. This computes amounts, not policy eligibility.
    Actual gas and real coordinator charges are NOT derived from this formula.
    """
    values = {
        "epoch_fee_wei": epoch_fee_wei,
        "max_epochs": max_epochs,
        "committee_size": committee_size,
        "monitor_reward_per_report_wei": monitor_reward_per_report_wei,
        "seal_bounty_wei": seal_bounty_wei,
        "settlement_bounty_wei": settlement_bounty_wei,
        "evidence_close_bounty_wei": evidence_close_bounty_wei,
        "release_bounty_wei": release_bounty_wei,
        "vrf_fee_wei": vrf_fee_wei,
        "estimated_consumer_gas_wei": estimated_consumer_gas_wei,
    }
    for name, value in values.items():
        _amount(value, name, positive=name in (
            "epoch_fee_wei", "max_epochs", "committee_size"
        ))
    service = epoch_fee_wei * max_epochs
    monitor = max_epochs * committee_size * monitor_reward_per_report_wei
    executor = max_epochs * (
        seal_bounty_wei + settlement_bounty_wei + evidence_close_bounty_wei
    ) + release_bounty_wei
    prepaid = service + monitor + executor + vrf_fee_wei
    return FundingPlan(
        service,
        monitor,
        executor,
        vrf_fee_wei,
        prepaid,
        estimated_consumer_gas_wei,
        prepaid + estimated_consumer_gas_wei,
    )
