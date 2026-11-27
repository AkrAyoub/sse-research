"""R349 conservative aggregate evaluation regression tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from sse_pos_r349_v2_monitor_sample_session import evaluate

class TestR349Aggregate(unittest.TestCase):
    def setUp(self):
        self.policy={"minProbeCount":10,"maxObservedLatencyMs":5000}
        self.rh="0x"+"ab"*32
        self.rows=[{"providerSignatureVerified":True,"signedResponseHash":self.rh,
                    "elapsedMs":5000} for _ in range(10)]

    def check(self,rows,expected):
        result=evaluate(rows,self.policy,self.rh)
        self.assertEqual(result["conditionalSampleOutcome"],expected)
        self.assertFalse(result["automaticVoteAuthorized"])
        self.assertFalse(result["physicalSlaTruthVerified"])

    def test_exact_minimum_and_latency_boundary(self):
        self.check(self.rows,"SUPPORTED_SAMPLE_SUCCESS")

    def test_insufficient_samples(self):
        self.check(self.rows[:9],"INCONCLUSIVE")

    def test_empty(self):
        self.check([],"INCONCLUSIVE")

    def test_timeout(self):
        self.rows[0]={"transportStatus":"UNAVAILABLE_OR_ERROR","elapsedMs":6000}
        self.check(self.rows,"INCONCLUSIVE")

    def test_wrong_response_commitment(self):
        self.rows[0]["signedResponseHash"]="0x"+"cd"*32
        self.check(self.rows,"INCONCLUSIVE")

    def test_slow_authenticated_response(self):
        self.rows[0]["elapsedMs"]=5001
        self.check(self.rows,"INCONCLUSIVE")

    def test_bad_signature(self):
        self.rows[0]["providerSignatureVerified"]=False
        self.check(self.rows,"INCONCLUSIVE")

    def test_invalid_latency(self):
        for invalid in (-1,True,None,1.5):
            with self.subTest(invalid=invalid):
                self.rows[0]["elapsedMs"]=invalid
                self.check(self.rows,"INCONCLUSIVE")

if __name__=="__main__":
    unittest.main()
