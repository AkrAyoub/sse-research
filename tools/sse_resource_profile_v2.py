#!/usr/bin/env python3
"""SSE V2 experimental resource manifest for HTTP and deterministic compute.

Independent of the legacy R7 compute profile, which has its own historic
two-monitor/reservation semantics and must NOT be silently reinterpreted.
Resource hashes name an immutable offered configuration, never prove it was
actually provisioned or honored. Versioned policy and resource manifests are
distinct and both committed in the on-chain marketplace request.
"""
from __future__ import annotations

import json
import re

from sse_challenge import keccak256
from urllib.parse import urlsplit
from sse_sla_manifest import WORKLOAD_BY_SERVICE

def _private_endpoint(endpoint):
    if type(endpoint) is not str or not 1 <= len(endpoint) <= 255:
        raise ResourceProfileError("invalid endpoint")
    u = urlsplit(endpoint)
    try:
        port = u.port
    except ValueError:
        raise ResourceProfileError("invalid endpoint port") from None
    if (u.username or u.password or u.query or u.fragment or u.path not in ("", "/")):
        raise ResourceProfileError("resource endpoint cannot contain credentials or paths")
    if (u.scheme == "http" and u.hostname == "127.0.0.1" and
            port is not None and 1 <= port <= 65535):
        return endpoint.rstrip("/")
    if (u.scheme == "https" and u.hostname and u.hostname.endswith(".ts.net")
            and port in (None, 443)):
        return endpoint.rstrip("/")
    raise ResourceProfileError("resource endpoint must be loopback or Tailscale HTTPS")

SCHEMA = "sse-resource-profile-v2"
PREFIX = b"SSE_RESOURCE_PROFILE_V2\x00"
IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
FIELDS = frozenset({"schema", "serviceKind", "workloadSpec", "endpoint",
                    "imageDigest", "cpuMilli", "memoryBytes"})


class ResourceProfileError(ValueError):
    pass


def validate_profile(profile):
    if type(profile) is not dict or set(profile) != FIELDS or profile.get("schema") != SCHEMA:
        raise ResourceProfileError("unsupported or altered resource manifest")
    kind = profile.get("serviceKind")
    if type(kind) is not str or kind not in WORKLOAD_BY_SERVICE:
        raise ResourceProfileError("unsupported resource service type")
    if profile["workloadSpec"] != WORKLOAD_BY_SERVICE[kind]:
        raise ResourceProfileError("resource workload mismatch")
    _private_endpoint(profile["endpoint"])
    if profile["endpoint"].endswith("/"):
        raise ResourceProfileError("resource endpoint must have canonical origin")
    if kind == "http_challenge":
        if (profile["imageDigest"] is not None or
                profile["cpuMilli"] != 0 or profile["memoryBytes"] != 0):
            raise ResourceProfileError("HTTP challenge has no configured container entitlement")
    else:
        image = profile["imageDigest"]
        if type(image) is not str or not IMAGE.fullmatch(image):
            raise ResourceProfileError("compute requires an immutable Docker image digest")
        if (type(profile["cpuMilli"]) is not int or
                not 1 <= profile["cpuMilli"] <= 64000):
            raise ResourceProfileError("invalid requested CPU milli units")
        if (type(profile["memoryBytes"]) is not int or
                not 64 * 2**20 <= profile["memoryBytes"] <= 512 * 2**30):
            raise ResourceProfileError("invalid requested memory bytes")
    return profile


def canonical_profile(profile):
    validate_profile(profile)
    return json.dumps(profile, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def resource_hash(profile):
    return "0x" + keccak256(PREFIX + canonical_profile(profile)).hex()


def make_profile(kind, endpoint, *, image_digest=None, cpu_milli=0, memory_bytes=0):
    if kind not in WORKLOAD_BY_SERVICE:
        raise ResourceProfileError("unsupported service")
    return validate_profile({
        "schema": SCHEMA, "serviceKind": kind,
        "workloadSpec": WORKLOAD_BY_SERVICE[kind], "endpoint": endpoint,
        "imageDigest": image_digest, "cpuMilli": cpu_milli,
        "memoryBytes": memory_bytes,
    })


def compare_policy(profile, policy):
    from sse_sla_manifest import validate_policy
    validate_profile(profile)
    validate_policy(policy)
    if profile["serviceKind"] != policy["serviceKind"] or (
            resource_hash(profile) != policy["resourceProfileHash"]):
        raise ResourceProfileError("resource and SLA policy commitments disagree")
    return True
