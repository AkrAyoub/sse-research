"""Clean current mainline: reject legacy runtime and deployable test mocks.

The legacy implementations and original paper/milestone artifacts live in
the immutable Git history / archive branch, never as production gates.
These tests inspect the source tree; they cannot establish public-P2P
reachability or physical resource independence.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

OBSOLETE_DIRS=(
    "infra/qbft-multivm",
    "research/offline",
    "apps/enrollment",
    "apps/control-plane",
    "services/role-agent",
)
OBSOLETE_FILES=(
    "contracts/MockVRFV25Coordinator.sol",
    "contracts/OpenMonitorBondPool.sol",
    "contracts/SSEBoundsPure.sol",
    "scripts/r9_headless_validator_bootstrap.sh",
    "scripts/manual_integrated_gate.sh",
    "apply_wp09q.py",
)

class CurrentMainlineIntegrity(unittest.TestCase):
    def test_old_permissioned_and_centralized_runtimes_removed(self):
        for name in OBSOLETE_DIRS+OBSOLETE_FILES:
            with self.subTest(path=name):
                self.assertFalse((ROOT/name).exists(),name)

    def test_real_prod_contracts_and_resource_services_retained(self):
        for path in (
            "contracts/OpenMonitorCommittee.sol",
            "contracts/SSESettlement.sol",
            "contracts/OpenResourceBoard.sol",
            "services/provider-agent/direct_work_service.py",
            "services/provider-agent/compute_http_service.py",
            "services/consumer-agent/direct_work_client.py",
            "services/monitor-agent/monitor_capture_once.py",
            "tools/sse_pos_validator_deposit.py",
            "tools/sse_public_network_preflight.py",
        ):
            with self.subTest(path=path):
                self.assertTrue((ROOT/path).is_file(),path)

    def test_mock_vrf_is_confined_to_test_only_source(self):
        mock=ROOT/"foundry/mocks/MockVRFV25Coordinator.sol"
        self.assertTrue(mock.is_file())
        self.assertIn("ONLY a deterministic test double",mock.read_text())
        for p in ("foundry/test/VRFAdapterIntegration.t.sol",
                  "foundry/test/VRFFeePolicy.t.sol",
                  "foundry/test/WP09NGasBench.t.sol"):
            self.assertIn("../mocks/MockVRFV25Coordinator.sol",
                          (ROOT/p).read_text())

    def test_old_31339_launcher_fail_closed_for_public_mode(self):
        script=(ROOT/"scripts/sse_pos_launch.sh").read_text()
        self.assertIn("SSE_PUBLIC_NETWORK",script)
        self.assertIn("SSE_POS_EXPOSE_PUBLIC_P2P",script)
        self.assertIn("31339 leaked-key smoke genesis MUST NOT become public",script)

    def test_single_current_architecture_and_status(self):
        readme=(ROOT/"README.md").read_text()
        architecture=(ROOT/"docs/ARCHITECTURE.md").read_text()
        status=(ROOT/"docs/RESEARCH_STATUS.md").read_text()
        self.assertIn("public",readme.lower())
        self.assertIn("31339",status)
        self.assertIn("NOT",status)
        self.assertIn("No SSE operator approval",readme)
        self.assertIn("No fixed/static IP",architecture)
        self.assertIn("independently operated",architecture)

if __name__=="__main__":
    unittest.main()
