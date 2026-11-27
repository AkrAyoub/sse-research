#!/usr/bin/env python3
"""V4 provider job runner and monitor prober for the supported compute service.

SOURCE-ONLY (2026-11-27): never executed.

Supported service (fail closed for anything else): SHA256_CHAIN_8192, the
existing deterministic CPU workload (tools/compute_workload.py) executed by the
pinned rootless Docker worker (historically live-verified for V3 on VM4714).
Arbitrary uploaded code is NOT supported until microVM-grade isolation exists.

Canonical output: JSON with sorted keys and compact separators.
responseHash = keccak256(canonical output bytes). Outputs are stored
content-addressed under <state>/outputs/<responseHash>.json for consumer
retrieval through the provider's authenticated endpoint.

Monitor verdicts (never fabricated):
  success            fetched output == independently recomputed result and its
                     keccak equals the on-chain authenticated responseHash
  qualified_failure  on-chain authenticated responseHash, fetched output hashes
                     to it, but differs from the deterministic recomputation
                     (signed wrong result: design D-07; only for deterministic work)
  inconclusive       anything else (timeouts, HTTP errors, missing response,
                     hash mismatch with fetched bytes, unsupported service)
"""
import json
import time
import ssl
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler

import sse_v4_state as st
from compute_workload import compute_result
from sse_challenge import keccak256
from sse_compute_docker import inspect_container, local_endpoint, require_local_owner_rootless_socket

SUPPORTED_PROFILES = {}  # profileHash (lower hex) -> service id; filled from policy
MAX_BODY = 4096


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def response_hash(output):
    return "0x" + keccak256(canonical(output)).hex()


def endpoint_hash(url):
    return "0x" + keccak256(url.encode()).hex()


def _check_url(url, allow_http_local=False):
    u = urlsplit(url)
    st.require(u.username is None and u.password is None and not u.query and not u.fragment, "bad endpoint URL")
    if u.scheme == "http":
        st.require(allow_http_local and u.hostname == "127.0.0.1", "plain http only to the local worker")
    else:
        st.require(u.scheme == "https", "https required")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise st.StateError("endpoint redirect refused")


def _post(url, body, ca_file=None, timeout=8, allow_http_local=False):
    _check_url(url, allow_http_local)
    ctx = ssl.create_default_context(cafile=ca_file) if url.startswith("https") else None
    req = Request(url, data=canonical(body), headers={"Content-Type": "application/json"}, method="POST")
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout) as r:
        st.require(r.status == 200, "HTTP status " + str(r.status))
        data = r.read(MAX_BODY + 1)
    st.require(len(data) <= MAX_BODY, "response too large")
    return json.loads(data)


def resource_binding(cfg, lease):
    """Validate owner-held preimages of the exact V4 profile/offer commitments.
    CPU is a quota, not dedicated hardware. No writable storage is supported.
    """
    p = cfg.get("profiles", {}).get(lease["profileHash"])
    o = cfg.get("offers", {}).get(lease["offerHash"])
    w = cfg.get("workers", {}).get(lease["profileHash"])
    st.require(isinstance(p, dict) and response_hash(p) == lease["profileHash"], "profile preimage missing or mismatched")
    st.require(isinstance(o, dict) and response_hash(o) == lease["offerHash"], "offer preimage missing or mismatched")
    st.require(isinstance(w, dict), "worker binding missing")
    st.require(p.get("schema") == "SSE_V4_PROFILE_V1" and o.get("schema") == "SSE_V4_OFFER_V1"
               and p.get("service") == "SHA256_CHAIN_8192" and o.get("services") == ["SHA256_CHAIN_8192"],
               "unsupported resource manifest")
    st.require(isinstance(o.get("endpointUrl"), str) and endpoint_hash(o["endpointUrl"]) == lease["endpointHash"],
               "offer endpoint mismatch")
    r, a = p["resources"], o["resources"]
    for k in ("cpuCores", "memoryMiB", "storageMiB"):
        st.require(type(r.get(k)) is int and type(a.get(k)) is int and 0 <= r[k] <= a[k],
                   "invalid or insufficient offered resources")
    st.require(1 <= r["cpuCores"] <= 256 and 64 <= r["memoryMiB"] <= 1 << 20
               and r["storageMiB"] == a["storageMiB"] == 0, "unsupported resource allocation")
    st.require(type(o.get("maxConcurrentLeases")) is int and o["maxConcurrentLeases"] == 1,
               "only one reserved lease per worker is currently supported")
    sla = p["sla"]
    for k in ("responseSeconds", "maxRuntimeSeconds"):
        st.require(type(sla.get(k)) is int and 1 <= sla[k] <= 86400, "invalid runtime SLA")
    st.require(sla["maxRuntimeSeconds"] <= sla["responseSeconds"] <= lease["responseSeconds"],
               "profile response SLA incompatible with lease")
    st.require(isinstance(w.get("imageId"), str) and re.fullmatch(r"sha256:[0-9a-f]{64}", w["imageId"]),
               "immutable worker image required")
    st.require(isinstance(w.get("container"), str) and re.fullmatch(r"sse-compute-[a-z0-9][a-z0-9-]{0,45}", w["container"]),
               "invalid worker container")
    local_endpoint(w["url"])
    st.require(isinstance(w.get("dockerSocket"), str), "explicit private rootless Docker socket required")
    return p, o, w


def make_job_runner(policy, state_dir):
    cfg = policy.get("provider", {})
    outdir = st.private_dir(Path(state_dir) / "outputs")

    def run(job):
        try:
            p, _, w = resource_binding(cfg, job)
            require_local_owner_rootless_socket(w["dockerSocket"])
            worker = w["url"]
            limits = {"endpoint": worker, "imageId": w["imageId"],
                      "cpuMilli": p["resources"]["cpuCores"] * 1000,
                      "memoryBytes": p["resources"]["memoryMiB"] * 2**20}
            before = inspect_container(limits, worker, w["container"], strict_hardening=True,
                                       docker_socket=w["dockerSocket"])
        except (ValueError, KeyError, TypeError, OSError):
            return {"state": "REFUSED_RESOURCE_BINDING", "finishedAt": int(time.time())}
        remaining = job["responseDeadline"] - time.time()
        if remaining <= 0:
            return {"state": "MISSED_DEADLINE", "finishedAt": int(time.time())}
        timeout = min(8, p["sla"]["maxRuntimeSeconds"], remaining)
        started = time.monotonic()
        out = _post(worker + "/v1/compute",
                    {"leaseId": job["leaseId"], "epochId": job["epochId"], "requestHash": job["requestHash"]},
                    timeout=timeout, allow_http_local=True)
        after = inspect_container(limits, worker, w["container"], strict_hardening=True,
                                  docker_socket=w["dockerSocket"])
        st.require(before["containerId"] == after["containerId"], "worker changed during execution")
        expected = compute_result(job["leaseId"], job["epochId"], job["requestHash"])
        if out != expected:
            return {"state": "WORKER_MISMATCH", "finishedAt": int(time.time())}
        if time.time() > job["responseDeadline"] or time.monotonic() - started > p["sla"]["maxRuntimeSeconds"]:
            return {"state": "MISSED_DEADLINE", "finishedAt": int(time.time())}
        h = response_hash(out)
        st.atomic_write_json(outdir / (h + ".json"), out)
        return {"state": "DONE", "responseHash": h, "finishedAt": int(time.time()),
                "resourceObservation": {"before": before, "after": after,
                                        "elapsedSeconds": time.monotonic() - started,
                                        "trustedHardwareAttestation": False}}

    return run


def make_prober(policy, reader_factory, state_dir):
    cfg = policy.get("monitor", {})
    endpoints = {k.lower(): v for k, v in cfg.get("providerEndpoints", {}).items()}
    services = {k.lower(): v for k, v in cfg.get("services", {}).items()}
    policies = {k.lower(): v for k, v in cfg.get("approvedPolicies", {}).items()}
    evdir = st.private_dir(Path(state_dir) / "evidence")
    me = policy["wallet"]

    def probe(snapshot, now):
        results = []
        for lid, b in snapshot["leases"].items():
            if me not in b.get("members", []) or b["phase"] != "Active":
                continue
            l = b["lease"]
            for e in b["epochs"]:
                v = e["votes"]
                done = evdir / f"{lid}-{e['id']}.json"
                if not v["exists"] or v["monitoringSealed"] or now > v["monitoringClose"]:
                    continue
                approved = policies.get(l["policyHash"])
                policy_ok = isinstance(approved, dict) and response_hash(approved) == l["policyHash"] and approved.get("probe") == "SHA256_CHAIN_8192"
                if done.exists():
                    # Durable evidence survives crash or gas-cap refusal.
                    record = st.read_json(done)
                    st.require(record["leaseId"] == lid and record["epochId"] == e["id"] and
                               record["monitor"] == me and record.get("policyHash") == l["policyHash"] and
                               record.get("requestHash") == v["requestHash"], "stored evidence context mismatch")
                    if record["verdict"] != "inconclusive":
                        st.require(v["responseAuthenticated"] and record.get("onchainResponseHash") == v["responseHash"],
                                   "stored evidence response mismatch")
                    if policy_ok and record["verdict"] != "inconclusive" and (record["verdict"] != "qualified_failure" or
                            (approved.get("failureEvidence") == "conditional-quorum" and l["conditionalQuorumPolicy"] is True)):
                        results.append({"leaseId": lid, "epochId": e["id"], "verdict": record["verdict"],
                                        "reason": record.get("reason"),
                                        "evidenceHash": "0x" + keccak256(canonical(record)).hex()})
                    if record["verdict"] != "inconclusive":
                        continue
                    # Preserve inconclusive attempts separately, then retry.
                    archive = evdir / (done.stem + "-attempt-" + keccak256(canonical(record)).hex() + ".json")
                    st.atomic_write_json(archive, record)
                if not v["responseAuthenticated"] and now <= v["responseDeadline"]:
                    continue  # wait for the response window
                ep = endpoints.get(l["endpointHash"])
                service = services.get(l["profileHash"])
                record = {"leaseId": lid, "epochId": e["id"], "observedAt": now, "monitor": me,
                          "responseAuthenticated": v["responseAuthenticated"], "service": service,
                          "policyHash": l["policyHash"], "requestHash": v["requestHash"]}
                verdict, reason = "inconclusive", None
                if not policy_ok:
                    reason = "committed monitoring policy not owner-approved"
                elif service != "SHA256_CHAIN_8192" or ep is None or endpoint_hash(ep["url"]) != l["endpointHash"]:
                    reason = "unsupported service or unverified endpoint"
                elif not v["responseAuthenticated"]:
                    reason = "no authenticated response (not proof of violation)"
                else:
                    t0 = time.perf_counter()
                    try:
                        out = _post(ep["url"].rstrip("/") + "/v1/compute",
                                    {"leaseId": lid, "epochId": e["id"], "requestHash": v["requestHash"]},
                                    ca_file=ep.get("caFile"),
                                    timeout=min(approved.get("probeTimeoutSeconds", 8), max(1, v["monitoringClose"] - now)))
                        record["latencyMs"] = round((time.perf_counter() - t0) * 1000, 3)
                        fetched = response_hash(out)
                        expected = compute_result(lid, e["id"], v["requestHash"])
                        record.update(fetchedResponseHash=fetched, onchainResponseHash=v["responseHash"],
                                      observedOutput=out, expectedOutput=expected)
                        if fetched != v["responseHash"]:
                            reason = "fetched output does not match signed response hash"
                        elif out == expected:
                            verdict = "success"
                        elif approved.get("failureEvidence") == "conditional-quorum" and l["conditionalQuorumPolicy"] is True:
                            verdict = "qualified_failure"
                            reason = "signed output differs from deterministic recomputation"
                        else:
                            reason = "signed wrong result, but negative evidence policy not enabled"
                    except Exception as exc:  # noqa: BLE001 - network outcome is uncertainty
                        reason = "probe error: " + type(exc).__name__
                record.update(verdict=verdict, reason=reason)
                raw = canonical(record)
                st.atomic_write_json(done, record)
                results.append({"leaseId": lid, "epochId": e["id"], "verdict": verdict, "reason": reason,
                                "evidenceHash": "0x" + keccak256(raw).hex()})
        return results

    return probe
