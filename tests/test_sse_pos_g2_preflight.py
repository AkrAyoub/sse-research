"""Focused R35 provenance tests (synthetic data; no VM, keys or Docker)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_g2_preflight import (
    EXPECTED_PUBLIC_FILES, EXPECTED_VALIDATOR_DIGEST, EXPECTED_GENESIS_TIME,
    EXPECTED_SS_BYTES, G2PreflightError, validate_record,
    digest, strict_file, json_file,
)

class R35G2ExactObservedProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prep = {
            "schema": "SSE_R34_ONE_REAL_OPERATOR_PUBLIC_GENESIS_INPUTS_V1",
            "chainId": 31340, "genesisTimeUtcUnixSeconds": EXPECTED_GENESIS_TIME,
            "initialFundingOwnerEoa": "0x13fb73aace8A11Be2899D047635A757a224Ce00B",
            "initialFundingTestEth": 1000000,
            "declaredIndependentOperatorFaultDomains": 1, "publicValidatorsCount": 1,
            "publicValidatorListSha256": EXPECTED_VALIDATOR_DIGEST,
            "chainStarted": False, "trueIndependentOperatorsVerified": False,
        }
        self.gen = {
            "schema": "SSE_R25_GENESIS_ARTIFACT_PREPARE_V1",
            "intendedChainId": 31340, "mode": "single-real-operator-LAB-only",
            "consensusGenesisSszGeneratedByPinnedRealBinary": True,
            "genesisSszBytes": EXPECTED_SS_BYTES,
            "genesisSszSha256": EXPECTED_PUBLIC_FILES["beacon-generated/genesis.ssz"],
            "elGenesisSha256": EXPECTED_PUBLIC_FILES["genesis.json"],
            "clConfigSha256": EXPECTED_PUBLIC_FILES["config.yaml"],
            "publicValidatorListSha256": EXPECTED_VALIDATOR_DIGEST,
            "publicValidatorKeys": 1, "declaredOperators": 1,
            "actualELAndCLClientsAcceptedArtifacts": False, "networkStarted": False,
        }

    def test_exact_observed_step40_provenance_is_accepted_as_only_preflight(self):
        self.assertIsNone(validate_record(self.prep, self.gen))

    def test_refuse_changed_genesis_hash_or_non_real_ssz(self):
        self.gen["consensusGenesisSszGeneratedByPinnedRealBinary"] = False
        with self.assertRaisesRegex(G2PreflightError, "generator provenance"):
            validate_record(self.prep, self.gen)
        self.gen["consensusGenesisSszGeneratedByPinnedRealBinary"] = True
        self.gen["genesisSszSha256"] = "0" * 64
        with self.assertRaisesRegex(G2PreflightError, "generator provenance"):
            validate_record(self.prep, self.gen)

    def test_refuse_fake_independent_operator_claim(self):
        self.prep["declaredIndependentOperatorFaultDomains"] = 4
        with self.assertRaisesRegex(G2PreflightError, "public preparation"):
            validate_record(self.prep, self.gen)

    def test_refuse_test_ether_change_or_wrong_chain(self):
        self.prep["chainId"] = 31339
        with self.assertRaisesRegex(G2PreflightError, "public preparation"):
            validate_record(self.prep, self.gen)
        self.prep["chainId"] = 31340
        self.prep["initialFundingTestEth"] = 2000000
        with self.assertRaisesRegex(G2PreflightError, "public preparation"):
            validate_record(self.prep, self.gen)

    def test_public_manifest_duplicate_keys_rejected(self):
        p = self.root / "bad.json"
        p.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
        # Explicit safe fixture mode: the owner VM may have group-writable
        # default umask. Exercise duplicate JSON parsing, not the earlier
        # (correct) file-permission gate. Never weaken the production gate.
        p.chmod(0o600)
        with self.assertRaisesRegex(G2PreflightError, "manifest"):
            json_file(p)

    def test_group_writable_manifest_is_refused_before_json_parsing(self):
        p = self.root / "unsafe.json"
        p.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
        p.chmod(0o660)
        with self.assertRaisesRegex(G2PreflightError, "unsafe or unexpected public artifact"):
            json_file(p)

    def test_symlinked_public_artifact_rejected(self):
        p = self.root / "public.txt"
        p.write_text("ok", encoding="utf-8")
        link = self.root / "linked.txt"
        link.symlink_to(p)
        with self.assertRaisesRegex(G2PreflightError, "unsafe"):
            strict_file(link)

    def test_g2_besu_engine_api_uses_supported_port_not_unsupported_host(self):
        launcher = (ROOT / "scripts/r35_launch_native_chain31340_g2.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--engine-rpc-host", launcher)
        self.assertIn("--engine-rpc-port=8551", launcher)
        self.assertIn("--engine-rpc-port --engine-host-allowlist", launcher)
        self.assertIn("--engine-jwt-secret=/jwt/engine.jwt", launcher)
        self.assertIn("--network \"$NET\"", launcher)
        self.assertIn("--p2p-enabled=false", launcher)

    def test_any_public_artifact_mutation_changes_sha(self):
        p = self.root / "genesis.json"
        p.write_text("real input", encoding="utf-8")
        h1 = digest(p)
        p.write_text("altered input", encoding="utf-8")
        self.assertNotEqual(h1, digest(p))

if __name__ == "__main__":
    unittest.main()
