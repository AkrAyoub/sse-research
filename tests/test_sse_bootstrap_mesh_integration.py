"""R6 bootstrap automatically wires the node-local UI and opt-in broker enrollment.

Source-only checks: never touch systemd, install packages or contact broker.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_vm_bootstrap as b

SHA="a"*40
ADDRESS="0x"+"12"*20


def opts(**overrides):
    values=dict(revision=SHA,node_id="provider-node-a",role_names="provider",
                rpc_url="https://sepolia.example.org",chain_id=11155111,
                settlement=ADDRESS,install_root=Path("/opt/sse"))
    values.update(overrides)
    return b.make_spec(**values)


class BootstrapIntegrationTests(unittest.TestCase):
    def test_local_console_credential_and_state_directory_bounded(self):
        unit=b.systemd_unit(opts())
        self.assertIn("LoadCredential=ui-token:/etc/sse/node-ui.token",unit)
        self.assertIn("StateDirectory=sse-role-agent",unit)
        self.assertIn("SSE_NODE_SETTINGS_FILE=/var/lib/sse-role-agent/preferences.json",unit)
        self.assertIn("SSE_AGENT_HOST=127.0.0.1",unit)
        self.assertNotIn("SSE_NODE_UI_TOKEN=",unit)
        self.assertNotIn("private_key",unit.lower())

    def test_broker_requires_pair_and_strict_token_path(self):
        for changes in (
            {"broker_url":"https://broker.example"},
            {"enrollment_token_file":Path("/run/sse/enrollment.token")},
            {"broker_url":"http://broker.example","enrollment_token_file":Path("/run/sse/enrollment.token")},
            {"broker_url":"https://broker.example?key=secret",
             "enrollment_token_file":Path("/run/sse/enrollment.token")},
            {"broker_url":"https://broker.example",
             "enrollment_token_file":Path("/tmp/secret")},
        ):
            with self.subTest(changes=changes),self.assertRaises(b.BootstrapError):
                opts(**changes)

    def test_enrollment_plan_is_offline_no_transactions(self):
        s=opts(broker_url="https://broker.example",
               enrollment_token_file=Path("/run/sse/enrollment.token"))
        p=b.describe(s)
        self.assertTrue(p["meshBrokerConfigured"])
        self.assertEqual(p["meshBrokerOrigin"],"https://broker.example")
        self.assertFalse(p["roleActivated"])
        self.assertFalse(p["ethereumTransactionsSent"])
        self.assertNotIn("tskey-auth",repr(p))

    def test_no_mesh_by_default_remains_compatible(self):
        s=opts()
        self.assertIsNone(s.broker_url)
        self.assertFalse(b.describe(s)["meshBrokerConfigured"])

if __name__=="__main__": unittest.main()
