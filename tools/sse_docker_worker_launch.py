#!/usr/bin/env python3
"""R7 node-local Docker worker installer/launcher; DRY RUN by default.

This is an explicitly local, privileged Docker operation on the provider
owner's Linux VM. It NEVER deploys contracts, owns the buyer's wallet, joins
a Tailscale network, or performs remote shell commands. Only immutable locally
available image IDs are accepted; no pull/build during launch.

Rootless Docker is preferred. A Docker daemon socket is a highly privileged
API: do not expose it to the SSE web service or an untrusted tenant.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from urllib.request import ProxyHandler, Request, build_opener
from pathlib import Path

from sse_docker_sla_runner import (DockerSLAError, docker_launch_argv,
                                   validate_setup)
from sse_compute_docker import inspect_container
from sse_resource_profile_v2 import validate_profile
from sse_sla_manifest import validate_policy

HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


class LaunchError(ValueError):
    pass


def _json_file(path: Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 8192:
        raise LaunchError("expected small existing ordinary manifest")
    try:
        return json.loads(path.read_text("utf-8"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise LaunchError("invalid JSON manifest") from exc


def ensure_local_docker():
    if sys.platform != "linux" or os.geteuid() == 0:
        raise LaunchError("Docker launch requires nonroot Linux provider VM")
    if shutil.which("docker") is None:
        raise LaunchError("Docker CLI unavailable")
    host = os.environ.get("DOCKER_HOST", "")
    if host and not host.startswith("unix://"):
        raise LaunchError("remote or non-Unix Docker API forbidden")
    try:
        r = subprocess.run(["docker", "context", "inspect", "--format",
                            "{{.Endpoints.docker.Host}}"],
                           capture_output=True, text=True, timeout=7, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchError("Docker context unavailable") from exc
    if r.returncode != 0 or not r.stdout.strip().startswith("unix://"):
        raise LaunchError("Docker engine must be local Unix socket")
    sock = Path(r.stdout.strip()[len("unix://"):])
    if (not sock.is_absolute() or sock.is_symlink() or not sock.exists()
            or not stat.S_ISSOCK(sock.stat().st_mode)):
        raise LaunchError("Docker context socket is not local or cannot be verified")


def wait_worker_ready(endpoint: str, container_name: str, *, timeout_seconds: float = 12.0):
    """Do not report a running worker until local HTTP has answered healthz.

    Anvil and container start-up on a real Ubuntu VM can be asynchronous.
    A successful 'docker run -d' or inspect is NOT proof that the unprivileged
    Python process can read the code or serve its HTTP endpoint.
    """
    from sse_compute_docker import local_endpoint
    local_endpoint(endpoint)
    opener = build_opener(ProxyHandler({}))  # Never route loopback via a proxy.
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            observed = subprocess.run(
                ["docker", "container", "inspect", "--format",
                 "{{.State.Running}}", container_name],
                capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LaunchError("Docker worker state check failed") from exc
        if observed.returncode != 0 or observed.stdout.strip() != "true":
            raise LaunchError("Docker worker exited before HTTP readiness")
        try:
            with opener.open(Request(endpoint + "/healthz", method="GET"),
                             timeout=1.0) as response:
                if response.status == 200:
                    raw = response.read(2049)
                    if len(raw) <= 2048:
                        body = json.loads(raw)
                        if (type(body) is dict and body.get("ok") is True
                                and body.get("localComputeWorker") is True):
                            return
        except (OSError, ValueError, UnicodeError, TypeError):
            pass
        if time.monotonic() >= deadline:
            raise LaunchError("Docker worker HTTP health did not become ready")
        time.sleep(0.35)


def execute_launch(profile, policy, endpoint, name):
    setup = validate_setup(profile, policy, endpoint, name)
    ensure_local_docker()
    image = setup["imageId"]
    if not HASH.fullmatch(image):
        raise LaunchError("pinned image ID required")
    try:
        verify = subprocess.run(["docker", "image", "inspect", "--format",
                                 "{{.Id}}", image],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchError("immutable image inspection unavailable") from exc
    if verify.returncode != 0 or verify.stdout.strip().lower() != image:
        raise LaunchError("immutable image ID not installed; no implicit pulls allowed")
    args = docker_launch_argv(profile, policy, endpoint, name)
    try:
        launched = subprocess.run(args, capture_output=True, text=True,
                                  timeout=40, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchError("Docker start unavailable; check for orphaned named containers") from exc
    if launched.returncode != 0:
        raise LaunchError("Docker refused worker launch: check local daemon diagnostics")
    cid = launched.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{64}", cid):
        raise LaunchError("Docker started but returned malformed container identity")
    try:
        installed = inspect_container({
            "imageId": image, "endpoint": endpoint,
            "cpuMilli": profile["cpuMilli"], "memoryBytes": profile["memoryBytes"],
        }, endpoint, name, strict_hardening=True)
        if installed["containerId"] != cid:
            raise LaunchError("runtime inspected unexpected Docker container")
        wait_worker_ready(endpoint, name)
    except (ValueError, TypeError, KeyError):
        try:
            subprocess.run(["docker", "stop", cid], timeout=15,
                           capture_output=True, text=True, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise LaunchError("worker inspection or HTTP readiness failed; attempted to stop worker") from None
    return {"kind": "SSE_COMPUTE_DOCKER_WORKER", "running": True,
            "containerId": cid, "containerName": name,
            "localWorkerEndpoint": endpoint, "imageId": image,
            "resourceLimitsLocallyInspected": True,
            "onChainTransactionSent": False, "physicalSlaCertified": False}


def main(argv=None):
    p = argparse.ArgumentParser(description="SSE owner-local immutable Docker worker")
    p.add_argument("--resource-profile", type=Path, required=True)
    p.add_argument("--sla-policy", type=Path, required=True)
    p.add_argument("--worker-endpoint", required=True,
                   help="host local origin, e.g. http://127.0.0.1:8877")
    p.add_argument("--container-name", required=True,
                   help="sse-compute-<approved lease-local identifier>")
    p.add_argument("--launch", action="store_true",
                   help="explicitly launch local Docker worker as nonroot Linux owner")
    args = p.parse_args(argv)
    try:
        profile, policy = _json_file(args.resource_profile), _json_file(args.sla_policy)
        validate_profile(profile)
        validate_policy(policy)
        command = docker_launch_argv(profile, policy, args.worker_endpoint,
                                     args.container_name)
        if not args.launch:
            print(json.dumps({"kind": "SSE_COMPUTE_DOCKER_LAUNCH_PLAN",
                              "mode": "DRY_RUN", "commandArgv": command,
                              "running": False, "dockerContacted": False,
                              "ethereumTransactionsSent": False,
                              "physicalSlaCertified": False},
                             sort_keys=True, indent=2))
            return 0
        print(json.dumps(execute_launch(profile, policy, args.worker_endpoint,
                                        args.container_name),
                         sort_keys=True, indent=2))
        return 0
    except (ValueError, TypeError, OSError) as exc:
        print("SSE_DOCKER_WORKER_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
