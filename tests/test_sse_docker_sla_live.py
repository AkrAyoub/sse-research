"""Opt-in real Docker cgroup/image isolation and signed-workload functional test.

This test launches an ephemeral Docker container on the operator's LOCAL Docker
Engine; it does NOT build images, connect to blockchain, or contact any VM.
Never enable the opt-in against a remote Docker context/daemon. Docker daemon
API access is a privileged machine capability, not a safe tenant service.

Prerequisites: build Dockerfile.sse-compute, export full local image ID as
SSE_DOCKER_WORKER_IMAGE=sha256:<64 hex>, then set
SSE_RUN_DOCKER_INTEGRATION=1. Otherwise this suite is skipped.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from sse_challenge import keccak256
from sse_resource_profile_v2 import make_profile,resource_hash
from sse_sla_manifest import proposed_policy
from sse_docker_sla_runner import docker_launch_argv,make_docker_runner
from compute_workload import compute_result

IMAGE_RE=re.compile(r"sha256:[0-9a-f]{64}\Z")
ENABLED=os.environ.get("SSE_RUN_DOCKER_INTEGRATION")=="1"
IMAGE=os.environ.get("SSE_DOCKER_WORKER_IMAGE","")
AVAILABLE=(shutil.which("docker") is not None and bool(IMAGE_RE.fullmatch(IMAGE)))


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def _docker_local_only():
    env_host=os.environ.get("DOCKER_HOST","")
    if env_host and not env_host.startswith("unix://") and not env_host.startswith("npipe://"):
        raise AssertionError("real Docker test forbids remote DOCKER_HOST")
    args=["docker","context","inspect","--format","{{.Endpoints.docker.Host}}"]
    result=subprocess.run(args,capture_output=True,text=True,timeout=10,check=True)
    host=result.stdout.strip()
    if not (host.startswith("unix://") or host.startswith("npipe://")
            or host.startswith("unix:/")):
        raise AssertionError("real Docker test requires a local Unix/npipe Docker context")


def require_local_docker_engine(image):
    """Never run integration Docker commands without a local Linux engine.

    Missing daemon/image is an explicit skipped prerequisite, NOT a passed
    Docker performance/attestation result. Remote contexts fail closed.
    """
    if not isinstance(image, str) or not IMAGE_RE.fullmatch(image):
        raise unittest.SkipTest(
            "Build local Docker image first and export SSE_DOCKER_WORKER_IMAGE")
    if shutil.which("docker") is None:
        raise unittest.SkipTest("Docker CLI not installed")
    _docker_local_only()
    try:
        info = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                              capture_output=True, text=True, timeout=15,
                              check=False)
        if info.returncode != 0 or info.stdout.strip() != "linux":
            raise unittest.SkipTest(
                "Local Docker Linux Engine unavailable: start Docker Desktop")
        found = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True, text=True, timeout=15, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest("Local Docker Linux Engine not reachable") from exc
    if found.returncode != 0 or found.stdout.strip().lower() != image:
        raise unittest.SkipTest(
            "Pinned Docker image unavailable; run docker build then re-export ID")


@unittest.skipUnless(ENABLED, "real Docker test requires explicit opt-in")
@unittest.skipUnless(AVAILABLE, "local Docker CLI and pinned image ID required")
class RealDockerWorker(unittest.TestCase):
    def test_immutable_image_under_strict_limits_produces_exact_result(self):
        require_local_docker_engine(IMAGE)
        port=_port()
        endpoint="http://127.0.0.1:"+str(port)
        name="sse-compute-"+secrets.token_hex(5)
        profile=make_profile("deterministic_compute","https://provider.demo.ts.net",
                             image_digest=IMAGE,cpu_milli=500,
                             memory_bytes=512*2**20)
        policy=proposed_policy(service_kind="deterministic_compute",
                               chain_id=31337,settlement="0x"+"12"*20,
                               resource_profile_hash=resource_hash(profile))
        argv=docker_launch_argv(profile,policy,endpoint,name)
        container_id=None
        try:
            started=subprocess.run(argv,capture_output=True,text=True,
                                   timeout=45,check=False)
            self.assertEqual(started.returncode,0,started.stderr)
            container_id=started.stdout.strip()
            self.assertRegex(container_id,r"^[0-9a-f]{64}$")
            for _ in range(80):
                try:
                    with urlopen(endpoint+"/healthz",timeout=.5) as resp:
                        if resp.status==200:
                            break
                except (OSError,TimeoutError):
                    pass
                time.sleep(.2)
            else:
                self.fail("local isolated compute worker did not become available")
            worker=make_docker_runner(profile,policy,endpoint,name)
            request="0x"+keccak256(b"R7_REAL_DOCKER_CPU_WORKLOAD").hex()
            result=worker(1,0,request)
            self.assertEqual(result,compute_result(1,0,request))
            self.assertEqual(result["rounds"],8192)
        finally:
            if container_id:
                subprocess.run(["docker","stop",container_id],
                               capture_output=True,text=True,timeout=20,check=False)


if __name__=="__main__":
    unittest.main()
