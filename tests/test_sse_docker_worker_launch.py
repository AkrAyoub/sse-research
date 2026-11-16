"""R7 Docker worker launcher: dry-run first, local Docker only, never HTTP/RPC."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import sse_docker_worker_launch as launcher
from sse_resource_profile_v2 import make_profile,canonical_profile,resource_hash
from sse_sla_manifest import proposed_policy,canonical_policy

PROFILE=make_profile("deterministic_compute","https://provider.demo.ts.net",
                     image_digest="sha256:"+"ab"*32,
                     cpu_milli=500,memory_bytes=512*2**20)
POLICY=proposed_policy(service_kind="deterministic_compute",
                       chain_id=31337,settlement="0x"+"12"*20,
                       resource_profile_hash=resource_hash(PROFILE))
WORKER="http://127.0.0.1:8877"
NAME="sse-compute-lease123"


class LocalLauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile=Path(self.temp.name)/"profile.json"
        self.policy=Path(self.temp.name)/"policy.json"
        self.profile.write_bytes(canonical_profile(PROFILE))
        self.policy.write_bytes(canonical_policy(POLICY))

    def argv(self,extra=()):
        return ["--resource-profile",str(self.profile),
                "--sla-policy",str(self.policy),
                "--worker-endpoint",WORKER,
                "--container-name",NAME,*extra]

    def test_dryrun_does_not_probe_or_launch_docker(self):
        output=StringIO()
        with patch.object(launcher,"ensure_local_docker",
                          side_effect=AssertionError("unexpected Docker access")), \
             patch.object(launcher,"execute_launch",
                          side_effect=AssertionError("unexpected launch")), \
             redirect_stdout(output):
            self.assertEqual(launcher.main(self.argv()),0)
        data=json.loads(output.getvalue())
        self.assertEqual(data["kind"],"SSE_COMPUTE_DOCKER_LAUNCH_PLAN")
        self.assertFalse(data["running"])
        self.assertFalse(data["dockerContacted"])
        self.assertEqual(data["commandArgv"][-1],PROFILE["imageDigest"])

    def test_do_not_accept_altered_resource_or_sla(self):
        tampered={**PROFILE,"memoryBytes":256*2**20}
        self.profile.write_text(json.dumps(tampered))
        with redirect_stderr(StringIO()),redirect_stdout(StringIO()):
            self.assertEqual(launcher.main(self.argv()),1)
        self.profile.write_bytes(canonical_profile(PROFILE))
        tampered_policy={**POLICY,"serviceKind":"http_challenge"}
        self.policy.write_text(json.dumps(tampered_policy))
        with redirect_stderr(StringIO()),redirect_stdout(StringIO()):
            self.assertEqual(launcher.main(self.argv()),1)

    def test_launch_explicitly_requires_local_docker(self):
        with patch.object(launcher,"ensure_local_docker",
                          side_effect=launcher.LaunchError("no remote Docker")), \
             redirect_stderr(StringIO()),redirect_stdout(StringIO()):
            self.assertEqual(launcher.main(self.argv(["--launch"])),1)

    def test_no_profile_symlink_or_large_json(self):
        big=Path(self.temp.name)/"huge.json"
        big.write_bytes(b"x"*8193)
        with self.assertRaises(launcher.LaunchError):
            launcher._json_file(big)
        with self.assertRaises(launcher.LaunchError):
            launcher._json_file(Path(self.temp.name)/"missing.json")

    def test_launch_permission_refused_for_root_windows_and_remote(self):
        with patch.object(launcher.sys,"platform","win32"):
            with self.assertRaises(launcher.LaunchError):
                launcher.ensure_local_docker()
        with patch.object(launcher.sys,"platform","linux"), \
             patch.object(launcher.os,"geteuid",return_value=0):
            with self.assertRaises(launcher.LaunchError):
                launcher.ensure_local_docker()
        with patch.object(launcher.sys,"platform","linux"), \
             patch.object(launcher.os,"geteuid",return_value=10001), \
             patch.object(launcher.shutil,"which",return_value="/usr/bin/docker"), \
             patch.dict(launcher.os.environ,{"DOCKER_HOST":"tcp://example.org:2375"}):
            with self.assertRaises(launcher.LaunchError):
                launcher.ensure_local_docker()


if __name__=="__main__": unittest.main()
