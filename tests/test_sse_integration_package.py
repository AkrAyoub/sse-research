"""Static protections for a one-host/Actions-free R9 integration branch."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntegrationPackageTests(unittest.TestCase):
    def test_no_workflow_files_in_this_branch(self):
        workflow = ROOT / ".github" / "workflows"
        self.assertFalse(workflow.exists() and any(workflow.glob("*.yml")),
                         "No GitHub Actions workflows allowed on this branch")

    def test_one_validator_per_host_compose(self):
        compose = (ROOT / "infra" / "qbft-multivm" / "compose.yaml").read_text()
        self.assertIn("network_mode: host", compose)
        self.assertIn("--network-id=31338", compose)
        self.assertIn("--rpc-http-host=127.0.0.1", compose)
        self.assertIn("--p2p-interface=", compose)
        self.assertIn("--node-private-key-file=/etc/sse/node.key", compose)
        self.assertIn("sha256 digest", compose)
        self.assertNotIn("0.0.0.0:8545", compose)

    def test_wp09q_integrated_source_and_tests(self):
        pool = (ROOT / "contracts" / "OpenMonitorCommittee.sol").read_text()
        test = (ROOT / "foundry" / "test" / "WP09QBatchedGlobalRecovery.t.sol").read_text()
        self.assertIn("function enableGlobalBatchedRecovery(", pool)
        self.assertIn("function advanceGlobalRecovery(", pool)
        self.assertIn("test40OrderedLeavesInFiveBatchesBuildsFourSeatsAndStandbys", test)

    def test_preserved_research_outputs(self):
        for name in ("WP09N_BASELINE.json", "wp09m_gas_report.txt",
                     "docs/research/WP09N_FINDINGS.md", "tests/test_wp09p.py"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())


if __name__ == "__main__":
    unittest.main()
