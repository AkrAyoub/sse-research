"""Plan-only tests for scripts/sse_setup.py (TEST FIXTURES ONLY).
SOURCE-ONLY: written 2026-11-27, not executed. Owner runs: python3 -m unittest tests.test_sse_setup -v"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sse_setup as setup

SHA = "a" * 40


class SetupPlanTest(unittest.TestCase):
    def ids(self, roles, **kw):
        return [s["id"] for s in setup.plan(roles, SHA, **kw)]

    def test_app_roles_get_a_node_first_and_linger_last(self):
        self.assertEqual(self.ids(["consumer", "monitor"]),
                         ["source-and-role-state", "owner-cli", "v4-app-roles", "linger"])

    def test_validator_adds_validator_and_reward_timer_without_app_steps(self):
        self.assertEqual(self.ids(["validator"]),
                         ["source-and-role-state", "owner-cli", "validator", "reward-timer"])

    def test_refuses_unknown_roles_and_missing_commit(self):
        with self.assertRaises(setup.Refused):
            setup.plan(["miner"], SHA)
        with self.assertRaises(setup.Refused):
            setup.plan([], SHA)
        with self.assertRaises(setup.Refused):
            setup.plan(["consumer"], "HEAD")

    def test_never_plans_wallet_funding_or_deployment(self):
        argv = " ".join(" ".join(s["argv"]) for s in setup.plan(list(setup.ROLES), SHA, publish_console=True))
        for forbidden in ("forge", "cast", "deploy", "sendTransaction", "--private-key"):
            self.assertNotIn(forbidden, argv)
        self.assertIn("--publish-readonly-console", argv)


if __name__ == "__main__":
    unittest.main()
