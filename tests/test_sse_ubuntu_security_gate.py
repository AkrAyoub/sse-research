"""Portable static contract for the Ubuntu-only security gate."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_ubuntu_security_gate import UbuntuGateError, environment_check, REQUIRED


class UbuntuSecurityGateTests(unittest.TestCase):
    def test_linux_vs_wsl_vs_windows(self):
        environment_check('NAME="Ubuntu"\nID=ubuntu\n',"6.8.0-generic","Linux")
        for osname,release,kernel in [
            ("Windows",'ID=ubuntu\n',"windows"),
            ("Linux",'ID=debian\n',"6.8.0"),
            ("Linux",'ID=ubuntu\n',"5.15.0-microsoft-standard-WSL2"),
        ]:
            with self.subTest(osname=osname,kernel=kernel),self.assertRaises(UbuntuGateError):
                environment_check(release,kernel,osname)

    def test_gate_includes_all_posix_only_regressions(self):
        expected={"test_sse_qbft_validator_identity.py",
                  "test_sse_vm_role_setup.py",
                  "test_sse_ssh_identity_tunnel.py",
                  "test_sse_lab_release_handoff.py",
                  "test_sse_vm_bootstrap.py"}
        self.assertTrue(expected.issubset(set(REQUIRED)))
        for name in REQUIRED:
            self.assertTrue((ROOT/"tests"/name).is_file())

    def test_gate_does_not_silently_accept_skips(self):
        code=(ROOT/"tools"/"sse_ubuntu_security_gate.py").read_text()
        self.assertIn("result.skipped",code)
        self.assertIn("not result.wasSuccessful()",code)
        self.assertIn("gitCommit",code)
        self.assertNotIn("docker compose up",code)
        self.assertNotIn("cast send",code)


if __name__=="__main__":
    unittest.main()
