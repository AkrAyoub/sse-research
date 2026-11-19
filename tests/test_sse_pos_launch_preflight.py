"""R13 one-host PoS devnet launch is pinned and upstream fork compatible."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_pos_devnet_plan import _render,plan
from sse_pos_launch_preflight import verify,LaunchError,FAR,FIRST_R13_GENERATOR_SHA

FAUCET="0x"+"12"*20
SHA="a"*40
MNEMONIC=" ".join(["secret"]*24)


def files(directory:Path):
    raw=_render(faucet=FAUCET,participants=1,
                validators_per_node=32,enclave="sse-pos-research01",
                mnemonic=MNEMONIC,public_p2p=False).encode()
    manifest={
        **plan(faucet=FAUCET,participants=1,validators_per_node=32),
        "sourceConfigProfile":"R13_PINNED_ETHEREUM_PACKAGE_SMALL_BOOTSTRAP_V1",
        "sourceGitSha":SHA,
        "sourceConfigFileExists":True,
        "expectedFuluForkEpoch":FAR,
        "expectedBpoForkEpochs":{f"bpo_{i}_epoch":FAR for i in range(1,6)},
        "networkConfigCreated":True,
        "secretConfigSha256":hashlib.sha256(raw).hexdigest(),
    }
    for name,content in (
        ("network_params.yaml",raw),
        ("manifest.json",json.dumps(manifest).encode())
    ):
        path=directory/name
        path.write_bytes(content)
        if os.name=="posix":path.chmod(0o600)
    return manifest,raw


class SmallHostPoSLaunchTests(unittest.TestCase):
    def test_generator_explicitly_defer_all_upstream_dependencies(self):
        rendered=_render(faucet=FAUCET,participants=1,
                         validators_per_node=32,enclave="sse-pos-research01",
                         mnemonic=MNEMONIC,public_p2p=False)
        self.assertIn("count: 1",rendered)
        self.assertIn("validator_count: 32",rendered)
        self.assertNotIn("  - dora",rendered)
        self.assertIn("additional_services: []",rendered)
        for key in ["fulu_fork_epoch"]+[f"bpo_{i}_epoch" for i in range(1,6)]:
            self.assertEqual(rendered.count(f"  {key}: {FAR}"),1)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "nonroot POSIX ACL integration")
    def test_no_secret_printed_and_own_one_host_config_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            base.chmod(0o700)
            manifest,raw=files(base)
            report=verify(base,git_sha=SHA)
            self.assertEqual(report["bootstrapClientPairs"],1)
            self.assertEqual(report["bootstrapValidatorKeys"],32)
            self.assertFalse(report["publicP2PExposed"])
            self.assertFalse(report["consensusRunning"])
            self.assertEqual(report["genesisConfigSha256"],
                             hashlib.sha256(raw).hexdigest())
            self.assertNotIn(MNEMONIC,json.dumps(report))
            self.assertEqual(report["faucetPublicAddress"],FAUCET)
            with self.assertRaises(LaunchError):
                verify(base,git_sha="b"*40)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "nonroot POSIX ACL integration")
    def test_existing_vm4705_genesis_survives_reviewed_code_revisions(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            base.chmod(0o700)
            manifest,raw=files(base)
            manifest["sourceGitSha"]=FIRST_R13_GENERATOR_SHA
            (base/"manifest.json").write_text(json.dumps(manifest))
            accepted=verify(base,git_sha="b"*40)
            self.assertEqual(accepted["sourceGitSha"],FIRST_R13_GENERATOR_SHA)
            self.assertEqual(accepted["reviewedCurrentCheckoutSha"],"b"*40)
            self.assertTrue(accepted["originalR13GenesisPreservedAcrossCodeFix"])
            self.assertEqual(accepted["genesisConfigSha256"],
                             hashlib.sha256(raw).hexdigest())
            self.assertNotIn(MNEMONIC,json.dumps(accepted))
            manifest["sourceGitSha"]="c"*40
            (base/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(LaunchError):
                verify(base,git_sha="b"*40)

    @unittest.skipUnless(os.name=="posix" and os.geteuid()!=0,
                         "nonroot POSIX ACL integration")
    def test_missing_bpo_or_tampered_wallet_causes_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            base.chmod(0o700)
            manifest,raw=files(base)
            # The simplest attack: mutate config but leave signed-off hash.
            config=base/"network_params.yaml"
            config.write_bytes(raw.replace(b"  bpo_1_epoch:",b"  bpo_1_epoch: 0 #"))
            with self.assertRaises(LaunchError):
                verify(base,git_sha=SHA)
            config.write_bytes(raw)
            # A local operator cannot change faucet in JSON alone.
            m=base/"manifest.json"
            manifest["genesisFundedFaucetAddress"]="0x"+"33"*20
            m.write_text(json.dumps(manifest))
            with self.assertRaises(LaunchError):
                verify(base,git_sha=SHA)

    def test_launcher_bash_syntax_is_valid(self):
        bash=shutil.which("bash")
        if not bash:
            self.skipTest("bash not present on this test platform")
        checked=subprocess.run(
            [bash,"-n",str(ROOT/"scripts"/"sse_pos_launch.sh")],
            capture_output=True,text=True,timeout=10,check=False
        )
        self.assertEqual(checked.returncode,0,checked.stderr)

    def test_launcher_prevents_start_when_invalid(self):
        text=(ROOT/"scripts"/"sse_pos_launch.sh").read_text()
        self.assertIn("sse_pos_launch_preflight.py",text)
        self.assertIn("--verify-only",text)
        self.assertIn('readonly UPSTREAM_SHA=',text)
        self.assertIn("kurtosis run --enclave",text)
        # Comments can mention forbidden commands as warnings; only
        # executable shell lines are relevant to destructive execution.
        commands="\n".join(line for line in text.splitlines()
                           if not line.lstrip().startswith("#"))
        self.assertNotIn("kurtosis clean -a",commands)
        self.assertNotIn("git reset --hard",text)
        self.assertNotIn("sudo docker",text)

if __name__=="__main__":
    unittest.main()
