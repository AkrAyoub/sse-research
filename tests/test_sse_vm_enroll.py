"""Pure offline SSE VM broker client contract tests."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("sse_vm_enroll",ROOT/"tools"/"sse_vm_enroll.py")
c=importlib.util.module_from_spec(spec);sys.modules[spec.name]=c;spec.loader.exec_module(c)


class VmEnrollTests(unittest.TestCase):
    def test_plan_offline_and_no_eth(self):
        p=c.dry_run("provider-01","provider,monitor","https://broker.example.org",
                    "/run/sse/enrollment.token")
        self.assertEqual(p["mode"],"DRY_RUN")
        self.assertFalse(p["ethereumTransactionsSent"])
        self.assertEqual(p["rolesConfigured"],["provider","monitor"])

    def test_reject_http_broker_secrets_paths(self):
        for bad in ("http://broker.example.org", "https://x:y@broker.example.org",
                    "https://broker.example.org/evil", "https://broker.example.org?a=1",
                    "https://broker.example.org#fragment"):
            with self.subTest(bad=bad),self.assertRaises(c.EnrollmentClientError):
                c.safe_broker_url(bad)

    def test_reject_external_token_path(self):
        with self.assertRaises(c.EnrollmentClientError):
            c.dry_run("node-a","monitor","https://broker.example.org","/tmp/secret")

    def test_main_dryrun_no_external_join(self):
        with patch.object(c,"enroll",side_effect=AssertionError("must be dry")):
            self.assertEqual(c.main(["--node-id","node-a","--roles","monitor",
                                     "--broker-url","https://broker.example.org"]),0)

    def test_apply_refuses_unprivileged(self):
        plan=c.dry_run("node-a","monitor","https://broker.example.org",
                       "/run/sse/enrollment.token")
        with patch.object(c,"_require_ubuntu_root",side_effect=c.MeshJoinError("root required")):
            with self.assertRaises(c.MeshJoinError):
                c.enroll(plan)

if __name__=="__main__": unittest.main()
