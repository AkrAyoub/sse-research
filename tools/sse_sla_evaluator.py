#!/usr/bin/env python3
"""Conservative provisional SLA sample summary for HTTP/compute observations.

Metrics can describe *reported* HTTP correctness and latency; report signatures
and endpoint scope must be verified separately. This is NOT an oracle proving
physical delivery, network independence, or permitting SSESettlement payout.
An observed timeout NEVER becomes a final SLA failure verdict.
"""
from __future__ import annotations

import math
import re

from sse_sla_manifest import validate_policy

ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
KIND = frozenset(("RESULT_OBSERVED", "LOCAL_TIMEOUT"))
FIELDS = frozenset(("monitor", "probeId", "kind", "resultCorrect", "elapsedMs",
                    "signatureVerified"))


class SLAEvaluationError(ValueError):
    pass


def evaluate(policy, samples):
    validate_policy(policy)
    if type(samples) is not list or len(samples) > 10000:
        raise SLAEvaluationError("bounded signed sample list required")
    seen = set()
    values = []
    timeout_count = 0
    correct_count = 0
    incorrect_count = 0
    verified_sample_count = 0
    distinct = set()
    for row in samples:
        if type(row) is not dict or set(row) != FIELDS:
            raise SLAEvaluationError("invalid sample schema")
        monitor, probe = row["monitor"], row["probeId"]
        if (type(monitor) is not str or not ADDR.fullmatch(monitor) or
                type(probe) is not int or not 0 <= probe < 2**64 or
                (monitor.lower(), probe) in seen):
            raise SLAEvaluationError("invalid or duplicated sample scope")
        seen.add((monitor.lower(), probe))
        distinct.add(monitor.lower())
        kind = row["kind"]
        if type(kind) is not str or kind not in KIND or type(row["signatureVerified"]) is not bool:
            raise SLAEvaluationError("invalid sample kind/attribution")
        if not row["signatureVerified"]:
            raise SLAEvaluationError("unattributed sample cannot be aggregated")
        verified_sample_count += 1
        if kind == "LOCAL_TIMEOUT":
            if row["resultCorrect"] is not None or row["elapsedMs"] is not None:
                raise SLAEvaluationError("timeout cannot assert a result or duration")
            timeout_count += 1
            continue
        if (type(row["resultCorrect"]) is not bool or type(row["elapsedMs"]) is not int
                or not 0 <= row["elapsedMs"] <= 3600_000):
            raise SLAEvaluationError("result observation must carry bounded latency and correctness")
        values.append(row["elapsedMs"])
        if row["resultCorrect"] and row["elapsedMs"] <= policy["maxResponseLatencyMs"]:
            correct_count += 1
        else:
            incorrect_count += 1
    ordered = sorted(values)
    p95 = ordered[min(len(ordered)-1, math.ceil(len(ordered)*0.95)-1)] if ordered else None
    # A timeout is an unknown physical outcome rather than proven failure.
    denominator = len(values)
    observed_bps = (correct_count * 10000 // denominator) if denominator else None
    enough = len(samples) >= policy["minProbeCount"]
    if not enough or not denominator:
        provisional = "INSUFFICIENT_OBSERVATIONS"
    elif timeout_count:
        # Positive observed replies do not erase the unknown outcomes of
        # unreachable witnesses; no overall compliance claim is justified.
        provisional = "PARTIAL_VISIBILITY_INCONCLUSIVE"
    elif observed_bps >= policy["minSuccessBps"] and p95 <= policy["maxResponseLatencyMs"]:
        provisional = "OBSERVED_PASS_CONDITIONAL"
    else:
        provisional = "OBSERVED_DEVIATION_CONDITIONAL"
    return {
        "kind": "SSE_SLA_OBSERVATION_SUMMARY_V1",
        "serviceKind": policy["serviceKind"],
        "reportedSamples": verified_sample_count,
        "distinctReportingSigners": len(distinct),
        "correctTimelyResults": correct_count,
        "incorrectOrSlowResults": incorrect_count,
        "localTimeouts": timeout_count,
        "observedResults": denominator,
        "observedSuccessBps": observed_bps,
        "observedP95LatencyMs": p95,
        "minimumSamplesReached": enough,
        "provisionalAssessment": provisional,
        "timeoutsAreSlaFailures": False,
        "independentWitnessesVerified": False,
        "consumerPhysicalDeliveryVerified": False,
        "suitableForOnChainSlaFailureVote": False,
    }
