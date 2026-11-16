"""Offline preflight tests for opt-in real-Docker integration.

These tests must never contact Docker or a public/remote context. They prove
that Docker-backed acceptance tests check local engine and image prerequisites
before any container run or Anvil deployment.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import test_sse_docker_sla_live as live

IMAGE = "sha256:" + "ab" * 32


class DockerPrerequisiteTests(unittest.TestCase):
    def test_missing_image_skips_before_cli_or_context_access(self):
        with patch.object(live.shutil, "which",
                          side_effect=AssertionError("must not inspect CLI")):
            with self.assertRaisesRegex(unittest.SkipTest, "SSE_DOCKER_WORKER_IMAGE"):
                live.require_local_docker_engine("")

    def test_docker_cli_missing_is_skipped(self):
        with patch.object(live.shutil, "which", return_value=None), \
             patch.object(live, "_docker_local_only",
                          side_effect=AssertionError("must not query Docker context")):
            with self.assertRaisesRegex(unittest.SkipTest, "Docker CLI not installed"):
                live.require_local_docker_engine(IMAGE)

    def test_remote_context_refused_before_image_inspection(self):
        with patch.object(live.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(live, "_docker_local_only",
                          side_effect=AssertionError("remote Docker context refused")), \
             patch.object(live.subprocess, "run",
                          side_effect=AssertionError("no docker info allowed")):
            with self.assertRaisesRegex(AssertionError, "remote Docker context"):
                live.require_local_docker_engine(IMAGE)

    def test_stopped_engine_skipped_before_image_inspect(self):
        with patch.object(live.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(live, "_docker_local_only"), \
             patch.object(live.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1, stdout="", stderr="")) as ran:
            with self.assertRaisesRegex(unittest.SkipTest, "Engine unavailable"):
                live.require_local_docker_engine(IMAGE)
        self.assertEqual(ran.call_count, 1)

    def test_local_image_identity_checked_exactly(self):
        working=SimpleNamespace(returncode=0, stdout="linux\n", stderr="")
        wrong=SimpleNamespace(returncode=0, stdout="sha256:"+"ff"*32+"\n", stderr="")
        with patch.object(live.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(live, "_docker_local_only"), \
             patch.object(live.subprocess, "run", side_effect=[working,wrong]) as ran:
            with self.assertRaisesRegex(unittest.SkipTest, "Pinned Docker image unavailable"):
                live.require_local_docker_engine(IMAGE)
        self.assertEqual(ran.call_count, 2)

    def test_validated_local_engine_and_image_pass_preflight(self):
        working=SimpleNamespace(returncode=0, stdout="linux\n", stderr="")
        matching=SimpleNamespace(returncode=0, stdout=IMAGE+"\n", stderr="")
        with patch.object(live.shutil, "which", return_value="/usr/bin/docker"), \
             patch.object(live, "_docker_local_only"), \
             patch.object(live.subprocess, "run", side_effect=[working,matching]) as ran:
            self.assertIsNone(live.require_local_docker_engine(IMAGE))
        self.assertEqual(ran.call_count, 2)


if __name__ == "__main__":
    unittest.main()
