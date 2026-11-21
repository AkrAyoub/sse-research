"""R137 pure safety tests: no Docker daemon, wallet, genesis or peer traffic."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_pos_r137_independent_observer_create_once as m

class R137Tests(unittest.TestCase):
    def test_names_are_operator_specific_and_not_existing_names(self):
        a = m.names("independent-a")
        b = m.names("independent-b")
        self.assertNotEqual(a, b)
        self.assertNotIn("sse31340-g2-vc", a.values())
        self.assertNotIn("sse31340-r59-nonsigning-el", a.values())
        self.assertNotIn("sse31340-g2-el-r40", a.values())
        for name in (*a.values(), *b.values()):
            self.assertLess(len(name), 128)

    def test_existing_data_root_blocks_creation(self):
        with patch.object(Path, "exists", return_value=True):
            with self.assertRaises(m.Refused):
                m.require_absent(Path("/already-present"), m.names("other-operator"))

    def test_existing_resources_block_creation(self):
        with patch.object(Path, "exists", return_value=False), \\
             patch.object(Path, "is_symlink", return_value=False), \\
             patch.object(m.r59, "resource_exists", side_effect=[False, True]):
            with self.assertRaises(m.Refused):
                m.require_absent(Path("/absent"), m.names("third-party"))

    def test_seed_records_mandatory(self):
        for a, b in [(None, None), ("garbage", None),
                     ("garbage", "enr:" + "A"*90)]:
            with self.subTest(a=a), self.assertRaises((m.Refused, m.r59.R59Refused)):
                m.validate_seeds(a, b)

    def test_only_seven_published_ports_engine_api_not_exposed(self):
        captured = []
        def fake_docker(command, timeout=25):
            captured.append(command)
            return "dummy"
        with patch.object(m.r59, "docker", side_effect=fake_docker), \\
             patch.object(m.os, "geteuid", return_value=1000), \\
             patch.object(m.os, "getegid", return_value=1000):
            m.docker_run("pinned", "independent-el", "independent-network",
                         Path("/home/operator/state"),
                         ["[fca0:2328:7777:8888:9999::1]:30404:30404/tcp",
                          "127.0.0.1:28545:8545/tcp"], ["--network-id=31340"])
        argv = captured[0]
        self.assertIn("--read-only", argv)
        self.assertIn("--cap-drop", argv)
        self.assertIn("--security-opt", argv)
        self.assertIn("no-new-privileges", argv)
        self.assertNotIn("8551/tcp", " ".join(argv))
        self.assertNotIn("--privileged", argv)
        self.assertEqual(argv.count("--publish"), 2)

    def test_refuses_noninteractive_apply_without_mutation(self):
        plan = {"resources": m.names("third-party"), "root": Path("/tmp/unused"),
                "ip": "fca0:2328:7777:8888:9999::1"}
        with patch.object(m.sys.stdin, "isatty", return_value=False), \\
             patch.object(m.sys.stderr, "isatty", return_value=False), \\
             patch.object(m.r59, "docker") as docker:
            with self.assertRaises(m.Refused):
                m.apply(plan, "dummy", "dummy")
            docker.assert_not_called()

    def test_plan_does_not_call_apply(self):
        with patch.object(m, "preflight", return_value={
                "manifest": {"nodeId": "third-party"},
                "ip": "fca0:2328:7777:8888:9999::1",
                "resources": m.names("third-party"),
                "root": Path("/tmp/third-party")}), \\
             patch.object(m, "apply") as apply:
            self.assertEqual(m.main([
                "--plan", "--manifest", "/tmp/manifest",
                "--archive", "/tmp/archive",
                "--execution-seed-enode-v6", "placeholder",
                "--beacon-seed-enr", "placeholder"]), 0)
            apply.assert_not_called()

if __name__ == "__main__":
    unittest.main()
