#!/usr/bin/env python3
"""WP-16: real Anvil + distinct consumer/orchestrator, provider and monitor OS processes.

All three roles run on ONE host. Injects bounded delay, HTTP 503, offline
endpoint, bad provider signature and unauthorized monitor cases; no negative
consumer-delivery inference or automatic monetary settlement is permitted.
"""
from __future__ import annotations

from contextlib import closing
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, ProxyHandler, build_opener

from wp15_anvil_v2_e2e import LiveAnvil, run as prepare_anvil
from sse_chain_read import LocalRPC
from sse_evidence_wire_v1 import EvidenceScope, EvidenceError
from sse_v2_chain_authority_v1 import V2AuthoritySpec, V2AuthorityError, read_v2_authority
from sse_v2_provenance_archive_v1 import V2ProvenanceArchive

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHAIN = 31337


def _address_key(account) -> str:
    return "0x" + bytes(account.key).hex()


def _service_wait(root: str, process: subprocess.Popen) -> None:
    url = root + "/healthz"
    opener = build_opener(ProxyHandler({}))
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("provider child exited before health check")
        try:
            with opener.open(Request(url, method="GET"), timeout=0.3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.1)
    raise RuntimeError("provider child did not become ready on loopback")


def _monitor_case(manifest_path: Path, archive_path: Path, anvil: LiveAnvil,
                  *, case: str, nonce_no: int, monitor_index: int,
                  provider_mode: str | None, provider_index: int = 1,
                  delay: float = 0, request_timeout: float = 0.6,
                  expected: str, expected_error: str | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest["serviceRoot"]
    port = int(root.rsplit(":", 1)[1])
    provider = None
    service_pid = None
    try:
        if provider_mode is not None:
            service_env = os.environ.copy()
            service_env["SSE_WP16_LAB_PROVIDER_KEY"] = _address_key(anvil.accounts[provider_index])
            cmd = [
                sys.executable,
                str(ROOT / "services/provider-agent/wp16_fault_provider.py"),
                "--port", str(port), "--chain-id", str(EXPECTED_CHAIN),
                "--controller", manifest["controller"],
                "--lease-id", str(manifest["leaseId"]),
                "--epoch-id", str(manifest["epochId"]),
                "--request-hash", manifest["requestHash"],
                "--mode", provider_mode, "--delay-seconds", str(delay),
            ]
            provider = subprocess.Popen(cmd, cwd=ROOT, env=service_env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            service_pid = provider.pid
            _service_wait(root, provider)

        monitor_env = os.environ.copy()
        monitor_env["SSE_WP16_LAB_MONITOR_KEY"] = _address_key(
            anvil.accounts[monitor_index])
        monitor_cmd = [
            sys.executable,
            str(ROOT / "services/monitor-agent/wp16_v2_monitor.py"),
            "--rpc-url", "http://127.0.0.1:8545",
            "--manifest", str(manifest_path),
            "--archive", str(archive_path),
            "--nonce", "0x" + format(nonce_no, "064x"),
            "--timeout", str(request_timeout),
        ]
        done = subprocess.run(monitor_cmd, cwd=ROOT, env=monitor_env, text=True,
                              capture_output=True, timeout=12, check=False)
        try:
            response = json.loads(done.stdout.strip())
        except (ValueError, TypeError) as exc:
            raise AssertionError(
                f"monitor child returned no JSON for {case}; rc={done.returncode}; "
                f"stderr={done.stderr[-700:]}") from exc

        if (done.returncode != (0 if expected == "success" else 2) or
                response.get("status") != expected or
                (expected_error is not None and response.get("errorClass") != expected_error)):
            raise AssertionError(
                f"unexpected monitor behavior in {case}: rc={done.returncode}, "
                f"result={response}, stderr={done.stderr[-500:]}")
        if response["pid"] in (os.getpid(), service_pid):
            raise AssertionError("provider/monitor/consumer did not run as distinct OS processes")
        if int(response["archiveCount"]) < 0:
            raise AssertionError("invalid archive count")
        if anvil.read_uint(manifest["controller"], "withdrawable(address)",
                           (int(manifest["provider"], 16),)) != 0:
            raise AssertionError("monitor observation/fault caused forbidden provider payout")
        return {
            "name": case, "status": response["status"],
            "errorClass": response.get("errorClass"),
            "elapsedMs": response["elapsedMs"],
            "archiveCount": response["archiveCount"],
            "providerPid": service_pid, "monitorPid": response["pid"],
            "consumerPid": os.getpid(),
            "entryId": response.get("entryId"),
            "signer": response.get("signer"),
            "providerCreditedFromRaw": 0,
        }
    finally:
        if provider is not None:
            provider.terminate()
            try:
                provider.wait(timeout=3)
            except subprocess.TimeoutExpired:
                provider.kill()
                provider.wait(timeout=3)


def _spec(m: dict) -> V2AuthoritySpec:
    scope = EvidenceScope(m["chainId"], m["controller"], m["leaseId"],
                          m["epochId"], m["slaPolicyHash"],
                          m["resourceProfileHash"], m["requestHash"])
    return V2AuthoritySpec(scope, m["pool"], m["serviceRoot"],
                           m["controllerCodeHash"], m["poolCodeHash"],
                           "latest", True)


def run(url: str, output: Path) -> dict:
    if url != "http://127.0.0.1:8545":
        raise ValueError("WP16 runs only on local Anvil port 8545")
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        manifest_path = scratch / "deployment.json"
        manifest = prepare_anvil(url, manifest_path, prepare_only=True)
        anvil = LiveAnvil(url)
        selected = manifest["selectedMonitors"]
        accounts = {addr: i for i, addr in enumerate(anvil.addresses)}
        if len(selected) != 4 or len(set(selected)) != 4:
            raise AssertionError("unexpected active V2 committee")
        selected_a = accounts[selected[0]]
        selected_b = accounts[selected[1]]
        archive_path = scratch / "v2-evidence.sqlite"
        V2ProvenanceArchive(archive_path)
        archive = V2ProvenanceArchive(archive_path)
        observations = []

        scenarios = [
            dict(case="healthy", nonce_no=1, monitor_index=selected_a,
                 provider_mode="healthy",
                 expected="RAW_OBSERVATION_ARCHIVED_NOT_QUALIFIED"),
            dict(case="delayed_timeout", nonce_no=2, monitor_index=selected_a,
                 provider_mode="delay", delay=1.6, request_timeout=0.35,
                 expected="REJECTED_RAW_NO_PAYOUT", expected_error="TransportFailure"),
            dict(case="http_503", nonce_no=3, monitor_index=selected_a,
                 provider_mode="http503",
                 expected="REJECTED_RAW_NO_PAYOUT", expected_error="TransportFailure"),
            dict(case="provider_offline", nonce_no=4, monitor_index=selected_a,
                 provider_mode=None,
                 expected="REJECTED_RAW_NO_PAYOUT", expected_error="TransportFailure"),
            dict(case="wrong_provider_signature", nonce_no=5, monitor_index=selected_a,
                 provider_mode="healthy", provider_index=11,
                 expected="REJECTED_RAW_NO_PAYOUT",
                 expected_error="ProviderResponseInvalid"),
            dict(case="unselected_monitor", nonce_no=6, monitor_index=10,
                 provider_mode="healthy",
                 expected="REJECTED_RAW_NO_PAYOUT", expected_error="AuthenticationError"),
            dict(case="recovered_selected_monitor", nonce_no=7, monitor_index=selected_b,
                 provider_mode="healthy",
                 expected="RAW_OBSERVATION_ARCHIVED_NOT_QUALIFIED"),
        ]
        expected_counts = [1, 1, 1, 1, 1, 1, 2]
        for args, count in zip(scenarios, expected_counts):
            observation = _monitor_case(manifest_path, archive_path, anvil, **args)
            if observation["archiveCount"] != count or archive.count() != count:
                raise AssertionError("fault or unauthorized signer changed archive rows")
            observations.append(observation)

        spec = _spec(manifest)
        good = [x for x in observations if x["entryId"]]
        if len(good) != 2:
            raise AssertionError("expected exactly two valid selected monitor observations")
        for event in good:
            verified = archive.load_verified(LocalRPC(url), spec, event["entryId"])
            if verified.signer != event["signer"]:
                raise AssertionError("historical evidence signer mismatch")

        service_end = anvil.read_uint(
            manifest["pool"], "serviceDeadline(uint256)",
            (manifest["assignmentId"],))
        anvil.warp_after(service_end)
        anvil.send(0, manifest["pool"], "expire(uint256)",
                   ["uint256"], [manifest["assignmentId"]])
        anvil.send(0, manifest["controller"], "endAdmissions(uint256)",
                   ["uint256"], [manifest["leaseId"]])
        try:
            read_v2_authority(LocalRPC(url), spec)
        except V2AuthorityError:
            pass
        else:
            raise AssertionError("current committee still falsely authorizes an expired epoch")
        for event in good:
            verified = archive.load_verified(LocalRPC(url), spec, event["entryId"])
            if verified.signer != event["signer"]:
                raise AssertionError("archived historic evidence lost authorization")

        # Tamper a signed provider byte and ensure the original pinned Anvil
        # chain reference never lets that altered evidence authenticate.
        first_id = good[0]["entryId"]
        with closing(sqlite3.connect(archive_path)) as db:
            original = db.execute(
                "SELECT provider_bytes FROM v2_observations WHERE entry_id=?",
                (first_id,)).fetchone()[0]
            with db:
                db.execute(
                    "UPDATE v2_observations SET provider_bytes=? WHERE entry_id=?",
                    (b"{}", first_id))
        try:
            archive.load_verified(LocalRPC(url), spec, first_id)
        except EvidenceError:
            pass
        else:
            raise AssertionError("tampered evidence accepted by historical Anvil state")
        with closing(sqlite3.connect(archive_path)) as db:
            with db:
                db.execute("UPDATE v2_observations SET provider_bytes=? WHERE entry_id=?",
                           (original, first_id))
        archive.load_verified(LocalRPC(url), spec, first_id)
        if anvil.read_uint(manifest["controller"], "withdrawable(address)",
                           (int(manifest["provider"], 16),)) != 0:
            raise AssertionError("provider credited from raw monitoring or injected faults")

        report = {
            "schema": "sse-wp16-multiprocess-local-fault-lab-v1",
            "chainId": EXPECTED_CHAIN, "sameHost": True,
            "separateOsProcesses": True,
            "consumerPid": os.getpid(), "providerAndMonitorPidsDistinct": True,
            "eightRegistered": True, "fourSelected": True,
            "leaseId": manifest["leaseId"], "assignmentId": manifest["assignmentId"],
            "selectedMonitors": selected,
            "scenarioCount": len(observations), "observations": observations,
            "archivedSignedRawCount": archive.count(),
            "historicalBlockReverifiedAfterClosure": True,
            "tamperedBytesRejected": True, "providerCreditedFromRaw": 0,
            "realVRFProof": False, "consumerDeliveryProven": False,
            "wanExperiment": False, "independentConsensusProof": False,
            "qualifiedEvidence": False,
            "receiptCount": len(anvil.receipts),
            "txReceipts": manifest["txReceipts"] + anvil.receipts,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                          encoding="utf-8")
        return report


def main():
    p = argparse.ArgumentParser(description="WP16 real Anvil + separate process failure experiment")
    p.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    p.add_argument("--output", default="artifacts/wp16-multiprocess-faults.json")
    args = p.parse_args()
    result = run(args.rpc_url, Path(args.output))
    print(json.dumps({
        "status": "PASSED_LOCAL_MULTIPROCESS_FAULT_LAB",
        "cases": result["scenarioCount"],
        "signedRawRecords": result["archivedSignedRawCount"],
        "providerCreditedFromRaw": result["providerCreditedFromRaw"],
        "historicReverified": result["historicalBlockReverifiedAfterClosure"],
        "realVRFProof": False, "WAN": False,
        "trace": args.output,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
