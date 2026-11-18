"""R10 research validation: full predeclared strata and no fictitious measurements."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_r10_observation_campaign import (
    CampaignError, POLICIES, WORLDS, allocation, policy_allocation,
    trial_rows, summarize, wilson95, run,
)

REV="a"*40

class EpistemicCampaignTests(unittest.TestCase):
    def test_guaranteed_bounds_conserve_fee_all_world_subsets(self):
        from itertools import combinations
        for size in (1,2,3):
            for subset in combinations(WORLDS,size):
                p,c,h=allocation(set(subset),25,5)
                self.assertEqual(p+c+h,25)
                ent={"N":5,"F":0,"S":25}
                for world in subset:
                    self.assertLessEqual(p,ent[world])
                    self.assertLessEqual(c,25-ent[world])
        self.assertEqual(allocation(set(WORLDS),25,5),(0,0,25))
        self.assertEqual(allocation({"N","F"},25,5),(0,20,5))
        self.assertEqual(allocation({"F"},25,5),(0,25,0))
        self.assertEqual(allocation({"S"},25,5),(25,0,0))

    def test_counterexample_response_not_delivery(self):
        data={
          "world":"F","observedSuccessVotes":3,
          "observedFailureVotes":0,"signedResponseVisible":True,
          "untrustedAckClaim":False,"hypotheticalVerifiedOutcome":"",
        }
        self.assertEqual(policy_allocation(data,"observed_quorum",25,5),(25,0,0))
        self.assertEqual(policy_allocation(data,"ambiguity_hold",25,5),(0,0,25))
        # When the hypothetical trusted F certificate is present:
        data["hypotheticalVerifiedOutcome"]="F"
        self.assertEqual(policy_allocation(data,"ambiguity_hold",25,5),(0,25,0))

    def test_three_failure_votes_in_success_world_refund_is_unsafe(self):
        case={
            "world":"S","observedSuccessVotes":0,
            "observedFailureVotes":3,"signedResponseVisible":False,
            "untrustedAckClaim":False,"hypotheticalVerifiedOutcome":"",
        }
        self.assertEqual(policy_allocation(case,"observed_quorum",25,5),(0,20,5))
        self.assertEqual(policy_allocation(case,"ambiguity_hold",25,5),(0,0,25))

    def test_full_factorial_seeded_model_is_reproducible(self):
        params=dict(seed=32414,replications=3,fee=25,reservation=5)
        a=list(trial_rows(**params))
        b=list(trial_rows(**params))
        self.assertEqual(a,b)
        self.assertEqual(len(a),810)
        summary=summarize(a,**params)
        self.assertEqual(summary["totalPolicyRows"],810)
        self.assertEqual(summary["uniqueModelScenarios"],270)
        self.assertEqual(len(summary["arms"]),45)
        self.assertTrue(summary["notMeasuredLiveNetwork"])
        self.assertTrue(summary["hypotheticalTrustedReceiptNotDeployed"])
        for row in a:
            self.assertEqual(row["providerCreditWei"]+row["consumerCreditWei"]+
                             row["heldWei"],25)
            self.assertLessEqual(row["onlineAdversarialMonitors"],
                                 min(row["adversarialMonitors"],
                                     4-row["partitionedMonitors"]))
            if row["partitionedMonitors"]==4:
                self.assertEqual(row["observedSuccessVotes"]+
                                 row["observedFailureVotes"],0)
                self.assertEqual(row["onlineAdversarialMonitors"],0)
            if row["policy"] in ("ambiguity_hold","ideal_oracle"):
                self.assertFalse(row["isUnsafeCredit"])
        quorum=[r for r in a if r["policy"]=="observed_quorum"]
        self.assertGreater(sum(r["isUnsafeCredit"] for r in quorum),0)

    def test_binomial_interval_and_bad_inputs(self):
        for successes,counts in ((0,10),(5,10),(10,10)):
            low,up=wilson95(successes,counts)
            self.assertLessEqual(low,successes/counts)
            self.assertGreaterEqual(up,successes/counts)
        with self.assertRaises(CampaignError):
            wilson95(11,10)
        with self.assertRaises(CampaignError):
            allocation(set(),25,5)
        for bad in (dict(seed=True),dict(replications=0),dict(fee=0),
                    dict(reservation=26),dict(replications=400)):
            with self.subTest(kwargs=bad),self.assertRaises(CampaignError):
                list(trial_rows(**{**dict(seed=1,replications=3,fee=25,reservation=5),**bad}))

    def test_immutable_hashed_paper_evidence_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            manifest=run(folder,revision=REV,seed=33,replications=2)
            self.assertFalse(manifest["liveNetworkMeasured"])
            for name,item in manifest["artifacts"].items():
                blob=(folder/name).read_bytes()
                self.assertEqual(hashlib.sha256(blob).hexdigest(),item["sha256"])
                self.assertEqual(len(blob),item["bytes"])
            report=json.loads((folder/"summary.json").read_text())
            self.assertEqual(report["totalPolicyRows"],540)
            self.assertIn("Synthetic simulation",
                          (folder/"summary.md").read_text())
            with self.assertRaises(CampaignError):
                run(folder,revision=REV,seed=33,replications=2)
            with self.assertRaises(CampaignError):
                run(folder,revision="main",seed=1,replications=1)

if __name__=="__main__":
    unittest.main()
