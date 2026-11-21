"""R43: actual read-only chain31340 proof must never be synthetic."""
import hashlib
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_g2_postlaunch_r43 as r43
from sse_pos_deposit_predeploy import standard_reference

class R43GenuineNativeLivenessTests(unittest.TestCase):
    def test_pinned_reference_is_actual_unmodified_ethereum_runtime(self):
        code = standard_reference()["code"]
        evidence = r43.code_evidence(code, code)
        self.assertTrue(evidence["liveCodeByteForByteMatchesPinnedStandardDepositRuntime"])
        self.assertTrue(evidence["originalR42ConstantMatchesActualPinnedReference"])
        self.assertEqual(evidence["executionRpcDepositCodeBytes"], 6358)

    def test_empty_code_never_passes(self):
        code = standard_reference()["code"]
        result = r43.code_evidence("0x", code)
        self.assertEqual(result["executionRpcDepositCodeStatus"], "RPC_EMPTY_CODE")
        self.assertFalse(result["liveCodeByteForByteMatchesPinnedStandardDepositRuntime"])

    def test_missing_or_malformed_evm_code_never_passes(self):
        code = standard_reference()["code"]
        for candidate in (None, "", "zzz", "0xGG", "0x1"):
            r = r43.code_evidence(candidate, code)
            self.assertFalse(r["liveCodeByteForByteMatchesPinnedStandardDepositRuntime"])

    def test_code_exposure_is_public_hash_only(self):
        code = standard_reference()["code"]
        report = r43.code_evidence(code, code)
        self.assertNotIn(code, str(report))
        self.assertTrue(report["rawCodeNotEmitted"])

    def test_progress_only_if_actual_height_increases(self):
        a = {"elBlockHeightObserved": 0, "beaconHeadSlotObserved": 0,
             "beaconFinalizedEpochObserved": 0}
        b = {"elBlockHeightObserved": 0, "beaconHeadSlotObserved": 0,
             "beaconFinalizedEpochObserved": 0}
        result = r43.progression(a, b)
        for k in ("executionBlockHeightIncreasedBetweenRealSamples",
                  "beaconHeadSlotIncreasedBetweenRealSamples",
                  "beaconFinalizedEpochIncreasedBetweenRealSamples",
                  "positiveExecutionBlockHeightObserved",
                  "positiveRealBeaconFinalityObserved"):
            self.assertFalse(result[k])

    def test_nonzero_real_height_and_epoch_prove_progress_only_with_chain_identity(self):
        a = {"elBlockHeightObserved": 0, "beaconHeadSlotObserved": 0,
             "beaconFinalizedEpochObserved": 0}
        b = {"elBlockHeightObserved": 2, "beaconHeadSlotObserved": 15,
             "beaconFinalizedEpochObserved": 1,
             "elChain31340VerifiedInsideDocker": True,
             "realPositiveBeaconFinalityObserved": True}
        result = r43.progression(a, b)
        self.assertTrue(result["executionBlockHeightIncreasedBetweenRealSamples"])
        self.assertTrue(result["beaconHeadSlotIncreasedBetweenRealSamples"])
        self.assertTrue(result["beaconFinalizedEpochIncreasedBetweenRealSamples"])
        self.assertTrue(result["positiveExecutionBlockHeightObserved"])
        self.assertTrue(result["positiveRealBeaconFinalityObserved"])

    def test_only_local_public_nonsecret_operations(self):
        src = (ROOT / "tools/sse_pos_g2_postlaunch_r43.py").read_text("utf-8")
        for forbidden in ('"start"', '"restart"', '"run"', '"stop"', '"kill"', '"rm"', "mnemonic"):
            self.assertNotIn(forbidden, src)
        self.assertIn('health.rpc("eth_getCode"', src)
        self.assertIn("health.observe(args.expected_commit)", src)
        self.assertIn("health.require_actual_source(args.expected_commit)", src)

if __name__ == "__main__":
    unittest.main()
