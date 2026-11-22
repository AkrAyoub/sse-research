"""R163 public-release dry-run and mock upload: no GitHub writes or VM IO."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r163_publish_verified_genesis as m

SHA="1c5583968cdf5480382ca988d4a9501f55acee98"

class R163Tests(unittest.TestCase):
    def candidate(self,tmp):
        path=Path(tmp)/m.ASSET
        path.write_bytes(b"UNIT TEST PLACEHOLDER NOT GENESIS")
        (path.parent/"verified-public-genesis.json").write_text(
            json.dumps({
                "schema":m.PROOF_SCHEMA,
                "sha256":m.original.ARCHIVE_SHA,
                "assetFilename":m.ASSET,
                "includesOnlyPublicGenesisMembers":True,
                "newGenesisGenerated":False,
                "validatorSecretInspectedOrCopied":False,
                "publiclyPublished":False,
            }))
        return path

    def test_release_address_is_constant_artifact_not_network_seed(self):
        self.assertEqual(m.PUBLIC_URL,
            "https://github.com/AkrAyoub/sse-research/releases/download/"
            "chain31340-genesis-v1/chain31340-public-native-observer-v1.tar.gz")
        self.assertNotIn("enode:",m.PUBLIC_URL)
        self.assertNotIn("10.50.",m.PUBLIC_URL)

    def test_real_candidate_requires_exact_r150_public_proof(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.original,"verify",return_value={"sha256":m.original.ARCHIVE_SHA,
                                                          "memberDigestsVerified":4}):
            asset=self.candidate(tmp)
            self.assertEqual(m.candidate(asset)["memberDigestsVerified"],4)
            meta=asset.parent/"verified-public-genesis.json"
            doc=json.loads(meta.read_text())
            doc["validatorSecretInspectedOrCopied"]=True
            meta.write_text(json.dumps(doc))
            with self.assertRaises(m.Refused):
                m.candidate(asset)

    def test_missing_original_proof_never_uploads(self):
        with tempfile.TemporaryDirectory() as tmp:
            asset=Path(tmp)/m.ASSET
            asset.write_bytes(b"untrusted")
            with self.assertRaises((m.Refused,m.original.Refused)):
                m.candidate(asset)

    def test_dry_run_prepares_no_authentication_or_external_action(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.original,"verify",return_value={"sha256":m.original.ARCHIVE_SHA,
                                                          "memberDigestsVerified":4}):
            asset=self.candidate(tmp)
            with patch.object(m,"run") as host:
                self.assertEqual(m.candidate(asset)["sha256"],m.original.ARCHIVE_SHA)
                host.assert_not_called()

    def test_explicit_upload_uses_gh_then_independent_sha_readback(self):
        commands=[]
        blob=b"UNIT TEST PLACEHOLDER NOT GENESIS"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.original,"verify",return_value={"sha256":m.original.ARCHIVE_SHA,
                                                          "memberDigestsVerified":4}), \
             patch.object(m.shutil,"which",return_value="/usr/bin/gh"), \
             patch.object(m.subprocess,"run",return_value=subprocess.CompletedProcess(
                 args=[],returncode=1,stdout="",stderr="not found")):
            asset=self.candidate(tmp)
            result=m.upload(
                asset,SHA,
                runner=lambda cmd,**kwargs:commands.append(cmd) or "",
                downloader=lambda url:blob)
            self.assertTrue(result["publishedPublicBytesIndependentlyVerified"])
        self.assertEqual(commands[0][:3],["gh","auth","status"])
        self.assertEqual(commands[1][:3],["gh","release","create"])
        self.assertIn("--target",commands[1])
        self.assertEqual(commands[1][commands[1].index("--target")+1],SHA)
        self.assertNotIn("--clobber",commands[1])

    def test_release_existing_must_not_be_modified(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.original,"verify",return_value={"sha256":m.original.ARCHIVE_SHA,
                                                          "memberDigestsVerified":4}), \
             patch.object(m.shutil,"which",return_value="/usr/bin/gh"), \
             patch.object(m.subprocess,"run",return_value=subprocess.CompletedProcess(
                 args=[],returncode=0,stdout='{"tagName":"chain31340-genesis-v1"}',
                 stderr="")):
            asset=self.candidate(tmp)
            with self.assertRaises(m.Refused):
                m.upload(asset,SHA,runner=lambda cmd,**kwargs:"")
        # A repeat upload should NEVER clobber published genesis.

    def test_published_byte_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.original,"verify",return_value={"sha256":m.original.ARCHIVE_SHA,
                                                          "memberDigestsVerified":4}), \
             patch.object(m.shutil,"which",return_value="/usr/bin/gh"), \
             patch.object(m.subprocess,"run",return_value=subprocess.CompletedProcess(
                 args=[],returncode=1,stdout="",stderr="not found")):
            asset=self.candidate(tmp)
            with self.assertRaises(m.Refused):
                m.upload(asset,SHA,runner=lambda cmd,**kw:"",
                         downloader=lambda url:b"different bytes")

    def test_no_unpinned_commit_allowed(self):
        for revision in ("main","HEAD","0x"+SHA,SHA[:9]):
            with self.subTest(revision=revision),self.assertRaises(m.Refused):
                m.upload("/not/real",revision)

if __name__=="__main__":
    unittest.main()
