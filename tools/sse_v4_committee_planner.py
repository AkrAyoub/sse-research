#!/usr/bin/env python3
"""SSE V4 consumer committee planner (pure, stdlib only, read-only).

SOURCE-ONLY (2026-11-27): written without execution; tests in
tests/test_sse_v4_committee_planner.py are unexecuted.

Given a consumer's requested committee (n primary seats, s ordered standbys,
fault bound b), an observed eligible-monitor count and prices, computes:
  * quorum q = n - floor((n-1)/3) and the checks 2q - n > b, q <= n - b,
    exactly mirroring SSEServiceBoardV4 / AdaptiveMonitorQuorum;
  * the exact price breakdown in integer wei;
  * the exact probability (uniform-hash model) that the on-chain bounded
    rejection sampler of SSEMonitorRegistryV4 finds n+s eligible entries;
  * a conservative hypergeometric risk bound on ALL n+s drawn identities
    (final committee is a subset, so attacker seats there cannot exceed it);
  * alternatives that never silently weaken the fault goal: changes to b are
    only ever listed with weakensFaultGoal=True and requiresExplicitConsent.

Inputs are observations; nothing here proves operator independence.
"""
import argparse
import json
from fractions import Fraction
from math import comb

MAX_SEATS = 64
ATTEMPTS_PER_SEAT = 8   # SSEMonitorRegistryV4.ATTEMPTS_PER_SEAT
MAX_ATTEMPTS = 512      # SSEMonitorRegistryV4.MAX_ATTEMPTS


def quorum(seats):
    if type(seats) is not int or seats < 4:
        raise ValueError("seats must be an integer >= 4")
    return seats - (seats - 1) // 3


def validate(seats, fault_tolerance, standbys):
    for v in (seats, fault_tolerance, standbys):
        if type(v) is not int or v < 0:
            raise ValueError("integer, non-negative committee parameters required")
    errors = []
    if seats < 4:
        errors.append("seats must be >= 4")
    if fault_tolerance < 1:
        errors.append("fault tolerance b must be >= 1")
    if seats < 3 * fault_tolerance + 1:
        errors.append("seats must satisfy n >= 3b + 1")
    if seats + standbys > MAX_SEATS:
        errors.append("n + s must be <= 64")
    if errors:
        return errors
    q = quorum(seats)
    if not (2 * q - seats > fault_tolerance and q <= seats - fault_tolerance):
        errors.append("quorum intersection condition failed")  # unreachable if n >= 3b+1
    return errors


def draw_success_probability(population, eligible, count):
    """Exact P(sampler finds `count` distinct eligible entries) under a uniform
    hash model: each attempt hits a not-yet-picked eligible entry with
    probability (eligible - found) / population."""
    if count == 0:
        return Fraction(1)
    if population < count or eligible < count:
        return Fraction(0)
    attempts = min(count * ATTEMPTS_PER_SEAT, MAX_ATTEMPTS)
    state = [Fraction(0)] * (count + 1)
    state[0] = Fraction(1)
    for _ in range(attempts):
        nxt = [Fraction(0)] * (count + 1)
        nxt[count] = state[count]
        for found in range(count):
            p = state[found]
            if not p:
                continue
            hit = Fraction(eligible - found, population)
            nxt[found + 1] += p * hit
            nxt[found] += p * (1 - hit)
        state = nxt
    return state[count]


def drawn_identity_risk(eligible, adversarial, drawn, fault_tolerance):
    """P(more than b adversarial identities among all n+s drawn identities)."""
    if not 0 <= adversarial <= eligible or drawn > eligible:
        raise ValueError("invalid population")
    total = comb(eligible, drawn)
    exceeded = Fraction(0)
    for i in range(fault_tolerance + 1, min(drawn, adversarial) + 1):
        exceeded += Fraction(comb(adversarial, i) * comb(eligible - adversarial, drawn - i), total)
    return exceeded


def prices(seats, epochs, epoch_fee, per_report_reward):
    service = epoch_fee * epochs
    monitor = seats * epochs * per_report_reward
    return {"serviceWei": service, "monitorReportBudgetWei": monitor,
            "totalFundingWei": service + monitor,
            "standbyRetainerWei": 0,
            "note": "Unpromoted standbys are unpaid in V4 candidate; gas is extra and estimated separately."}


def plan(seats, fault_tolerance, standbys, population, eligible, epochs, epoch_fee,
         per_report_reward, adversarial=None):
    errors = validate(seats, fault_tolerance, standbys)
    if errors:
        return {"valid": False, "errors": errors}
    count = seats + standbys
    success = draw_success_probability(population, eligible, count)
    out = {"valid": True, "seats": seats, "standbys": standbys, "faultTolerance": fault_tolerance,
           "quorum": quorum(seats), "prices": prices(seats, epochs, epoch_fee, per_report_reward),
           "observedPopulation": population, "observedEligible": eligible,
           "feasibleNow": eligible >= count,
           "drawSuccessProbability": success,
           "assumptions": ["uniform seed/hash model; blockhash is proposer-influenceable",
                           "eligibility may change between observation and draw",
                           "addresses are not independent operators"],
           "alternatives": []}
    if adversarial is not None and eligible >= count:
        out["conservativeRiskAllDrawn"] = drawn_identity_risk(eligible, adversarial, count, fault_tolerance)
    if eligible < count:
        out["alternatives"].append({"action": "wait", "needEligible": count, "weakensFaultGoal": False})
        if eligible >= seats:
            out["alternatives"].append({"action": "reduce_standbys", "standbys": eligible - seats,
                "weakensFaultGoal": False, "tradeoff": "fewer replacements for unconfirmed seats"})
        min_seats = 3 * fault_tolerance + 1
        if eligible >= min_seats and seats > min_seats:
            n2 = min(seats, eligible)
            out["alternatives"].append({"action": "reduce_seats_same_b", "seats": n2, "standbys": 0,
                "quorum": quorum(n2), "weakensFaultGoal": False,
                "tradeoff": "smaller committee with the same fault bound b"})
        if eligible >= 4 and eligible < min_seats:
            b2 = (eligible - 1) // 3
            out["alternatives"].append({"action": "lower_fault_tolerance", "faultTolerance": b2,
                "seats": eligible, "weakensFaultGoal": True, "requiresExplicitConsent": True})
    return out


def _render(v):
    if isinstance(v, Fraction):
        return {"numerator": v.numerator, "denominator": v.denominator, "probability": float(v)}
    if isinstance(v, dict):
        return {k: _render(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_render(x) for x in v]
    return v


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("seats", "fault-tolerance", "standbys", "population", "eligible", "epochs",
                 "epoch-fee", "per-report-reward"):
        p.add_argument("--" + name, type=int, required=True)
    p.add_argument("--adversarial", type=int)
    a = p.parse_args()
    print(json.dumps({"schema": "SSE_V4_COMMITTEE_PLAN_V1", "observedNetworkRisk": False,
        "operatorIndependenceProved": False,
        "result": _render(plan(a.seats, a.fault_tolerance, a.standbys, a.population, a.eligible,
            a.epochs, a.epoch_fee, a.per_report_reward, a.adversarial))}, indent=2))


if __name__ == "__main__":
    main()
