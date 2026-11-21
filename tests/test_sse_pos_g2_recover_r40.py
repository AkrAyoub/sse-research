"""R40 G2 recovery source invariants + read-only operation checks."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_g2_recover_r40 as r40

class R40ExistingRealChainRecoveryTests(unittest.TestCase):
    def test_recovery_is_same_chain_and_exact_original_data(self):
        self.assertEqual(r40.GENESIS_TIME, 1795219212)
        self.assertEqual(r40.ORIGINAL_EL, "sse31340-g2-el")
        self.assertEqual(r40.NETWORK, "sse31340-g2-internal")
        self.assertEqual(len(r40.EXPECTED), 5)
        self.assertIn("testnet/deposit_contract_block.txt", r40.EXPECTED)

    def test_recovery_uses_a_different_container_name_preserving_original(self):
        self.assertNotEqual(r40.REPLACEMENT_EL, r40.ORIGINAL_EL)
        self.assertNotIn("31339", r40.REPLACEMENT_EL)

    def test_exact_original_existing_genesis_manifest_is_pinned(self):
        self.assertEqual(
            r40.EXPECTED["testnet/genesis.ssz"],
            "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
        )

    def test_no_source_or_runtime_key_generation_and_no_delete(self):
        code = (ROOT / "tools/sse_pos_g2_recover_r40.py").read_text("utf-8")
        for forbidden in ("--entrypoint", '"rm"', '"kill"', '"prune"', '"stop"',
                          "CREATE-BLS-HD-WALLET", "DERIVE-BLS-VALIDATORS",
                          "recovery.mnemonic", "owner-wallet.pass"):
            self.assertNotIn(forbidden, code)
        self.assertIn("--tmpfs", code)
        self.assertIn("/tmp:rw,nosuid,exec,size=256m", code)
        self.assertIn('"--network-alias", ORIGINAL_EL', code)
        self.assertIn('"--p2p-enabled=false"', code)
        self.assertIn('"--engine-host-allowlist=" + ORIGINAL_EL', code)
        self.assertIn('"--engine-jwt-secret=/jwt/engine.jwt"', code)
        self.assertIn('"--publish", "127.0.0.1:18545:8545/tcp"', code)

    def test_immutable_file_gate_refuses_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "genesis.json"
            f.write_bytes(b"altered")
            with self.assertRaisesRegex(r40.RecoveryRefused, "immutable PUBLIC"):
                r40.safe_public(f, r40.EXPECTED["testnet/genesis.json"])

    def test_no_external_urls_or_data_egress(self):
        code = (ROOT / "tools/sse_pos_g2_recover_r40.py").read_text("utf-8")
        self.assertNotIn("requests.", code)
        self.assertNotIn("https://", code)
        self.assertIn('ProxyHandler({})', code)
        self.assertIn('"--network", NETWORK', code)

    def test_cli_must_require_exact_sha_and_owner_consent(self):
        code = (ROOT / "tools/sse_pos_g2_recover_r40.py").read_text("utf-8")
        self.assertIn("exact_git(commit)", code)
        self.assertIn('RECOVER-CHAIN31340-G2', code)
        self.assertIn("sys.stdin.isatty()", code)


    def test_future_launch_has_exec_tmpfs_only_for_java_besu(self):
        launcher = (ROOT / "scripts/r35_launch_native_chain31340_g2.sh").read_text("utf-8")
        besu = launcher.split("== SUBMIT PINNED BESU EXECUTION ==")[1].split(
            "== SUBMIT PINNED LIGHTHOUSE BEACON =="
        )[0]
        self.assertIn("/tmp:rw,nosuid,exec,size=256m", besu)
        self.assertNotIn("/tmp:rw,nosuid,noexec", besu)
        self.assertIn("--p2p-enabled=false", besu)

    def test_safe_diagnostic_can_identify_new_besu_without_raw_logs(self):
        from sse_pos_g2_diagnose import RECOVERY_CONTAINERS
        self.assertEqual(RECOVERY_CONTAINERS, (r40.REPLACEMENT_EL,))
        script = (ROOT / "tools/sse_pos_g2_diagnose.py").read_text("utf-8")
        self.assertIn('"recoveryContainers": [inspect_one(name)', script)
        self.assertIn('"rawDockerLogsEmitted": False', script)

    def test_readonly_plan_invokes_no_docker_start(self):
        with patch.object(r40, "review", return_value={"safe": True}):
            with patch.object(r40, "recover", side_effect=AssertionError("no start")):
                with patch.object(sys, "argv", ["r40", "--plan", "--expected-commit", "a"*40]):
                    self.assertEqual(r40.main(), 0)

if __name__ == "__main__":
    unittest.main()
