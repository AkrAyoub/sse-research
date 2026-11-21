#!/usr/bin/env python3
"""R43: compare actual postlaunch PoS progress over real time and real EVM code.

Read-only, no client restarts, validator operations, signatures, genesis
generation or network ports. Only original pinned chain31340 Docker-internal
RPC and the public R33 standard Ethereum deposit bytecode are inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import sys

import sse_pos_g2_internal_health_r42 as health
from sse_pos_deposit_predeploy import standard_reference, DepositPredeployError

MIN_INTERVAL = 12
MAX_INTERVAL = 36
DEPOSIT = health.DEPOSIT


def code_evidence(value: object, reference: str) -> dict:
    """Report public code hashes/lengths ONLY; never print code or raw RPC."""
    if not isinstance(reference, str) or not reference.startswith("0x"):
        raise ValueError("pinned public deposit reference absent")
    expected_bytes = bytes.fromhex(reference[2:])
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    if not isinstance(value, str):
        actual_status, actual_bytes = "RPC_NO_RESULT", None
    elif value == "0x":
        actual_status, actual_bytes = "RPC_EMPTY_CODE", b""
    elif not value.startswith("0x") or len(value) > 130000:
        actual_status, actual_bytes = "RPC_UNEXPECTED_FORMAT", None
    else:
        try:
            actual_bytes = bytes.fromhex(value[2:])
            actual_status = "RPC_CODE_RETURNED"
        except ValueError:
            actual_status, actual_bytes = "RPC_INVALID_HEX", None
    return {
        "pinnedPublicDepositRuntimeSha256": expected_hash,
        "originalR42ConstantMatchesActualPinnedReference": expected_hash == health.CODE_SHA,
        "expectedStandardDepositRuntimeBytes": len(expected_bytes),
        "executionRpcDepositCodeStatus": actual_status,
        "executionRpcDepositCodeBytes": len(actual_bytes) if actual_bytes is not None else None,
        "executionRpcDepositCodeSha256": hashlib.sha256(actual_bytes).hexdigest() if actual_bytes is not None else None,
        "liveCodeByteForByteMatchesPinnedStandardDepositRuntime": actual_bytes == expected_bytes
            if actual_bytes is not None else False,
        "rawCodeNotEmitted": True,
    }


def sample(commit: str, code: str) -> dict:
    observation = health.observe(commit)
    evidence = code_evidence(code, standard_reference()["code"])
    observation.update(evidence)
    return observation


def progression(first: dict, second: dict) -> dict:
    fh = first.get("elBlockHeightObserved")
    sh = second.get("elBlockHeightObserved")
    fs = first.get("beaconHeadSlotObserved")
    ss = second.get("beaconHeadSlotObserved")
    fe = first.get("beaconFinalizedEpochObserved")
    se = second.get("beaconFinalizedEpochObserved")
    def gain(before, after):
        return type(before) is int and type(after) is int and after > before
    return {
        "executionBlockHeightIncreasedBetweenRealSamples": gain(fh, sh),
        "beaconHeadSlotIncreasedBetweenRealSamples": gain(fs, ss),
        "beaconFinalizedEpochIncreasedBetweenRealSamples": gain(fe, se),
        "positiveExecutionBlockHeightObserved": (type(sh) is int and sh > 0 and second.get("elChain31340VerifiedInsideDocker") is True),
        "positiveRealBeaconFinalityObserved": second.get("realPositiveBeaconFinalityObserved") is True,
        "sameOriginalValidatorAndBeaconRunning": second.get("beaconAndOriginalVCBothRunning") is True,
        "noSyntheticProgressClaims": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe actual public-code and native PoS liveness without starting services")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--interval-seconds", type=int, default=12)
    args = parser.parse_args()
    if not MIN_INTERVAL <= args.interval_seconds <= MAX_INTERVAL:
        print("R43_OBSERVER_REFUSED: interval must be 12..36 seconds", file=sys.stderr)
        return 2
    try:
        health.require_actual_source(args.expected_commit)
        expected = standard_reference()["code"]
        observations = []
        for i in range(2):
            before = health.observe(args.expected_commit)
            # Use actual RPC output, never synthetic or hardcoded results.
            if before.get("elChain31340VerifiedInsideDocker") is True:
                runtime = health.rpc("eth_getCode", [DEPOSIT, "latest"])
            else:
                runtime = None
            before.update(code_evidence(runtime, expected))
            observations.append(before)
            print(json.dumps({"sample": i + 1, "readOnly": True, "observed": before}, sort_keys=True, indent=2), flush=True)
            if i == 0:
                time.sleep(args.interval_seconds)
        print(json.dumps({
            "schema": "SSE_R43_CHAIN31340_G2_TWO_REAL_OBSERVATION_LIVENESS_V1",
            "betweenSampleIntervalSeconds": args.interval_seconds,
            "comparison": progression(*observations),
            "signedBlsMessagesCryptographicallyVerified": False,
            "independentPublicP2PVerified": False,
            "containersOrKeyMaterialChangedByObserver": False,
        }, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, health.old.RecoveryRefused,
            health.internal.Refuse, DepositPredeployError) as exc:
        # Absolutely never include raw RPC or arbitrary exception text.
        print("R43_OBSERVER_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
