"""R5/R6 installer opt-in wiring for node-local transaction previews."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_vm_bootstrap as b

SHA="a"*40
BOARD="0x"+"11"*20
SETTLEMENT="0x"+"22"*20
POOL="0x"+"33"*20


def make(**updates):
    kwargs=dict(revision=SHA,node_id="provider-a",role_names="provider",
                rpc_url="https://sepolia.example.org",chain_id=11155111,
                settlement=SETTLEMENT,install_root=Path("/opt/sse"))
    kwargs.update(updates)
    return b.make_spec(**kwargs)


class BootstrapMarketplaceUI(unittest.TestCase):
    def test_absent_contract_config_preserves_read_only_bootstrap(self):
        s=make()
        self.assertFalse(b.describe(s)["marketplacePreviewConfigured"])
        unit=b.systemd_unit(s)
        self.assertNotIn("SSE_BOARD_ADDRESS",unit)
        self.assertNotIn("SSE_COMMITTEE_POOL_ADDRESS",unit)

    def test_configured_public_contracts_exported_only_to_local_service(self):
        s=make(board_address=BOARD,committee_address=POOL)
        self.assertTrue(b.describe(s)["marketplacePreviewConfigured"])
        unit=b.systemd_unit(s)
        self.assertIn("Environment=SSE_BOARD_ADDRESS="+BOARD,unit)
        self.assertIn("Environment=SSE_SETTLEMENT_ADDRESS="+SETTLEMENT,unit)
        self.assertIn("Environment=SSE_COMMITTEE_POOL_ADDRESS="+POOL,unit)
        self.assertIn("Environment=SSE_CHAIN_ID=11155111",unit)
        self.assertIn("ExecStart=/opt/sse/runtime/"+SHA+"/bin/python ",unit)
        self.assertIn("/opt/sse/releases/"+SHA+"/services/role-agent/agent.py",unit)
        self.assertIn("Environment=SSE_AGENT_HOST=127.0.0.1",unit)
        self.assertNotIn("PRIVATE_KEY",unit)
        self.assertNotIn("SSE_NODE_UI_TOKEN=",unit)

    def test_rejects_partial_and_invalid_addresses(self):
        for changes in (
            {"board_address":BOARD},
            {"committee_address":POOL},
            {"board_address":BOARD,"committee_address":"0x"+"00"*20},
            {"board_address":"bad","committee_address":POOL},
            {"board_address":"0x"+"ab"*20+"\nExecStart=/bin/sh","committee_address":POOL},
        ):
            with self.subTest(changes=changes),self.assertRaises(b.BootstrapError):
                make(**changes)

    def test_mismatched_marketplace_contract_values_do_not_trigger_implicit_transactions(self):
        s=make(board_address=BOARD,committee_address=POOL)
        p=b.describe(s)
        self.assertFalse(p["roleActivated"])
        self.assertFalse(p["ethereumTransactionsSent"])
        self.assertEqual(p["kind"],"SSE_UBUNTU_FIRST_BOOT_PLAN")


if __name__=="__main__":
    unittest.main()
