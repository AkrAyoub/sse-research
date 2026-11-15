"""R8 independent dashboard chain routes: authorized, read-only, offline tests."""
from __future__ import annotations
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("sse_dashboard_chain_api",ROOT/"apps"/"control-plane"/"api.py")
app_module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=app_module
spec.loader.exec_module(app_module)
TX="0x"+"ab"*32


class FakeObserver:
    def overview(self):
        return {"chainId":31337,"headNumber":4,"headHash":TX,
                "contractAddresses":[],"rpcFinalityVerified":False,
                "ethTransactionsSent":False}
    def blocks(self, limit):
        return {"chainId":31337,"blocks":[{"number":4,"finality":"UNVERIFIED"}],
                "limitReceived":limit}
    def transaction(self, tx_hash):
        return {"found":True,"hash":tx_hash,"finality":"UNVERIFIED"}
    def events(self, a,b):
        return {"events":[],"startBlock":a,"endBlock":b,"readOnly":True}


class ChainRoutesTest(unittest.TestCase):
    def setUp(self):
        self.before=dict(os.environ)
        os.environ["SSE_CONTROL_TOKEN"]="admin-token-for-chain-observer-tests"
        os.environ["SSE_READ_TOKEN"]="read-token-for-chain-observer-tests"
        self.client=TestClient(app_module.app)
        self.reader={"Authorization":"Bearer read-token-for-chain-observer-tests"}
        self.admin={"Authorization":"Bearer admin-token-for-chain-observer-tests"}

    def tearDown(self):
        os.environ.clear();os.environ.update(self.before)

    def test_default_no_config_fails_closed_for_readers(self):
        for key in ("SSE_OBSERVER_RPC_URL","SSE_OBSERVER_CHAIN_ID","SSE_OBSERVER_CONTRACTS"):
            os.environ.pop(key,None)
        r=self.client.get("/v1/chain/overview",headers=self.reader)
        self.assertEqual(r.status_code,503)

    def test_reader_sees_only_observer_data(self):
        with patch.object(app_module,"_chain_observer",return_value=FakeObserver()):
            overview=self.client.get("/v1/chain/overview",headers=self.reader)
            self.assertEqual(overview.status_code,200)
            self.assertFalse(overview.json()["rpcFinalityVerified"])
            blocks=self.client.get("/v1/chain/blocks?limit=3",headers=self.reader)
            self.assertEqual(blocks.status_code,200)
            self.assertEqual(blocks.json()["limitReceived"],3)
            tx=self.client.get("/v1/chain/transactions/"+TX,headers=self.reader)
            self.assertEqual(tx.status_code,200)
            self.assertEqual(tx.json()["hash"],TX)
            events=self.client.get("/v1/chain/events?start_block=1&end_block=4",headers=self.reader)
            self.assertEqual(events.status_code,200)
            self.assertTrue(events.json()["readOnly"])

    def test_auth_required_before_chain_information(self):
        with patch.object(app_module,"_chain_observer",side_effect=AssertionError("RPC should not be accessed")):
            self.assertEqual(self.client.get("/v1/chain/overview").status_code,401)
            self.assertEqual(self.client.get("/v1/chain/blocks").status_code,401)
            self.assertEqual(self.client.get("/v1/chain/transactions/"+TX).status_code,401)
            self.assertEqual(self.client.get("/v1/chain/events?start_block=1&end_block=4").status_code,401)

    def test_invalid_limits_and_no_write_method(self):
        for path in ("/v1/chain/blocks?limit=0",
                     "/v1/chain/blocks?limit=100",
                     "/v1/chain/events?start_block=-1&end_block=4",
                     "/v1/chain/events?start_block=1&end_block=-1"):
            self.assertEqual(self.client.get(path,headers=self.reader).status_code,422)
        self.assertEqual(self.client.post("/v1/chain/overview",headers=self.admin).status_code,405)

    def test_ui_chain_widgets_render_without_new_role_controls(self):
        doc=self.client.get("/").text
        self.assertIn('id="chainBlocks"',doc)
        self.assertIn('id="chainEvents"',doc)
        self.assertIn('id="lookupTx"',doc)
        self.assertNotIn("Submit monitor vote",doc)
        self.assertNotIn("Create consumer bid",doc)


if __name__=="__main__":
    unittest.main()
