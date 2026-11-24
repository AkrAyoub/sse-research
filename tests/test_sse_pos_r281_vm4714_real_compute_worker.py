"""R281 dedicated-VM actual worker wrapper preview safety, mocked; no Docker."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"r281_vm4714_real_compute_worker.sh"
SHA="a"*40


class TestR281Vm4714ActualWorkerPreview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/"home"
        self.home.mkdir()
        fake=Path(self.tmp.name)/"bin"
        fake.mkdir()
        self.fake_bin=fake
        (fake/"id").write_text(
            '#!/bin/sh\n'
            'case "$1" in\n'
            ' -u) echo 1001 ;;\n'
            ' -un) echo "$FAKE_VM_OWNER" ;;\n'
            ' *) exit 4 ;;\n'
            'esac\n'
        )
        (fake/"git").write_text(
            '#!/bin/sh\n'
            'case "$1" in\n'
            ' rev-parse) echo "$FAKE_SHA" ;;\n'
            ' status) if [ "$FAKE_DIRTY" = yes ]; then echo " M bad"; fi ;;\n'
            ' *) exit 4 ;;\n'
            'esac\n'
        )
        (fake/"docker").write_text(
            '#!/bin/sh\n'
            'echo FAKE_DOCKER_CALLED >&2\n'
            'exit 20\n'
        )
        for name in ("id","git","docker"):
            (fake/name).chmod(0o700)

    def cmd(self,*,owner="ayoubakrvm4714",sha=SHA,actual=SHA,
            mode="--preview",dirty=False):
        env=os.environ.copy()
        env.update({
            "HOME":str(self.home),
            "PATH":str(self.fake_bin)+os.pathsep+env.get("PATH",""),
            "FAKE_VM_OWNER":owner,
            "FAKE_SHA":actual,
            "FAKE_DIRTY":"yes" if dirty else "no",
        })
        return subprocess.run(
            ["bash",str(SCRIPT),sha,mode],
            input="\n",capture_output=True,text=True,
            timeout=12,check=False,env=env
        )

    def test_bash_syntax_checked(self):
        r=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_preview_is_strictly_docker_free(self):
        r=self.cmd()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("R281_PREVIEW_ONLY_NO_DOCKER_ACTIONS_NO_KEYS_NO_TX=true",r.stdout)
        self.assertIn("loopback:http://127.0.0.1:8877",r.stdout)
        self.assertIn("rootfs:readonly",r.stdout)
        self.assertNotIn("FAKE_DOCKER_CALLED",r.stderr)
        self.assertEqual(list(self.home.iterdir()),[])

    def test_wrong_owner_fails_before_docker(self):
        r=self.cmd(owner="ayoubakrvm4713")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("VM4714 owner only",r.stderr)
        self.assertNotIn("FAKE_DOCKER_CALLED",r.stderr)

    def test_wrong_pin_fails_before_docker(self):
        r=self.cmd(actual="b"*40)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("differs",r.stderr)
        self.assertNotIn("FAKE_DOCKER_CALLED",r.stderr)

    def test_malformed_pin_fails(self):
        r=self.cmd(sha="bad")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("40-hex",r.stderr)

    def test_dirty_source_fails_before_docker(self):
        r=self.cmd(dirty=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("tracked source modifications",r.stderr)

    def test_actual_run_requires_real_local_tty(self):
        r=self.cmd(mode="--run")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("real owner TTY required",r.stderr)
        self.assertNotIn("FAKE_DOCKER_CALLED",r.stderr)

    def test_unknown_mode_refused(self):
        r=self.cmd(mode="--install")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("use --preview",r.stderr)


if __name__=="__main__":
    unittest.main()
