"""R8 SSE conservative entitlement explanation: offline N/F/S combinations."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_settlement_explain import explain_inspection, SettlementExplainError


def state(**updates):
    ep={"exists":True,"fee":25,"reservationFee":5,"acknowledged":False,
        "monitoringSealed":False,"outcome":0,"successVotes":0,"failureVotes":0,
        "providerCredited":0,"consumerCredited":0,"unresolvedExposure":25}
    ep.update(updates)
    return {"schema":"sse-onchain-inspection-v1","leaseId":1,"epochId":0,
            "lease":{"consumer":"0x"+"12"*20},"epoch":ep}


class ExplainTests(unittest.TestCase):
    def test_no_epoch_has_no_payout_claim(self):
        s=state();s["epoch"]=None
        result=explain_inspection(s)
        self.assertFalse(result["epochAdmitted"])
        self.assertFalse(result["physicalTruthVerified"])

    def test_no_evidence_all_histories_unresolved(self):
        d=explain_inspection(state())
        self.assertEqual(d["admissibleHistories"],["N","F","S"])
        self.assertEqual(d["providerLowerBoundWei"],0)
        self.assertEqual(d["providerUpperBoundWei"],25)
        self.assertEqual(d["consumerRefundLowerBoundWei"],0)
        self.assertTrue(d["onChainCreditsMatchCurrentBounds"])

    def test_failure_quorum_without_ack_retains_reservation_uncertainty(self):
        d=explain_inspection(state(monitoringSealed=True,outcome=2,
                                   failureVotes=3,consumerCredited=20,
                                   unresolvedExposure=5))
        self.assertEqual(d["admissibleHistories"],["N","F"])
        self.assertEqual(d["providerLowerBoundWei"],0)
        self.assertEqual(d["providerUpperBoundWei"],5)
        self.assertEqual(d["consumerRefundLowerBoundWei"],20)
        self.assertEqual(d["unresolvedExposureWei"],5)
        self.assertTrue(d["onChainCreditsMatchCurrentBounds"])
        self.assertFalse(d["physicalTruthVerified"])

    def test_acknowledged_failure_only_F_refunds_all(self):
        d=explain_inspection(state(acknowledged=True,monitoringSealed=True,
                                  outcome=2, failureVotes=3,
                                  consumerCredited=25, unresolvedExposure=0))
        self.assertEqual(d["admissibleHistories"],["F"])
        self.assertEqual(d["consumerRefundLowerBoundWei"],25)
        self.assertEqual(d["providerUpperBoundWei"],0)

    def test_success_quorum_only_S_credits_provider(self):
        d=explain_inspection(state(monitoringSealed=True,outcome=1,
                                  successVotes=3,providerCredited=25,
                                  unresolvedExposure=0))
        self.assertEqual(d["admissibleHistories"],["S"])
        self.assertEqual(d["providerLowerBoundWei"],25)
        self.assertEqual(d["providerUpperBoundWei"],25)
        self.assertEqual(d["consumerRefundLowerBoundWei"],0)

    def test_ack_without_seal_leaves_F_S_and_no_financial_certification(self):
        d=explain_inspection(state(acknowledged=True))
        self.assertEqual(d["admissibleHistories"],["F","S"])
        self.assertFalse(d["monitoringSealed"])
        self.assertFalse(d["onChainCreditsMatchCurrentBounds"])

    def test_invalid_or_contradictory_evidence_refused(self):
        for inp in (
            state(monitoringSealed=True,outcome=1,acknowledged=False,
                  providerCredited=-1),
            state(fee=5,reservationFee=6),
            state(acknowledged=1),
            state(outcome=7),
            {"schema":"other","epoch":{}},
        ):
            with self.subTest(inp=inp), self.assertRaises(SettlementExplainError):
                explain_inspection(inp)

    def test_refuses_nonS_N_F_evidence_combinations(self):
        # Acknowledged receipt excludes N; failure seal excludes S -> F.
        d=explain_inspection(state(acknowledged=True,
                                   monitoringSealed=True,outcome=2,
                                   consumerCredited=25,
                                   unresolvedExposure=0))
        self.assertEqual(d["admissibleHistories"],["F"])
        self.assertEqual(d["historyProviderEntitlementsWei"]["N"],5)


if __name__=="__main__":
    unittest.main()
