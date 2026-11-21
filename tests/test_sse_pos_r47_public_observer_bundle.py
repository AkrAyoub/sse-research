"""R47: no original secrets in portable public EL/CL native observer bundle."""
from pathlib import Path
import sys
import unittest
import tempfile
import tarfile
import json
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_r47_public_observer_bundle as module

class R47PortableRealObserverArtifacts(unittest.TestCase):
    def test_exact_four_original_public_inputs_and_consensus(self):
        self.assertEqual(set(module.EXPECTED), {
            "genesis.json", "genesis.ssz", "config.yaml",
            "deposit_contract_block.txt",
        })
        self.assertEqual(module.manifest()["chainId"], 31340)
        self.assertEqual(module.manifest()["currency"], "UNVALUED_TEST_ETH")
        self.assertEqual(module.manifest()["genesisTimeUtcUnixSeconds"], 1795219212)

    def test_original_public_hashes_never_changed(self):
        self.assertEqual(module.EXPECTED["genesis.json"], "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8")
        self.assertEqual(module.EXPECTED["config.yaml"], "3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e")
        self.assertEqual(module.EXPECTED["genesis.ssz"], "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82")

    def test_private_signer_material_cannot_become_tar_member(self):
        import io
        bad = {name: b"x" for name in module.EXPECTED}
        bad["validators/keystore.json"] = b"SECRET"
        with self.assertRaisesRegex(module.ArtifactRefused, "only four"):
            module.archive_stream(io.BytesIO(), bad)

    def test_public_manifest_never_includes_operator_signer_or_wan_claim(self):
        data = module.manifest()
        self.assertFalse(data["ownerKeyMaterialIncluded"])
        self.assertFalse(data["bootstrapPeersProvided"])
        self.assertFalse(data["publicInternetP2pVerified"])
        self.assertFalse(data["independentValidatorSignaturesVerified"])
        self.assertFalse(any("password" in key.lower() or "jwt" in key.lower() for key in data))

    def test_tar_member_allowlist_rejects_private_keys_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo(module.PREFIX + "validators/private.json")
                info.size = 0
                archive.addfile(info)
            with self.assertRaisesRegex(module.ArtifactRefused, "unexpected"):
                module.verify_bundle(path)

    def test_archive_verifier_refuses_absent_original_public_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "missing.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo(module.PREFIX + "manifest.json")
                contents = json.dumps(module.manifest()).encode()
                info.size = len(contents)
                import io
                archive.addfile(info, io.BytesIO(contents))
            with self.assertRaisesRegex(module.ArtifactRefused, "lacks"):
                module.verify_bundle(path)

    def test_symlinked_archive_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as d:
            actual = Path(d) / "real.tar.gz"
            actual.write_bytes(b"junk")
            link = Path(d) / "link.tar.gz"
            link.symlink_to(actual)
            with self.assertRaisesRegex(module.ArtifactRefused, "symlinked"):
                module.verify_bundle(link)

    def test_complete_tar_from_synthetic_fixture_verifies_without_extracting(self):
        import io
        samples = {
            "genesis.json": b'{"config":{"chainId":31340}}',
            "config.yaml": b"DEPOSIT_CHAIN_ID: 31340\n",
            "genesis.ssz": b"\x12" * 64,
            "deposit_contract_block.txt": b"0\n",
        }
        hashes = {name: module.digest(data) for name, data in samples.items()}
        sizes = {name: (len(data), len(data)) for name, data in samples.items()}
        with patch.dict(module.EXPECTED, hashes, clear=True):
            with patch.dict(module.SIZES, sizes, clear=True):
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "synthetic-test-fixture.tar.gz"
                    with path.open("wb") as dest:
                        module.archive_stream(dest, samples)
                    report = module.verify_bundle(path, expected=hashes)
                    self.assertTrue(report["originalChain31340ManifestAuthenticated"])
                    self.assertEqual(report["publicGenesisFilesExact"], 4)
                    self.assertFalse(report["archiveExtractedByVerification"])
                    with tarfile.open(path, mode="r:gz") as archive:
                        self.assertEqual(
                            set(archive.getnames()),
                            {module.PREFIX + key for key in (*samples, "manifest.json")}
                        )

    def test_no_docker_restart_or_any_private_keyfile_read(self):
        source = (ROOT / "tools/sse_pos_r47_public_observer_bundle.py").read_text("utf-8")
        for token in ('"start"', '"restart"', '"stop"', '"kill"', '"rm"',
                      "os.environ", "ssh-key", "validators-dir", "secrets-dir"):
            self.assertNotIn(token, source)
        self.assertIn("os.O_EXCL", source)
        self.assertIn("original.safe_public", source)
        self.assertIn("archiveExtractedByVerification", source)

if __name__ == "__main__":
    unittest.main()
