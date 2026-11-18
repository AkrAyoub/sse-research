"""Domainless Funnel pilot: no accidental public exposure or chain actions."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_funnel_pilot as f


class FunnelTests(unittest.TestCase):
    def test_plan_is_read_only_explicit_and_no_domain_purchase(self):
        p = f.plan()
        self.assertEqual(p["mode"], "DRY_RUN")
        self.assertEqual(p["command"], ["tailscale", "funnel", "--bg", "--https=443", "18781"])
        self.assertFalse(p["blockchainTransactionsSent"])
        self.assertTrue(p["publicExposure"])
        self.assertIn(".ts.net", p["publicEndpoint"])

    def test_refuses_implicit_public_exposure(self):
        with self.assertRaises(f.FunnelError):
            f.enable(f.plan(), explicit_approval=False,
                     run=lambda *a: AssertionError("must not run"), probe=lambda *a: True)

    def test_altered_ports_refused(self):
        with self.assertRaises(f.FunnelError):
            f.plan(broker_port=8545)
        with self.assertRaises(f.FunnelError):
            f.plan(https_port=18781)
        bogus = f.plan()
        bogus["command"][-1] = "8545"
        with self.assertRaises(f.FunnelError):
            f.enable(bogus, explicit_approval=True,
                     run=lambda *a: AssertionError("must not run"), probe=lambda *a: True)

    def test_explicit_enable_requires_online_tailnet_and_local_broker(self):
        calls = []
        def runner(cmd):
            calls.append(cmd)
            if cmd[:2] == ["tailscale", "status"]:
                return json.dumps({"BackendState": "Running",
                                   "Self": {"Online": True,
                                            "DNSName": "enroll.tail1234.ts.net."}})
            return ""
        with self.assertRaises(f.FunnelError):
            f.enable(f.plan(), explicit_approval=True,
                     run=runner, probe=lambda host, port: False)
        self.assertEqual(len(calls), 1)
        result = f.enable(f.plan(), explicit_approval=True,
                          run=runner, probe=lambda host, port: True)
        self.assertEqual(result["httpsOrigin"], "https://enroll.tail1234.ts.net")
        self.assertEqual(calls[-1], f.plan()["command"])
        self.assertFalse(result["chainTransactionsSent"])

    def test_offline_tailnet_fails_before_funnel(self):
        def bad(cmd):
            return json.dumps({"BackendState": "Stopped",
                               "Self": {"Online": False, "DNSName": "enroll.tail.ts.net."}})
        with self.assertRaises(f.FunnelError):
            f.enable(f.plan(), explicit_approval=True,
                     run=bad, probe=lambda *a: True)


if __name__ == "__main__":
    unittest.main()
