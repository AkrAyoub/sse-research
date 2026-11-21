"""R145: actual Bash subprocess safety regression on isolated temporary HOME."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/sse_fresh_vm_source_bootstrap.sh"
SHA="6da0c668a23fdfec5d006a6da206dac0ce066cca"

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.key=self.home/"deploy_readonly"
        self.key.write_text("unit test placeholder, not an actual private key")
        self.key.chmod(0o600)

    def cmd(self, *args):
        env={**os.environ,"HOME":str(self.home)}
        return subprocess.run(
            ["bash",str(SCRIPT),*args],
            capture_output=True,text=True,timeout=8,env=env,check=False)

    def opts(self,mode="--plan",roles="full_node"):
        return [mode,"--ssh-key",str(self.key),"--commit",SHA,
                "--node-id","large-new-a","--roles",roles]

    def test_readonly_plan_never_clones_or_installs(self):
        r=self.cmd(*self.opts())
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("status=PLAN_ONLY_NO_MUTATION",r.stdout)
        self.assertIn("packagesInstalled=false",r.stdout)
        self.assertFalse((self.home/"sse-research").exists())

    def test_all_supported_roles_and_valid_multirole(self):
        for roles in ("full_node","observer","validator","provider",
                      "consumer","monitor","full_node,monitor,consumer"):
            with self.subTest(roles=roles):
                r=self.cmd(*self.opts(roles=roles))
                self.assertEqual(r.returncode,0,r.stderr)

    def test_unknown_and_duplicate_roles_refused(self):
        for roles in ("administrator","miner","monitor,monitor","full_node,root"):
            with self.subTest(roles=roles):
                r=self.cmd(*self.opts(roles=roles))
                self.assertEqual(r.returncode,2)
                self.assertFalse((self.home/"sse-research").exists())

    def test_missing_and_invalid_commit_refused(self):
        r=self.cmd("--plan","--ssh-key",str(self.key),"--node-id","large-new-a",
                   "--roles","full_node")
        self.assertEqual(r.returncode,2)
        r=self.cmd(*[x if x!=SHA else "not-a-commit" for x in self.opts()])
        self.assertEqual(r.returncode,2)

    def test_preexisting_git_source_refused_without_overwrite(self):
        (self.home/"sse-research").mkdir()
        r=self.cmd(*self.opts())
        self.assertEqual(r.returncode,2)

    def test_existing_chain_owner_identity_refused(self):
        (self.home/".local/share/sse-r27-bls-operator-private").mkdir(parents=True)
        r=self.cmd(*self.opts())
        self.assertEqual(r.returncode,2)

    def test_rejects_unprotected_or_missing_private_deploy_key(self):
        self.key.chmod(0o644)
        r=self.cmd(*self.opts())
        self.assertEqual(r.returncode,2)
        self.key.unlink()
        self.assertEqual(self.cmd(*self.opts()).returncode,2)

    def test_noninteractive_apply_refuses_before_package_or_network(self):
        r=self.cmd(*self.opts(mode="--apply"))
        self.assertEqual(r.returncode,2)
        self.assertFalse((self.home/"sse-research").exists())
        self.assertNotIn("R145_SOURCE_BOOTSTRAP_COMPLETED=true",r.stdout)

    def test_shell_syntax(self):
        r=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,
                         text=True,timeout=5,check=False)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=="__main__":
    unittest.main()
