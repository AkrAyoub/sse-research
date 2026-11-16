#!/usr/bin/env python3
"""R7 marketplace-funded compute -> inspected pinned Docker worker adapter.

The signed provider service MUST call the pre-running container and verify
its actual digest before signing. The Docker CLI and Docker local daemon must
be protected from consumers; these calls are made only by the provider node.

Docker inspect proves operator-reported configuration, NOT trusted CPU
allocation, runtime isolation integrity, real cloud SLA or delivery time.
"""
from __future__ import annotations

import re

from compute_workload import compute_result
from sse_resource_profile_v2 import compare_policy, validate_profile
from sse_compute_docker import (ComputeError, inspect_container,
                                local_endpoint, run_compute_probe)

NAME = re.compile(r"sse-compute-[a-z0-9][a-z0-9-]{0,45}\Z")


class DockerSLAError(ValueError):
    pass


def validate_setup(profile: dict, policy: dict, endpoint: str, container: str):
    try:
        validate_profile(profile)
        compare_policy(profile, policy)
        if profile["serviceKind"] != "deterministic_compute":
            raise DockerSLAError("Docker runner is only for deterministic compute")
        local_endpoint(endpoint)
    except (ValueError, TypeError, KeyError) as exc:
        raise DockerSLAError("Docker runner profile, SLA or loopback endpoint invalid") from exc
    if type(container) is not str or not NAME.fullmatch(container):
        raise DockerSLAError("unapproved Docker container name")
    return {
        "endpoint": endpoint,
        "container": container,
        "imageId": profile["imageDigest"],
        "cpuMilli": profile["cpuMilli"],
        "memoryBytes": profile["memoryBytes"],
    }


def docker_launch_argv(profile: dict, policy: dict, endpoint: str, container: str):
    """Exact owner-reviewed Docker run arguments; does NOT launch Docker."""
    setup = validate_setup(profile, policy, endpoint, container)
    port = local_endpoint(endpoint)
    milli = profile["cpuMilli"]
    cpus = f"{milli // 1000}.{milli % 1000:03d}"
    memory = str(profile["memoryBytes"])
    return [
        "docker", "run", "--detach", "--rm", "--pull", "never",
        "--name", setup["container"],
        "--network", "bridge",
        "--publish", f"127.0.0.1:{port}:8877",
        "--user", "10001:10001",
        "--read-only",
        "--cpus", cpus,
        "--memory", memory,
        "--memory-swap", memory,
        "--pids-limit", "64",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--security-opt", "seccomp=builtin",
        "--log-driver", "none",
        "--no-healthcheck",
        setup["imageId"],
    ]


def make_docker_runner(profile: dict, policy: dict, endpoint: str, container: str):
    """Bounded inspected worker function injected into provider signature path.

    The service refuses to sign when the container configuration, worker
    response, digest, or HTTP observation is incorrect/unavailable.
    """
    setup = validate_setup(profile, policy, endpoint, container)
    worker_profile = {
        "endpoint": setup["endpoint"],
        "imageId": setup["imageId"],
        "cpuMilli": setup["cpuMilli"],
        "memoryBytes": setup["memoryBytes"],
    }

    def execute(lease_id, epoch_id, request_hash):
        try:
            config = inspect_container(worker_profile, setup["endpoint"],
                                       setup["container"], strict_hardening=True)
            if config["imageId"] != setup["imageId"]:
                raise DockerSLAError("Docker worker image mismatch")
            if not config["runtimeReportedRunning"]:
                raise DockerSLAError("Docker worker not running")
            evidence = run_compute_probe(setup["endpoint"], lease_id, epoch_id, request_hash)
            expected = compute_result(lease_id, epoch_id, request_hash)
            if (evidence.get("workloadResultVerified") is not True or
                    evidence.get("resultDigest") != expected["resultDigest"] or
                    evidence.get("rounds") != expected["rounds"]):
                raise DockerSLAError("Docker worker result failed independent verification")
        except (ComputeError, OSError, ValueError, TypeError, KeyError) as exc:
            raise DockerSLAError("Docker worker not verified; refuse provider signature") from exc
        return expected

    return execute
