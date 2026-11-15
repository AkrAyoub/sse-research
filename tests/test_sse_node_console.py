"""Ubuntu node-local role UI, preference isolation, and auth regression tests."""
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
spec = importlib.util.spec_from_file_location("role_agent_ui", ROOT / "services/role-agent/agent.py")
agent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agent
spec.loader.exec_module(agent)


class RoleConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = "v" * 40
        env = {
            "SSE_NODE_ID": "provider-node-a",
            "SSE_ROLES": "provider,monitor",
            "SSE_AGENT_PORT": "9876",
            "SSE_NODE_UI_TOKEN": self.token,
            "SSE_NODE_SETTINGS_FILE": str(Path(self.tmp.name) / "settings.json"),
        }
        self.conf = agent.config(env)
        self.conf["port"] = 0  # ephemeral loopback port for isolation
        self.server = agent.make_server(self.conf)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close)
        self.url = "http://127.0.0.1:" + str(self.server.server_address[1])

    def _close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=3) as r:
            return r.status, r.read().decode("utf-8"), r.headers.get("Content-Type", "")

    def put(self, payload, token=None, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(
            self.url + "/v1/preferences",
            data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_role_local_ui_only_shows_node_roles(self):
        status, page, content_type = self.get("/ui")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Provider", page)
        self.assertIn("Monitor", page)
        self.assertNotIn("<strong>Consumer</strong>", page)
        self.assertNotIn("<strong>Observer</strong>", page)
        self.assertIn("do not submit transactions", page)

    def test_status_preserves_no_false_chain_claims(self):
        _, raw, _ = self.get("/v1/status")
        data = json.loads(raw)
        self.assertEqual(data["roles"], ["provider", "monitor"])
        self.assertIsNone(data["blockchain_synced"])
        self.assertIsNone(data["monitor_eligible"])

    def test_unauthed_cannot_write(self):
        status, _ = self.put({"provider": {"offered_capacity_units": 2}})
        self.assertEqual(status, 403)
        self.assertFalse(Path(self.conf["settings_file"]).exists())

    def test_cross_origin_refused(self):
        status, _ = self.put({"provider": {"offered_capacity_units": 2}}, self.token,
                             "https://attacker.example")
        self.assertEqual(status, 403)

    def test_local_role_preferences_persist_without_chain_activation(self):
        p = {"provider": {"offered_capacity_units": 3, "min_epoch_fee_wei": 20},
             "monitor": {"probe_interval_seconds": 15, "probe_timeout_ms": 1200}}
        code, result = self.put(p, self.token)
        self.assertEqual(code, 200)
        self.assertFalse(result["activeOnChain"])
        self.assertFalse(result["activeInRuntime"])
        self.assertEqual(result["preferences"], p)
        self.assertEqual(json.loads(Path(self.conf["settings_file"]).read_text()), p)
        _, raw, _ = self.get("/v1/preferences")
        self.assertEqual(json.loads(raw)["preferences"], p)

    def test_other_roles_and_unknown_keys_rejected(self):
        for bad in (
            {"consumer": {"max_epoch_fee_wei": 10}},
            {"provider": {"private_key": 10}},
            {"monitor": {"probe_interval_seconds": True}},
            {"provider": {"min_epoch_fee_wei": -1}},
            {"provider": {"offered_capacity_units": 100001}},
            ["provider"],
        ):
            with self.subTest(bad=bad):
                status, _ = self.put(bad, self.token)
                self.assertEqual(status, 422)

    def test_default_console_is_read_only(self):
        disabled = agent.config({"SSE_NODE_ID": "observer-1",
                                 "SSE_ROLES": "observer"})
        self.assertEqual(disabled["admin_token"], "")
        self.assertEqual(disabled["settings_file"], "")
        self.assertEqual(agent.read_preferences(disabled), {})

    def test_rejects_short_admin_token_and_duplicate_roles(self):
        with self.assertRaises(ValueError):
            agent.config({"SSE_ROLES": "monitor,monitor"})
        with self.assertRaises(ValueError):
            agent.config({"SSE_NODE_UI_TOKEN": "short",
                          "SSE_NODE_SETTINGS_FILE": "/tmp/preferences.json"})

if __name__ == "__main__":
    unittest.main()
