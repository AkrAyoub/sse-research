"""R12 safe migration of EXISTING protected PoS mnemonic (no regeneration)."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_prepare_launch import validated_patch,LaunchPrepError,prepare,verify
from sse_pos_devnet_plan import _render,plan

SHA="a"*40
FAUCET="0x"+"12"*20
MNEMONIC=" ".join(["secret"]*24)


def fixtures():
    original=_render(
        faucet=FAUCET,participants=2,validators_per_node=32,
        enclave="sse-pos-research01",mnemonic=MNEMONIC,public_p2p=False
    ).encode()
    # A prior R12 release produced the file without explicit Fulu override.
    prior=original.replace(
        b"  fulu_fork_epoch: 18446744073709551615\n",b""
    )
    manifest={**plan(faucet=FAUCET),"networkConfigCreated":True,
              "secretConfigSha256":hashlib.sha256(prior).hexdigest()}
    return prior,manifest


class PreparedPrivateLaunchTests(unittest.TestCase):
    def test_patch_preserves_every_mnemonic_byte(self):
        source,manifest=fixtures()
        amended,old,new=validated_patch(source,manifest)
        self.assertEqual(amended.count(b"  fulu_fork_epoch: "),1)
        self.assertIn(b"  fulu_fork_epoch: 18446744073709551615\n",amended)
        self.assertIn(MNEMONIC.encode(),amended)
        self.assertEqual(amended.replace(b"  fulu_fork_epoch: 18446744073709551615\n",b""),source)
        self.assertEqual(old,hashlib.sha256(source).hexdigest())
        self.assertEqual(new,hashlib.sha256(amended).hexdigest())
        self.assertNotEqual(old,new)
        same,_,_=validated_patch(amended,manifest)
        self.assertEqual(same,amended)

    def test_tampered_or_reused_genesis_rejected(self):
        source,manifest=fixtures()
        for bad in (
            source.replace(b"network_id: \"31339\"",b"network_id: \"31338\""),
            source.replace(b"validator_count: 32",b"validator_count: 128"),
            source.replace(MNEMONIC.encode(),b"nope"),
            source+b"  fulu_fork_epoch: 0\n",
        ):
            with self.subTest(bad=bad[-24:]),self.assertRaises(LaunchPrepError):
                validated_patch(bad,manifest)
        bad=dict(manifest,secretConfigSha256="a"*64)
        with self.assertRaises(LaunchPrepError):
            validated_patch(source,bad)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "0700 owner-only real file validation requires nonroot POSIX")
    def test_prepare_then_verify_without_leaking_private_mnemonic(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            folder.chmod(0o700)
            source,manifest=fixtures()
            p=folder/"network_params.yaml"
            m=folder/"manifest.json"
            p.write_bytes(source)
            m.write_text(json.dumps(manifest)+"\n")
            p.chmod(0o600)
            m.chmod(0o600)
            with patch("sse_pos_prepare_launch.subprocess.check_output",
                       side_effect=[SHA,""]):
                report=prepare(folder,expected_source_sha=SHA)
            self.assertEqual(report["chainId"],31339)
            self.assertNotIn(MNEMONIC,json.dumps(report))
            self.assertIn(MNEMONIC,p.read_text())
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE((folder/"launch_ready.json").stat().st_mode),0o600)
            self.assertEqual(report,verify(folder))
            self.assertEqual(manifest["secretConfigSha256"],json.loads(m.read_text())["secretConfigSha256"])
            with patch("sse_pos_prepare_launch.subprocess.check_output",
                       side_effect=[SHA,""]):
                with self.assertRaises(LaunchPrepError):
                    prepare(folder,expected_source_sha=SHA)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "nonroot owner-only ACL checks")
    def test_preparation_refuses_broad_directory_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            folder.chmod(0o755)
            with self.assertRaises(LaunchPrepError):
                verify(folder)

if __name__=="__main__":
    unittest.main()
