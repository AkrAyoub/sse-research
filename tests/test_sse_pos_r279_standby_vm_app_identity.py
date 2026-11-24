"""R279 fake owner/checkout preview tests: NO wallet creation or packages."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"r279_standby_vm_app_identity.sh"
SHA="1"*40
ROLES={
    "ayoubakrvm4711":"adaptive-v2-monitor-vm4711",
    "ayoubakrvm4712":"adaptive-v2-monitor-vm4712",
    "ayoubakrvm4713":"adaptive-v2-monitor-vm4713",
    "ayoubakrvm4714":"adaptive-v2-provider-vm4714",
}


class TestR279StandbyAppIdentityNoEffects(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/"home"
        self.home.mkdir()
        fake=Path(self.tmp.name)/"bin"
        fake.mkdir()
        self.fake_bin=fake
        (fake/"id").write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  -u) echo 1001 ;;\n"
            "  -un) echo \"$FAKE_VM_OWNER\" ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
        )
        (fake/"git").write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  rev-parse) echo \"$FAKE_SHA\" ;;\n"
            "  status) if [ \"$FAKE_DIRTY\" = yes ]; then echo ' M changed'; fi ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
        )
        for filename in ("id","git"):
            (fake/filename).chmod(0o700)

    def cmd(self,owner="ayoubakrvm4711",sha=SHA,mode="--preview",*,dirty=False):
        env=dict(os.environ)
        env.update({
            "HOME":str(self.home),
            "PATH":str(self.fake_bin)+os.pathsep+env.get("PATH",""),
            "FAKE_VM_OWNER":owner,
            "FAKE_SHA":SHA,
            "FAKE_DIRTY":"yes" if dirty else "no",
        })
        return subprocess.run(
            ["bash",str(SCRIPT),sha,mode],
            input="\n",capture_output=True,text=True,
            timeout=12,check=False,env=env,
        )

    def test_all_four_real_vm_identity_role_previews_have_no_effects(self):
        for owner,role in ROLES.items():
            with self.subTest(owner=owner):
                r=self.cmd(owner)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn("role:"+role,r.stdout)
                self.assertIn("R279_PREVIEW_ONLY_NO_WALLET_OR_PACKAGE_INSTALL=true",r.stdout)
                self.assertNotIn("R279_ONE_STANDBY_ENCRYPTED_APP_EOA_CREATED",r.stdout)
                self.assertFalse((self.home/".local").exists())

    def test_not_approved_vm_refuses(self):
        r=self.cmd("ayoubakrvm4707")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("owner not one of",r.stderr)

    def test_wrong_pinned_commit_refuses(self):
        r=self.cmd("ayoubakrvm4711",sha="2"*40)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("SHA differs",r.stderr)

    def test_dirty_git_worktree_refuses(self):
        r=self.cmd("ayoubakrvm4711",dirty=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("tracked source files not clean",r.stderr)

    def test_no_tty_create_refuses_without_any_install(self):
        r=self.cmd("ayoubakrvm4711",mode="--create")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("terminal required",r.stderr)
        self.assertFalse((self.home/".local").exists())

    def test_existing_encrypted_identity_refuses_no_overwrite(self):
        private=self.home/".local"/"share"/"sse-v2-app-only"
        private.mkdir(parents=True,mode=0o700)
        private.chmod(0o700)
        key=private/"adaptive-v2-monitor-vm4711.keystore.json"
        key.write_text("encrypted existing wallet dummy")
        r=self.cmd()
        self.assertNotEqual(r.returncode,0)
        self.assertIn("NEVER OVERWRITE",r.stderr)
        self.assertEqual(key.read_text(),"encrypted existing wallet dummy")

    def test_symlinked_private_parent_refuses(self):
        (self.home/".local").symlink_to(Path(self.tmp.name)/"other")
        r=self.cmd()
        self.assertNotEqual(r.returncode,0)
        self.assertIn("symlink",r.stderr)


if __name__=="__main__":
    unittest.main()
