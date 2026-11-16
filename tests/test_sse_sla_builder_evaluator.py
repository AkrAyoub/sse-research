"""R1/R7 versioned marketplace manifest builder and bounded SLA measurements."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_sla_build as builder
from sse_sla_manifest import proposed_policy, policy_hash
from sse_resource_profile_v2 import resource_hash, compare_policy
from sse_sla_evaluator import evaluate, SLAEvaluationError

CHAIN=31337
SETTLEMENT="0x"+"12"*20
PROFILE="0x"+"ab"*32
MONITOR="0x"+"ba"*20
POLICY=proposed_policy(service_kind="http_challenge",chain_id=CHAIN,
                       settlement=SETTLEMENT,resource_profile_hash=PROFILE,
                       max_response_latency_ms=500,
                       min_probe_count=3,min_success_bps=9000)


def sample(i,*,correct=True,ms=90,timeout=False):
    return {"monitor":MONITOR,"probeId":i,
            "kind":"LOCAL_TIMEOUT" if timeout else "RESULT_OBSERVED",
            "resultCorrect":None if timeout else correct,
            "elapsedMs":None if timeout else ms,"signatureVerified":True}


class SLABuilderTests(unittest.TestCase):
    def test_builds_marketplace_ready_hashes_without_chain_io(self):
        with tempfile.TemporaryDirectory() as td:
            args=["--service-kind","http_challenge",
                  "--endpoint","https://provider.demo.ts.net",
                  "--chain-id",str(CHAIN),"--settlement",SETTLEMENT,
                  "--output-dir",td]
            output=StringIO()
            with redirect_stdout(output):
                self.assertEqual(builder.main(args),0)
            data=json.loads(output.getvalue())
            self.assertEqual(data["onChainAction"],"OpenResourceBoard.requestResource")
            self.assertFalse(data["submittedToBlockchain"])
            profile=json.loads((Path(td)/"sse-resource-profile.json").read_text())
            policy=json.loads((Path(td)/"sse-sla-policy.json").read_text())
            self.assertEqual(data["resourceProfileHash"],resource_hash(profile))
            self.assertEqual(data["slaPolicyHash"],policy_hash(policy))
            self.assertTrue(compare_policy(profile,policy))
            with redirect_stdout(StringIO()):
                self.assertEqual(builder.main(args),1)

    def test_compute_builder_requires_image_digest(self):
        with tempfile.TemporaryDirectory() as td:
            with redirect_stdout(StringIO()):
                self.assertEqual(builder.main([
                  "--service-kind","deterministic_compute",
                  "--endpoint","https://provider.demo.ts.net",
                  "--chain-id",str(CHAIN),"--settlement",SETTLEMENT,
                  "--output-dir",td]),1)
            self.assertFalse((Path(td)/"sse-resource-profile.json").exists())


class EvaluationTests(unittest.TestCase):
    def test_full_observed_sample_has_conditional_pass(self):
        report=evaluate(POLICY,[sample(1),sample(2,ms=100),sample(3,ms=110)])
        self.assertEqual(report["provisionalAssessment"],"OBSERVED_PASS_CONDITIONAL")
        self.assertEqual(report["observedSuccessBps"],10000)
        self.assertEqual(report["observedP95LatencyMs"],110)
        self.assertFalse(report["consumerPhysicalDeliveryVerified"])
        self.assertFalse(report["suitableForOnChainSlaFailureVote"])

    def test_timeout_not_conclusive_failure(self):
        report=evaluate(POLICY,[sample(1),sample(2,timeout=True),sample(3,timeout=True)])
        self.assertEqual(report["localTimeouts"],2)
        self.assertEqual(report["observedSuccessBps"],10000)
        self.assertFalse(report["timeoutsAreSlaFailures"])
        self.assertFalse(report["independentWitnessesVerified"])
        self.assertFalse(report["suitableForOnChainSlaFailureVote"])

    def test_incorrect_or_slow_results_are_provisional_deviation(self):
        report=evaluate(POLICY,[sample(1),sample(2,ms=900),sample(3,correct=False)])
        self.assertEqual(report["incorrectOrSlowResults"],2)
        self.assertEqual(report["provisionalAssessment"],"OBSERVED_DEVIATION_CONDITIONAL")
        self.assertEqual(report["observedP95LatencyMs"],900)
        self.assertFalse(report["suitableForOnChainSlaFailureVote"])

    def test_only_timeouts_insufficient_eligible_results(self):
        report=evaluate(POLICY,[sample(1,timeout=True),sample(2,timeout=True),sample(3,timeout=True)])
        self.assertEqual(report["provisionalAssessment"],"INSUFFICIENT_OBSERVATIONS")
        self.assertIsNone(report["observedSuccessBps"])

    def test_signatures_and_dedup_required(self):
        wrong=sample(1);wrong["signatureVerified"]=False
        with self.assertRaises(SLAEvaluationError):
            evaluate(POLICY,[wrong])
        with self.assertRaises(SLAEvaluationError):
            evaluate(POLICY,[sample(1),sample(1)])
        invalid=sample(1,timeout=True);invalid["resultCorrect"]=False
        with self.assertRaises(SLAEvaluationError):
            evaluate(POLICY,[invalid])

    def test_no_samples_gives_insufficient(self):
        report=evaluate(POLICY,[])
        self.assertEqual(report["provisionalAssessment"],"INSUFFICIENT_OBSERVATIONS")
        self.assertFalse(report["minimumSamplesReached"])


if __name__=="__main__":
    unittest.main()
