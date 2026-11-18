"""Static contract for new-host source and local-key workflow."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class FirsthostScriptTests(unittest.TestCase):
    def test_no_remote_writes_or_unapproved_service_activation(self):
        src=(ROOT/"scripts"/"r9_ubuntu_firsthost.sh").read_text()
        self.assertIn("set -euo pipefail",src)
        self.assertIn("git rev-parse HEAD",src)
        self.assertIn("test_sse_qbft_*.py",src)
        self.assertIn("sse_ubuntu_security_gate.py",src)
        self.assertIn("sse_r9_host_setup.py doctor",src)
        self.assertIn("--apply-identity",src)
        self.assertIn("readyForValidatorIdentity",src)
        for forbidden in (
            "git reset --hard", "git clean -fd", "git push",
            "docker compose up", "tailscale up --auth-key=",
            "cast send", "anvil --chain-id",
        ):
            self.assertNotIn(forbidden,src)

    def test_runbook_freezes_historical_chain_and_explains_manual_join(self):
        src=(ROOT/"docs"/"research"/"R9_VM_SOURCE_ROLLOUT_AND_FIRSTHOST.md").read_text()
        self.assertIn("VM4695 original Anvil31337",src)
        self.assertIn("VM4704",src)
        self.assertIn("sudo tailscale up",src)
        self.assertIn("NeedsLogin",src)
        self.assertIn("sse_r9_release_update.py",src)
        self.assertIn("no automatic Docker start or restart",src)


if __name__=="__main__":
    unittest.main()
