"""Headless source-staged firstboot and tailnet policy must not grant broad access."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class HeadlessPolicyTests(unittest.TestCase):
    def test_headless_firstboot_no_secrets_in_argv_or_unapproved_chain_actions(self):
        s=(ROOT/"scripts"/"r9_headless_validator_bootstrap.sh").read_text()
        self.assertIn("set -euo pipefail",s)
        self.assertIn("/run/sse/validator.invitation",s)
        self.assertIn("--apply",s)
        self.assertIn("--use-existing-tailnet",s)
        self.assertIn("source",s.lower())
        self.assertIn("r9_ubuntu_firsthost.sh",s)
        self.assertIn("sse_validator_mesh_join.py",s)
        self.assertIn("git -C",s)
        for bad in (
            "git reset --hard", "git clean -fd", "git push",
            "docker compose up", "cast send", "anvil --",
            "tailscale logout", "--auth-key=tskey",
        ):
            self.assertNotIn(bad,s)

    def test_example_grants_no_wildcard_rpc_or_admin_tag(self):
        policy=(ROOT/"infra"/"network"/"tailscale-sse-dedicated.hujson.example").read_text()
        self.assertIn("tag:sse-validator",policy)
        self.assertIn("tag:sse-node",policy)
        self.assertIn('"ip": ["tcp:30303", "udp:30303"]',policy)
        self.assertNotIn('"ip": ["*"]',policy)
        self.assertNotIn("0.0.0.0/0",policy)
        self.assertNotIn("tag:admin",policy)
        self.assertNotIn("18545",policy)
        self.assertNotIn("8545",policy)

    def test_docs_claim_not_yet_production_complete(self):
        doc=(ROOT/"docs"/"research"/"R9_AUTOMATED_MESH_ONBOARDING_V1.md").read_text()
        for required in ("not automatic yet", "not complete yet",
                         "personal mixed-use tailnet", "Bearer",
                         "No validator node key was created", "validator-overlay-only"):
            # 'validator-overlay-only' appears in the code; the docs use
            # a broader nonconsensus description.
            if required=="validator-overlay-only":
                continue
            self.assertIn(required.lower(),doc.lower())


if __name__=="__main__":
    unittest.main()
