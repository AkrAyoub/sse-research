"""R233 public HTTPS V2 manifest: source-only funding/deadline policy tests."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r233_public_v2_compute_terms as m

MARKET="0x"+"11"*20
IMAGE="sha256:"+"cc"*32
PROFILE={
    "schema":m.RESOURCE_SCHEMA,
    "serviceKind":"deterministic_compute",
    "workloadSpec":m.WORKLOAD,
    "origin":"https://provider.example.org",
    "dockerImageId":IMAGE,
    "cpuMilli":1500,"memoryBytes":256*2**20,
}
POLICY={
    "schema":m.POLICY_SCHEMA,"chainId":31340,"market":MARKET,
    "resourceProfileHash":None,
    "measuredFinalitySafetySeconds":2100,
    "confirmationSeconds":3600,"responseSeconds":3600,
    "monitoringSeconds":3600,"maxObservedLatencyMs":1000,
    "probeIntervalMs":2000,"minProbeCount":8,"minCorrectBps":9900,
    "timeoutTreatment":m.TIMEOUT,
}
POLICY["resourceProfileHash"]=m.resource_hash(PROFILE)

class TestR233PublicV2ComputeTerms(unittest.TestCase):
    def test_public_dns_profile_hash_deterministic(self):
        self.assertRegex(m.resource_hash(PROFILE),r"^0x[0-9a-f]{64}$")
        self.assertEqual(m.resource_hash(dict(reversed(list(PROFILE.items())))),
                         m.resource_hash(PROFILE))
        self.assertRegex(m.policy_hash(POLICY,PROFILE),r"^0x[0-9a-f]{64}$")

    def test_measured_finality_safety_required_not_random_short_timeout(self):
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"responseSeconds":100},PROFILE)
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"confirmationSeconds":2000},PROFILE)
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"monitoringSeconds":1},PROFILE)

    def test_economic_terms_budget_matches_four_seats_two_epochs(self):
        p=m.plan(PROFILE,POLICY,epochs=2,seats=4,faults=1,reward=1000)
        t=p["fundingTermsProposal"]
        self.assertEqual(t["monitorBudgetWei"],8_000)
        self.assertEqual(t["gasBoundSeats"],4)
        self.assertEqual(t["responseSeconds"],3600)
        self.assertRegex(t["endpointHash"],r"^0x[0-9a-f]{64}$")
        self.assertFalse(p["physicalResourcesMeasured"])
        self.assertFalse(p["nativeTestEthReceived"])
        self.assertFalse(p["actualEligibleIndependentMonitorsVerified"])

    def test_many_possible_monitors_not_global_cap(self):
        t=m.funding_terms(PROFILE,POLICY,epochs=1,
                          expected_seats=7,fault_tolerance=2,
                          reward_per_seat_epoch_wei=123)
        self.assertEqual(t["monitorBudgetWei"],861)
        self.assertEqual(t["requiredFaultTolerance"],2)
        with self.assertRaises(m.Refused):
            m.funding_terms(PROFILE,POLICY,epochs=1,
                            expected_seats=6,fault_tolerance=2,
                            reward_per_seat_epoch_wei=123)

    def test_reject_tailscale_only_legacy_and_remote_insecure_http(self):
        with self.assertRaises(m.Refused):
            m.validate_profile({**PROFILE,"origin":"http://provider.example.org"})
        with self.assertRaises(m.Refused):
            m.validate_profile({**PROFILE,"origin":"https://evil.example.org/path"})
        with self.assertRaises(m.Refused):
            m.validate_profile({**PROFILE,"dockerImageId":"ubuntu:latest"})

    def test_hash_tampering_fails_closed(self):
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"resourceProfileHash":"0x"+"ff"*32},PROFILE)
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"chainId":1},PROFILE)
        with self.assertRaises(m.Refused):
            m.validate_profile({**PROFILE,"extra":"yes"})

    def test_timeout_never_classified_failure_from_http_error(self):
        self.assertEqual(m.validate_policy(POLICY,PROFILE)["timeoutTreatment"],
                         "INCONCLUSIVE_UNLESS_INDEPENDENTLY_ESTABLISHED")
        with self.assertRaises(m.Refused):
            m.validate_policy({**POLICY,"timeoutTreatment":"AUTO_FAILURE"},PROFILE)

    def test_bool_or_overflow_eth_funding_refused(self):
        with self.assertRaises(m.Refused):
            m.funding_terms(PROFILE,POLICY,epochs=True,expected_seats=4,
                            fault_tolerance=1,reward_per_seat_epoch_wei=100)
        with self.assertRaises(m.Refused):
            m.funding_terms(PROFILE,POLICY,epochs=2,expected_seats=4,
                            fault_tolerance=1,reward_per_seat_epoch_wei=0)

if __name__=="__main__":
    unittest.main()
