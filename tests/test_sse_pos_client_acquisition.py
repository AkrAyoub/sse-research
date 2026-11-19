"""Source-only contract for the real Besu/Lighthouse client acquisition gate."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "r19_acquire_pos_clients.sh"

class NativeClientGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SCRIPT.read_text(encoding="utf-8")

    def test_exact_git_sha_gate(self):
        self.assertIn('EXPECTED_SHA="$1"', self.src)
        self.assertIn('ACTUAL_SHA="$(git rev-parse --verify HEAD^{commit})"', self.src)
        self.assertIn('ACTUAL_SHA" != "$EXPECTED_SHA"', self.src)

    def test_besu_and_lighthouse_real_upstream_tags(self):
        self.assertIn('hyperledger/besu:26.11.1', self.src)
        self.assertIn('sigp/lighthouse:v8.3.3', self.src)
        self.assertNotIn('besu:latest', self.src)
        self.assertNotIn('lighthouse:latest', self.src)

    def test_immutable_digest_capture_required(self):
        self.assertIn('RepoDigests', self.src)
        self.assertIn('@sha256:', self.src)
        self.assertIn('R19_CLIENT_IMAGES_PINNED_BY_DIGEST=false', self.src)

    def test_docker_containers_cannot_open_public_ports_or_use_host_net(self):
        self.assertIn('--network none', self.src)
        self.assertIn('--read-only', self.src)
        self.assertIn('--cap-drop ALL', self.src)
        self.assertIn('--security-opt no-new-privileges', self.src)
        self.assertIn('--user 65534:65534', self.src)
        self.assertNotIn('--network host', self.src)
        self.assertNotIn('--privileged', self.src)
        self.assertNotIn('-p 30303', self.src)
        self.assertNotIn('-p 9000', self.src)

    def test_preserves_besu_security_wrapper(self):
        # Besu's Docker image has a security-configuring entrypoint; only
        # Lighthouse's dedicated CLI is overridden in this version probe.
        self.assertIn('entrypoint_args=(--entrypoint lighthouse)', self.src)
        self.assertIn('"${entrypoint_args[@]}" "$digest" --version', self.src)
        self.assertNotIn('--entrypoint "$name"', self.src)

    def test_no_admission_or_genesis_claims(self):
        self.assertIn('R19_NATIVE_EL_CL_P2P_STARTED=false', self.src)
        self.assertIn('R19_BEACON_GENESIS_CREATED=false', self.src)
        self.assertIn('R19_INDEPENDENT_VALIDATOR_KEYS_CREATED=false', self.src)
        self.assertIn('R19_PUBLIC_POS_NETWORK_DEPLOYED=false', self.src)

if __name__ == "__main__":
    unittest.main()
