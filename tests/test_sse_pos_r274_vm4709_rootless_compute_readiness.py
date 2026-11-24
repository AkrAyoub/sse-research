"""R274 safe rootless candidate audit: no rootful Docker or shell actions."""
import contextlib
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r274_vm4709_rootless_compute_readiness as r


class TestR274RootlessProviderNoEffects(unittest.TestCase):
    def test_valid_subuid_gid_ranges_preserve_owner_only(self):
        got=r.ranges("wrong:200000:99999\n"+
                     "ayoubakrvm4709:100000:65536\n"+
                     "# comment\n",r.OWNER)
        self.assertEqual(got,[{"start":100000,"count":65536}])

    def test_invalid_subordinate_range_fail_closed(self):
        for text in ("ayoubakrvm4709:a:65536",
                     "ayoubakrvm4709:4294967295:65536",
                     "ayoubakrvm4709:10000:4294967296"):
            with self.subTest(text=text),self.assertRaises(r.Refused):
                r.ranges(text,r.OWNER)

    def test_socket_no_implicit_rootful_docker_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"docker.sock"
            self.assertEqual(r.socket_state(p,os.geteuid())["state"],"NOT_CREATED")
            p.write_text("not socket")
            self.assertEqual(r.socket_state(p,os.geteuid())["state"],"NOT_UNIX_SOCKET")
            p.unlink()
            s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            try:
                s.bind(str(p))
                self.assertEqual(r.socket_state(p,os.geteuid())["state"],
                                 "EXISTING_OWNER_SOCKET")
            finally:
                s.close()

    def test_symlink_socket_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=root/"file"
            a.write_text("hello")
            b=root/"docker.sock"
            b.symlink_to(a)
            self.assertEqual(r.socket_state(b,os.geteuid())["state"],
                             "SYMLINK_REFUSED")

    def test_no_operator_root_or_wrong_vm_user(self):
        with patch.object(r.os,"geteuid",return_value=0):
            with self.assertRaisesRegex(r.Refused,"nonroot"):
                r.collect()
        with patch.object(r.os,"geteuid",return_value=11111),patch.object(
            r.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="wrong")):
            with self.assertRaisesRegex(r.Refused,"VM4709"):
                r.collect()

    def test_missing_rootless_deps_report_not_install(self):
        def read(path):
            if path in ("/etc/subuid","/etc/subgid"):
                return "ayoubakrvm4709:100000:65536\n"
            raise AssertionError("read unexpected path")
        with patch.object(r.os,"geteuid",return_value=11111),patch.object(
            r.pwd,"getpwuid",return_value=SimpleNamespace(pw_name=r.OWNER)),patch.dict(
            r.os.environ,{"XDG_RUNTIME_DIR":"/run/user/11111"}):
            report=r.collect(read_file=read,which=lambda name: None)
        self.assertFalse(report["rootlessPrerequisitesPresent"])
        self.assertFalse(report["rootlessDaemonActuallyRunningVerified"])
        self.assertFalse(report["nativePoSRootfulDaemonModified"])
        self.assertFalse(report["privilegedCommandExecuted"])
        self.assertFalse(report["packageInstalled"])
        self.assertFalse(report["transactionSignedOrSent"])
        self.assertTrue(report["subordinateIdMappings"]["subuid"][
            "atLeast65536ContiguousIds"])

    def test_main_requires_explicit_inventory_flag_no_install_mode(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(r.main([]),2)


if __name__=="__main__":
    unittest.main()
