"""Explain *conditional* SSE on-chain bounds from a pinned chain inspection.

Do not confuse monitor votes or on-chain flags with verified physical delivery.
This module reconstructs the N/F/S history mask and min/max entitlement
specified in SSESettlement.sol. It never sends a transaction.
"""
from __future__ import annotations


class SettlementExplainError(ValueError):
    pass


def explain_inspection(inspection: dict) -> dict:
    if type(inspection) is not dict or inspection.get("schema") != "sse-onchain-inspection-v1":
        raise SettlementExplainError("expected SSE on-chain inspector result")
    lease, epoch = inspection.get("lease"), inspection.get("epoch")
    if type(lease) is not dict:
        raise SettlementExplainError("lease state unavailable")
    if epoch is None:
        return {
            "kind": "SSE_SETTLEMENT_EXPLANATION",
            "epochAdmitted": False,
            "status": "NO_EPOCH",
            "physicalTruthVerified": False,
            "monitorIndependenceVerified": False,
            "readOnly": True,
        }
    if type(epoch) is not dict:
        raise SettlementExplainError("invalid epoch state")

    fee, reservation = epoch.get("fee"), epoch.get("reservationFee")
    ack = epoch.get("acknowledged")
    sealed = epoch.get("monitoringSealed")
    outcome = epoch.get("outcome")
    if (type(fee) is not int or type(reservation) is not int or
            not 0 <= reservation <= fee or fee == 0 or
            type(ack) is not bool or type(sealed) is not bool or
            type(outcome) is not int or outcome not in (0, 1, 2)):
        raise SettlementExplainError("invalid epoch settlement inputs")
    # Model precisely follows SSESettlement's HISTORY_N/F/S intersections.
    histories = {"N", "F", "S"}
    evidence = []
    if ack:
        histories &= {"F", "S"}
        evidence.append("On-chain provider acknowledgment narrows N away")
    if sealed and outcome == 1:
        histories &= {"S"}
        evidence.append("Sealed success quorum narrows admissible set to S")
    elif sealed and outcome == 2:
        histories &= {"N", "F"}
        evidence.append("Sealed failure quorum excludes S but may leave N/F")
    elif not sealed:
        evidence.append("Monitoring not sealed; payout is only a projection")
    if not histories:
        raise SettlementExplainError("mutually inconsistent on-chain evidence flags")
    payouts = {"N": reservation, "F": 0, "S": fee}
    lower = min(payouts[h] for h in histories)
    upper = max(payouts[h] for h in histories)
    expected_consumer = fee - upper
    unresolved = upper - lower
    credited_provider = epoch.get("providerCredited")
    credited_consumer = epoch.get("consumerCredited")
    exposure_on_chain = epoch.get("unresolvedExposure")
    if any(type(x) is not int or x < 0 for x in (
            credited_provider, credited_consumer, exposure_on_chain)):
        raise SettlementExplainError("invalid credited balances in epoch")
    accounting_matches = (
        credited_provider == lower and
        credited_consumer == expected_consumer and
        exposure_on_chain == unresolved
    )
    return {
        "kind": "SSE_SETTLEMENT_EXPLANATION",
        "leaseId": inspection.get("leaseId"),
        "epochId": inspection.get("epochId"),
        "epochAdmitted": True,
        "monitoringSealed": sealed,
        "sealedOutcome": {0: "None", 1: "Success", 2: "Failure"}[outcome],
        "successVotes": epoch.get("successVotes"),
        "failureVotes": epoch.get("failureVotes"),
        "providerAcknowledged": ack,
        "admissibleHistories": [h for h in ("N", "F", "S") if h in histories],
        "historyProviderEntitlementsWei": {h: payouts[h] for h in ("N", "F", "S")},
        "providerLowerBoundWei": lower,
        "providerUpperBoundWei": upper,
        "consumerRefundLowerBoundWei": expected_consumer,
        "unresolvedExposureWei": unresolved,
        "creditedOnChainWei": {"provider": credited_provider,
                               "consumer": credited_consumer},
        "remainingUnresolvedOnChainWei": exposure_on_chain,
        "onChainCreditsMatchCurrentBounds": accounting_matches,
        "settlementExecutedNotProvenByBoundsAlone": True,
        "derivation": evidence,
        "interpretation": (
            "Conditional on observed contract state and monitor evidence "
            "qualification; physical delivery and operator independence "
            "are not established by a vote count"
        ),
        "chainFinalityVerified": False,
        "physicalTruthVerified": False,
        "monitorIndependenceVerified": False,
        "readOnly": True,
    }
