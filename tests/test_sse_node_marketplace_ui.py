"""R5 node-owned marketplace preview interface: offline, no signing or RPC."""
from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sse_role_preview", ROOT/"services"/"role-agent"/"agent.py")
agent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agent
spec.loader.exec_module(agent)

BOARD = "0x" + "11" * 20
SETTLEMENT = "0x" + "22" * 20
POOL = "0x" + "33" * 20
HASH = "0x" + "aa" * 32
TOKEN = "w" * 40


def config(roles="provider,consumer", enabled=True):
    env = {
        "SSE_NODE_ID": "ubuntu-node-a", "SSE_ROLES": roles, "SSE_AGENT_PORT": "8765",
        "SSE_NODE_UI_TOKEN": TOKEN, "SSE_NODE_SETTINGS_FILE": "/tmp/sse-test-ui-settings.json",
    }
    if enabled:
        env.update(SSE_CHAIN_ID="31337", SSE_BOARD_ADDRESS=BOARD,
                   SSE_SETTLEMENT_ADDRESS=SETTLEMENT, SSE_COMMITTEE_POOL_ADDRESS=POOL)
    return agent.config(env)


class MarketplaceUiTests(unittest.TestCase):
    def setUp(self):
        self.conf=config()
        self.conf["port"]=0
        self.server=agent.make_server(self.conf)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self._close)
        self.url="http://127.0.0.1:"+str(self.server.server_address[1])

    def _close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def preview(self, action="bid", role="provider", params=None, token=TOKEN,
                origin=None, conf=None):
        params=params if params is not None else {"requestId": 1,"epochFeeWei": 10}
        headers={"Content-Type": "application/json"}
        if token is not None: headers["Authorization"]="Bearer "+token
        if origin is not None: headers["Origin"]=origin
        request=urllib.request.Request(self.url+"/v1/transaction-plans",
            data=json.dumps({"action": action,"role": role,"params": params}).encode(),
            method="POST",headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=3) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as response:
            return response.code,json.load(response)

    def test_provider_preview_exact_contract_and_zero_broadcast(self):
        code,response=self.preview()
        self.assertEqual(code,200)
        self.assertEqual(response["kind"],"SSE_NODE_TRANSACTION_PLAN")
        self.assertEqual(response["role"],"provider")
        self.assertEqual(response["to"],BOARD)
        self.assertTrue(response["previewOnly"])
        self.assertFalse(response["canBroadcastHere"])
        self.assertFalse(response["ethereumTransactionsSent"])

    def test_consumer_request_preview_owned_by_consumer(self):
        code,data=self.preview("request","consumer",
            {"profileHash":HASH, "policyHash":"0x"+"bb"*32,
             "maxEpochFeeWei":30,"biddingClose":1800000000})
        self.assertEqual(code,200)
        self.assertEqual(data["action"],"request")
        self.assertFalse(data["physicalServiceVerified"])

    def test_roles_not_configured_on_vm_are_refused(self):
        status,data=self.preview("monitor-register","monitor",{"bondWei":1000})
        self.assertEqual(status,422)
        self.assertIn("error",data)

    def test_authentication_required(self):
        self.assertEqual(self.preview(token=None)[0],403)
        self.assertEqual(self.preview(token="wrong")[0],403)

    def test_cross_origin_refused(self):
        self.assertEqual(self.preview(origin="https://attacker.example.org")[0],403)

    def test_without_chain_config_preview_is_disabled(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.conf=config(enabled=False);self.conf["port"]=0
        self.server=agent.make_server(self.conf)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_address[1])
        self.assertEqual(self.preview()[0],503)

    def test_invalid_config_fails_closed(self):
        for changes in (
            {"SSE_CHAIN_ID":"0"},
            {"SSE_CHAIN_ID":"wrong"},
            {"SSE_BOARD_ADDRESS":"0x"+"00"*20},
        ):
            with self.subTest(changes=changes):
                env={"SSE_NODE_ID":"node-a","SSE_ROLES":"consumer",
                     "SSE_CHAIN_ID":"31337","SSE_BOARD_ADDRESS":BOARD,
                     "SSE_SETTLEMENT_ADDRESS":SETTLEMENT,"SSE_COMMITTEE_POOL_ADDRESS":POOL}
                env.update(changes)
                with self.assertRaises(ValueError):
                    agent.config(env)
        with self.assertRaises(ValueError):
            agent.config({"SSE_NODE_ID":"node-a","SSE_ROLES":"consumer",
                          "SSE_CHAIN_ID":"31337"})

    def test_ui_lists_own_role_actions_only(self):
        with urllib.request.urlopen(self.url+"/ui",timeout=3) as r:
            page=r.read().decode()
        self.assertIn('id="txpreview"',page)
        self.assertIn('const ownedRoles=["provider", "consumer"]',page)
        self.assertIn("Preview transaction only",page)
        self.assertIn("No transaction submitted",page)

    def test_invalid_action_arguments_refused(self):
        self.assertEqual(self.preview(params={"requestId":1, "epochFeeWei":-1})[0],422)
        self.assertEqual(self.preview(action="fund",params={})[0],422)
        self.assertEqual(self.preview(action="monitor-register",role="provider",
                             params={"bondWei":1})[0],422)


if __name__=="__main__":
    unittest.main()
