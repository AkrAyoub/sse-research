"""R42 genuine, pinned Lighthouse v8.3.3 full config over ORIGINAL R34."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sse_pos_chain31340_inputs import consensus_lines
from sse_pos_g2_lighthouse_config_r42 import (
    BASELINE, BASELINE_GIT_BLOB, ORIGINAL_KEYS, PUBLIC_HASH, ConfigRefused,
    get_keys, synthesize, upstream_git_blob,
)

class R42PinnedLighthouseConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = consensus_lines(genesis_time=1795219212, count=1)
        cls.baseline = BASELINE.read_text("utf-8")

    def test_reference_bytes_equal_exact_upstream_git_blob(self):
        self.assertEqual(upstream_git_blob(BASELINE.read_bytes()), BASELINE_GIT_BLOB)
        self.assertEqual(BASELINE_GIT_BLOB, "d19a5eefb9d428343cb44c45c59803239e0cc787")

    def test_known_original_source_hash_is_unmodified(self):
        self.assertEqual(PUBLIC_HASH, "839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13")

    def test_source_generator_outputs_exact_expected_original_keys(self):
        original = get_keys(self.original, allow_inline_comments=False)
        self.assertEqual(set(original), ORIGINAL_KEYS)
        self.assertEqual(original["DEPOSIT_CHAIN_ID"], "31340")
        self.assertEqual(original["FULU_FORK_EPOCH"], str(2**64 - 1))

    def test_complete_config_fills_required_lighthouse_fields(self):
        rendered, report = synthesize(self.baseline, self.original)
        fields = get_keys(rendered, allow_inline_comments=True)
        for key in (
            "SECONDS_PER_ETH1_BLOCK", "MIN_VALIDATOR_WITHDRAWABILITY_DELAY",
            "SHARD_COMMITTEE_PERIOD", "ETH1_FOLLOW_DISTANCE", "EJECTION_BALANCE",
            "BLOB_SIDECAR_SUBNET_COUNT_ELECTRA", "SLOT_DURATION_MS",
        ):
            self.assertIn(key, fields)
        self.assertGreater(report["newFullConfigTopLevelKeys"], len(ORIGINAL_KEYS))

    def test_every_actual_r34_chain_setting_is_preserved(self):
        rendered, report = synthesize(self.baseline, self.original)
        old = get_keys(self.original, allow_inline_comments=False)
        new = get_keys(rendered, allow_inline_comments=True)
        for key, value in old.items():
            self.assertEqual(new[key], value, key)
        self.assertEqual(report["exactOriginalR34OverridesPreserved"], len(ORIGINAL_KEYS))

    def test_original_electra_genesis_and_fulu_deferred(self):
        rendered, _ = synthesize(self.baseline, self.original)
        data = get_keys(rendered, allow_inline_comments=True)
        self.assertEqual(data["ELECTRA_FORK_EPOCH"], "0")
        self.assertEqual(data["FULU_FORK_EPOCH"], str(2**64 - 1))
        self.assertEqual(data["BLOB_SCHEDULE"], "[]")
        self.assertNotIn("EPOCH: 412672", rendered)
        self.assertEqual(data["DEPOSIT_CHAIN_ID"], "31340")
        self.assertEqual(data["MIN_GENESIS_TIME"], "1795219212")

    def test_refuses_any_changed_chain_id_or_fork(self):
        with self.assertRaisesRegex(ConfigRefused, "genesis/fork"):
            synthesize(self.baseline, self.original.replace("DEPOSIT_CHAIN_ID: 31340", "DEPOSIT_CHAIN_ID: 1"))
        with self.assertRaisesRegex(ConfigRefused, "genesis/fork"):
            synthesize(self.baseline, self.original.replace("ELECTRA_FORK_EPOCH: 0", "ELECTRA_FORK_EPOCH: 5"))

    def test_duplicate_original_public_yaml_field_fails(self):
        with self.assertRaisesRegex(ConfigRefused, "duplicate"):
            synthesize(self.baseline, self.original + "\nDEPOSIT_CHAIN_ID: 31340\n")

    def test_missing_required_upstream_baseline_field_fails(self):
        with self.assertRaisesRegex(ConfigRefused, "missing mandatory config"):
            synthesize(self.baseline.replace("SECONDS_PER_ETH1_BLOCK:", "SECONDS_PER_ETH1_BLOCK_X:"), self.original)

    def test_resume_rechecks_exact_upstream_render_and_r34_backup(self):
        source = (ROOT / "tools/sse_pos_g2_resume_r41.py").read_text("utf-8")
        self.assertIn("BASELINE_GIT_BLOB", source)
        self.assertIn("old.safe_public(BACKUP", source)
        self.assertIn("synthesize(", source)
        self.assertIn('if name != "testnet/config.yaml":', source)

    def test_original_public_config_backup_is_hardlinked_without_destroying_ssz(self):
        source = (ROOT / "tools/sse_pos_g2_lighthouse_config_r42.py").read_text("utf-8")
        self.assertIn("os.link(TARGET, BACKUP)", source)
        self.assertIn("os.replace(TEMP, TARGET)", source)
        self.assertIn("testnet/genesis.ssz", source)

    def test_repair_never_starts_docker_or_modifies_keys(self):
        source = (ROOT / "tools/sse_pos_g2_lighthouse_config_r42.py").read_text("utf-8")
        self.assertNotIn('"start"', source)
        self.assertNotIn('"restart"', source)
        self.assertNotIn('"run"', source)
        self.assertNotIn('"rm"', source)
        self.assertNotIn('mnemonic', source.lower())
        self.assertIn("os.replace(TEMP, TARGET)", source)
        self.assertIn("os.link(TARGET, BACKUP)", source)
        self.assertIn("hashlib.sha1", source)

if __name__ == "__main__":
    unittest.main()
