"""R48: separate genuinely NON-SIGNING native node launch safeguards."""
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r48_external_observer as r

class R48NonsigningIndependentObserverTests(unittest.TestCase):
    def test_exact_actual_step54_tar_sha(self):
        self.assertEqual(r.BUNDLE_SHA256, "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7")

    def test_real_original_public_el_and_cl_genesis_only(self):
        self.assertEqual(set(r.bundle.EXPECTED), {"genesis.json", "config.yaml", "genesis.ssz", "deposit_contract_block.txt"})

    def test_both_signed_enrs_required_not_experimental_enode_dns(self):
        self.assertFalse(r.validate_bootstrap(None, None))
        self.assertTrue(r.validate_bootstrap("enr:"+"A"*120, "enr:"+"B"*120))
        with self.assertRaises(r.ExternalObserverRefused):
            r.validate_bootstrap("enr:"+"A"*120, None)
        with self.assertRaises(r.ExternalObserverRefused):
            r.validate_bootstrap("enr:"+"A"*120, "enr:"+"A"*120)

    def test_new_local_jwt_not_original_owner_jwt(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn("secrets.token_hex(32)", source)
        self.assertIn('create_file(RUN / "engine.jwt"', source)
        self.assertNotIn('source_gate.RUN / "engine.jwt"', source)

    def test_non_internal_docker_and_loopback_only_rpc(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn('"network", "create", "--driver", "bridge", NETWORK', source)
        self.assertNotIn('"--internal"', source)
        self.assertIn('"127.0.0.1:28545:8545/tcp"', source)
        self.assertIn('"127.0.0.1:25052:5052/tcp"', source)
        self.assertNotIn('"0.0.0.0:8551', source)

    def test_no_validator_client_or_secret_path(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertNotIn('"--validators-dir"', source)
        self.assertNotIn('"--secrets-dir"', source)
        self.assertNotIn('["start", "sse31340-g2-vc"]', source)
        self.assertNotIn("mnemonic", source)

    def test_strict_allowlist_archive_no_extractall(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn("bundle.verify_bundle(archive)", source)
        self.assertIn("bundle.digest(content) != bundle.EXPECTED[name]", source)
        self.assertNotIn("extractall", source)

    def test_exact_chain31340_and_engine_auth_native_peering(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        for v in ('"--network-id=31340"', '"--discovery-mode=BOTH"', '"--bootnodes=" + el_enr',
                  '"--boot-nodes=" + bn_enr', '"--engine-jwt-secret=/jwt/engine.jwt"'):
            self.assertIn(v, source)

    def test_plan_has_no_write_or_docker_run(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        plan = source[source.index("def preflight("):source.index("def create_file(")]
        self.assertNotIn('docker(["run"', plan)
        self.assertNotIn('docker(["network", "create"', plan)
        self.assertNotIn("mkdir(", plan)

    def test_archive_and_enr_must_never_be_claimed_as_live_public_peer(self):
        src = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn("archive.stat().st_size <= bundle.MAX_TARBALL", src)
        self.assertIn('"actualSeedReachabilityWasVerifiedByPreflight": False', src)
        self.assertIn('"authenticatedInternetPeerHandshakesObserved": False', src)
        self.assertIn('"realExternalFinalityVerified": False', src)
        self.assertIn('"sourceOnlyEnrSyntaxNotCryptographicVerification": True', src)
        self.assertIn('"noServicesCreatedOrChanged": False', src)

    def test_fresh_non_signing_lighthouse_genesis_sync_is_explicitly_disclaimed(self):
        src = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn('"--allow-insecure-genesis-sync"', src)
        self.assertIn("weak-subjectivity", src)
        self.assertIn('"realExternalFinalityVerified": False', src)

    def test_external_vm_launch_pins_actual_linux_amd64_image_ids(self):
        src = (ROOT / "tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn('pin["tag"]', src)
        self.assertIn('pin["imageId"]', src)
        self.assertIn('"{{.Os}}/{{.Architecture}}"', src)
        self.assertIn('refs[role] = image_id', src)

    def test_apply_is_one_time_and_explicitly_approved(self):
        source = (ROOT/"tools/sse_pos_r48_external_observer.py").read_text("utf-8")
        self.assertIn("START-EXTERNAL-31340-OBSERVER", source)
        self.assertIn("sys.stdin.isatty()", source)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("if RUN.exists() or RUN.is_symlink()", source)

if __name__ == "__main__":
    unittest.main()
