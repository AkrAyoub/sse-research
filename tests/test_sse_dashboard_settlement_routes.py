"""R8 read-only lease explanation endpoint with pinned chain state."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("sse_dashboard_settlement_api",ROOT/"apps"/"control-plane"/"api.py")
control=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=control
spec.loader.exec_module(control)
SETTLEMENT="0x"+"22"*20


def snapshot():
    return {"schema":"sse-onchain-inspection-v1",
            "leaseId":1,"epochId":0,"lease":{"consumer":"0x"+"33"*20},
            "epoch":{"exists":True,"fee":25,"reservationFee":5,
                     "acknowledged":False,"monitoringSealed":True,"outcome":2,
                     "successVotes":0,"failureVotes":3,
                     "providerCredited":0,"consumerCredited":20,
                     "unresolvedExposure":5}}


class FakeObserver:
    config={"contracts":(SETTLEMENT,),"chain_id":31337}
    def rpc(self, method, params):
        raise AssertionError("direct RPC must be stubbed in offline route test")


class SettlementRoutes(unittest.TestCase):
    def setUp(self):
        self.original=dict(os.environ)
        os.environ["SSE_CONTROL_TOKEN"]="lab-node-console-read-separation-admin"
        os.environ["SSE_READ_TOKEN"]="lab-node-console-read-separation-observer"
        os.environ["SSE_OBSERVER_SETTLEMENT_ADDRESS"]=SETTLEMENT
        self.client=TestClient(control.app)
        self.reader={"Authorization":"Bearer lab-node-console-read-separation-observer"}

    def tearDown(self):
        os.environ.clear();os.environ.update(self.original)

    def test_unauthorized_cannot_access_chain(self):
        with patch.object(control,"_chain_observer",
                          side_effect=AssertionError("unauthorized observer call")):
            self.assertEqual(self.client.get(
                "/v1/chain/leases/1/epochs/0").status_code,401)

    def test_read_only_snapshot_and_bounds(self):
        with patch.object(control,"_chain_observer",return_value=FakeObserver()), \
             patch.object(control,"inspect_chain",return_value=snapshot()) as inspect:
            response=self.client.get("/v1/chain/leases/1/epochs/0",
                                     headers=self.reader)
        self.assertEqual(response.status_code,200,response.text)
        details=response.json()
        self.assertFalse(details["participantActionsAvailable"])
        self.assertTrue(details["readOnly"])
        self.assertEqual(details["explanation"]["admissibleHistories"],["N","F"])
        self.assertEqual(details["explanation"]["consumerRefundLowerBoundWei"],20)
        self.assertEqual(details["explanation"]["unresolvedExposureWei"],5)
        self.assertFalse(details["explanation"]["physicalTruthVerified"])
        self.assertTrue(inspect.call_args.kwargs["pin_block_hash"])

    def test_wrong_configured_settlement_is_refused(self):
        os.environ["SSE_OBSERVER_SETTLEMENT_ADDRESS"]="0x"+"ee"*20
        with patch.object(control,"_chain_observer",return_value=FakeObserver()), \
             patch.object(control,"inspect_chain",
                          side_effect=AssertionError("must not inspect unknown address")):
            r=self.client.get("/v1/chain/leases/1/epochs/0",headers=self.reader)
        self.assertEqual(r.status_code,503)

    def test_invalid_indexes_and_write_action_refused(self):
        for path in ("/v1/chain/leases/0/epochs/0",
                     "/v1/chain/leases/1/epochs/-1"):
            self.assertEqual(self.client.get(path,headers=self.reader).status_code,422)
        self.assertEqual(self.client.post("/v1/chain/leases/1/epochs/0",
                                          headers=self.reader).status_code,405)

    def test_dashboard_has_read_only_explanation_panel(self):
        page=self.client.get("/").text
        self.assertIn('id="inspectLease"',page)
        self.assertIn('id="leaseDetail"',page)
        self.assertIn("monitor votes do not independently certify physical service",page)


if __name__=="__main__":
    unittest.main()
