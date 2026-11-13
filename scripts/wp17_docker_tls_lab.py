#!/usr/bin/env python3
"""WP-17: Docker bridge-isolated TLS provider/monitor + actual V2 Anvil RPC.

A single ephemeral GitHub runner still administers ALL roles; this proves
separate container network namespaces and certificate-verified provider
transport, NOT independent cloud operators or physical service delivery.

LAB-ONLY: the Anvil mnemonic and unlocked keys are publicly known.
No production contracts, TLS credentials, funds or archives are used.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from wp15_anvil_v2_e2e import LiveAnvil, run as prepare
from sse_chain_read import LocalRPC
from sse_evidence_wire_v1 import EvidenceError, EvidenceScope
from sse_v2_chain_authority_v1 import V2AuthoritySpec, V2AuthorityError, read_v2_authority
from sse_v2_provenance_archive_v1 import V2ProvenanceArchive

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "sse-wp17-lab"
CHAIN_ID = 31337
RPC_URL = "http://127.0.0.1:8545"


def _exec(cmd: list[str], *, timeout: int = 30, check: bool = True):
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout,
                          check=False)
    if check and proc.returncode:
        # Never print potentially sensitive docker command arguments (keys).
        raise RuntimeError(
            f"WP17 command {cmd[0]} {cmd[1] if len(cmd)>1 else ''} "
            f"failed (code {proc.returncode}): {proc.stderr[-500:]}")
    return proc


def _docker(*args: str, timeout: int = 30, check: bool = True):
    return _exec(["docker", *map(str, args)], timeout=timeout, check=check)


def _cert(folder: Path, prefix: str) -> tuple[Path, Path]:
    crt = folder / (prefix + ".crt")
    key = folder / (prefix + ".key")
    proc = _exec([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256",
        "-nodes", "-days", "1",
        "-keyout", str(key), "-out", str(crt),
        "-subj", "/CN=provider.wp17",
        "-addext", "subjectAltName=DNS:provider.wp17",
    ], timeout=30)
    key.chmod(0o600)
    return crt, key


def _source_key(account) -> str:
    return "0x" + bytes(account.key).hex()


def _provider_start(network: str, name: str, provider_dir: Path,
                    manifest: dict, provider_key: str,
                    *, mode: str, delay: float = 0.0,
                    untrusted_cert: bool = False) -> str:
    path = "untrusted" if untrusted_cert else "trusted"
    command = [
        "docker", "run", "--detach", "--rm",
        "--name", name, "--network", network,
        "--network-alias", "provider.wp17",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{provider_dir.resolve()}:/secrets:ro",
        "-e", "SSE_WP17_CONTAINER_LAB=yes",
        "-e", f"SSE_WP17_LAB_PROVIDER_KEY={provider_key}",
        IMAGE, "python", "services/provider-agent/wp17_tls_provider.py",
        "--chain-id", "31337",
        "--controller", manifest["controller"],
        "--lease-id", str(manifest["leaseId"]),
        "--epoch-id", str(manifest["epochId"]),
        "--request-hash", manifest["requestHash"],
        "--cert", f"/secrets/{path}.crt",
        "--key", f"/secrets/{path}.key",
        "--mode", mode, "--delay-seconds", str(delay),
    ]
    cid = _exec(command, timeout=30).stdout.strip()
    if len(cid) < 12:
        raise RuntimeError("Docker provider startup did not return container ID")

    # A healthy HTTPS endpoint inside the provider namespace proves the
    # service is listening; it does not grant the monitor trust in its cert.
    readiness_script = (
        "import ssl,urllib.request,time;"
        f"c=ssl.create_default_context(cafile='/secrets/{path}.crt');"
        "op=urllib.request.build_opener(urllib.request.ProxyHandler({}),"
        "urllib.request.HTTPSHandler(context=c));"
        "u=op.open('https://provider.wp17:9443/healthz',timeout=2);"
        "assert u.status==200"
    )
    for _ in range(40):
        check = _docker("exec", name, "python", "-c", readiness_script,
                        check=False, timeout=8)
        if check.returncode == 0:
            return cid
        time.sleep(0.15)
    raise RuntimeError("TLS provider never became ready inside its network namespace")


def _stop_provider(name: str):
    _docker("rm", "--force", name, timeout=15, check=False)


def _case(network: str, manifest: dict, monitor_dir: Path, provider_dir: Path,
          anvil: LiveAnvil, *, index: int, label: str,
          monitor_idx: int, provider_idx: int = 1,
          mode: str = "healthy", delay: float = 0.0,
          tls_mismatch: bool = False, partition: bool = False,
          timeout: float = 0.7, expect_error: str | None = None) -> dict:
    provider_name = f"{network}-provider"
    provider_cid = None
    disconnected = False
    archive = V2ProvenanceArchive(monitor_dir / "evidence.sqlite")
    try:
        provider_cid = _provider_start(
            network, provider_name, provider_dir, manifest,
            _source_key(anvil.accounts[provider_idx]), mode=mode,
            delay=delay, untrusted_cert=tls_mismatch)

        if partition:
            _docker("network", "disconnect", network, provider_name)
            disconnected = True

        cidfile = monitor_dir / f"monitor-{index}.cid"
        command = [
            "docker", "run", "--rm", "--cidfile", str(cidfile),
            "--network", network,
            "--add-host", "host.docker.internal:host-gateway",
            "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{monitor_dir.resolve()}:/lab",
            "-e", "SSE_WP17_CONTAINER_LAB=yes",
            "-e", "SSE_WP16_LAB_MONITOR_KEY=" + _source_key(anvil.accounts[monitor_idx]),
            IMAGE, "python", "services/monitor-agent/wp17_container_monitor.py",
            "--manifest", "/lab/manifest.json",
            "--archive", "/lab/evidence.sqlite",
            "--nonce", "0x" + format(index, "064x"),
            "--timeout", str(timeout),
            "--ca-cert", "/lab/trusted.crt",
        ]
        result = _exec(command, timeout=35, check=False)
        try:
            response = json.loads(result.stdout.strip())
        except (ValueError, TypeError) as exc:
            raise AssertionError(
                f"{label}: monitor container returned no JSON; "
                f"exit={result.returncode} stderr={result.stderr[-600:]}") from exc

        expected_status = (
            "RAW_OBSERVATION_ARCHIVED_NOT_QUALIFIED" if expect_error is None
            else "REJECTED_RAW_NO_PAYOUT"
        )
        if (result.returncode != (0 if expect_error is None else 2) or
                response.get("status") != expected_status or
                (expect_error is not None and response.get("errorClass") != expect_error)):
            raise AssertionError(
                f"{label}: unexpected exit/status from monitor container: "
                f"code={result.returncode}, response={response}, stderr={result.stderr[-600:]}")
        monitor_cid = cidfile.read_text(encoding="utf-8").strip()
        if not monitor_cid or monitor_cid == provider_cid:
            raise AssertionError("provider and monitor containers are not distinct")
        credit = anvil.read_uint(
            manifest["controller"], "withdrawable(address)",
            (int(manifest["provider"], 16),))
        if credit != 0:
            raise AssertionError("raw network report caused unauthorized provider payout")
        return {
            "case": label, "status": response["status"],
            "errorClass": response.get("errorClass"),
            "elapsedMs": response.get("elapsedMs"),
            "archiveCount": response.get("archiveCount"),
            "entryId": response.get("entryId"),
            "signer": response.get("signer"),
            "distinctContainerIds": True,
            "providerNetworkDisconnected": partition,
            "tlsCertificateMismatch": tls_mismatch,
            "providerCredit": credit,
        }
    finally:
        if disconnected:
            _docker("network", "connect", "--alias", "provider.wp17",
                    network, provider_name, check=False)
        if provider_cid:
            _stop_provider(provider_name)


def _authority_spec(m: dict) -> V2AuthoritySpec:
    scope = EvidenceScope(
        m["chainId"], m["controller"], m["leaseId"], m["epochId"],
        m["slaPolicyHash"], m["resourceProfileHash"], m["requestHash"])
    return V2AuthoritySpec(
        scope, m["pool"], m["serviceRoot"],
        m["controllerCodeHash"], m["poolCodeHash"],
        block_tag="latest", allow_unfinalized=True)


def run(output: Path) -> dict:
    if os.name != "posix" or not shutil.which("docker") or not shutil.which("openssl"):
        raise RuntimeError("WP17 requires Linux/Unix with Docker and OpenSSL")
    anvil = LiveAnvil(RPC_URL)
    anvil.require_lab()
    with tempfile.TemporaryDirectory(prefix="sse-wp17-") as tmp:
        base = Path(tmp)
        provider_dir = base / "provider-private"
        monitor_dir = base / "monitor"
        provider_dir.mkdir(mode=0o700)
        monitor_dir.mkdir(mode=0o700)
        trusted_crt, _ = _cert(provider_dir, "trusted")
        _cert(provider_dir, "untrusted")
        shutil.copyfile(trusted_crt, monitor_dir / "trusted.crt")
        manifest = prepare(RPC_URL, monitor_dir / "manifest.json", prepare_only=True)
        accounts = {v: i for i, v in enumerate(anvil.addresses)}
        selected = manifest["selectedMonitors"]
        if len(selected) != 4 or len(set(selected)) != 4:
            raise AssertionError("WP17 expected four unique V2 monitors")
        selected_a, selected_b = accounts[selected[0]], accounts[selected[1]]
        network = f"sse-wp17-{os.getpid()}"
        _docker("network", "create", "--driver", "bridge", network)
        try:
            cases = [
                dict(label="tls_healthy", monitor_idx=selected_a),
                dict(label="tls_certificate_mismatch", monitor_idx=selected_a,
                     tls_mismatch=True, expect_error="TransportFailure"),
                dict(label="tls_response_timeout", monitor_idx=selected_a,
                     mode="delay", delay=1.5, timeout=0.35,
                     expect_error="TransportFailure"),
                dict(label="tls_http_503", monitor_idx=selected_a,
                     mode="http503", expect_error="TransportFailure"),
                dict(label="wrong_provider_signature", monitor_idx=selected_a,
                     provider_idx=11, expect_error="ProviderResponseInvalid"),
                dict(label="unselected_monitor", monitor_idx=10,
                     expect_error="AuthenticationError"),
                dict(label="docker_network_partition", monitor_idx=selected_a,
                     partition=True, expect_error="TransportFailure"),
                dict(label="tls_recovery_other_monitor", monitor_idx=selected_b),
            ]
            results = []
            archive = V2ProvenanceArchive(monitor_dir / "evidence.sqlite")
            for i, spec in enumerate(cases, start=1):
                result = _case(
                    network, manifest, monitor_dir, provider_dir, anvil,
                    index=i, **spec)
                expected = 1 if i < 8 else 2
                if result["archiveCount"] != expected or archive.count() != expected:
                    raise AssertionError(
                        f"{spec['label']}: failed/rejected case changed the archive")
                results.append(result)

            verified_good = [x for x in results if x["entryId"]]
            if len(verified_good) != 2:
                raise AssertionError("expected two and only two authenticated monitor reports")
            authority = _authority_spec(manifest)
            for item in verified_good:
                original = archive.load_verified(LocalRPC(RPC_URL), authority, item["entryId"])
                if original.signer != item["signer"]:
                    raise AssertionError("real Anvil historical signer binding failed")

            deadline = anvil.read_uint(
                manifest["pool"], "serviceDeadline(uint256)",
                (manifest["assignmentId"],))
            anvil.warp_after(deadline)
            anvil.send(0, manifest["pool"], "expire(uint256)",
                       ["uint256"], [manifest["assignmentId"]])
            anvil.send(0, manifest["controller"], "endAdmissions(uint256)",
                       ["uint256"], [manifest["leaseId"]])
            try:
                read_v2_authority(LocalRPC(RPC_URL), authority)
            except V2AuthorityError:
                pass
            else:
                raise AssertionError("current-state authority accepted an expired committee")
            for item in verified_good:
                archive.load_verified(LocalRPC(RPC_URL), authority, item["entryId"])

            with closing(sqlite3.connect(archive.path)) as conn:
                raw = conn.execute(
                    "SELECT provider_bytes FROM v2_observations WHERE entry_id=?",
                    (verified_good[0]["entryId"],)).fetchone()[0]
                with conn:
                    conn.execute(
                        "UPDATE v2_observations SET provider_bytes=? WHERE entry_id=?",
                        (b"{}", verified_good[0]["entryId"]))
            try:
                archive.load_verified(LocalRPC(RPC_URL), authority,
                                      verified_good[0]["entryId"])
            except EvidenceError:
                pass
            else:
                raise AssertionError("tampered historical provider bytes verified")
            with closing(sqlite3.connect(archive.path)) as conn:
                with conn:
                    conn.execute(
                        "UPDATE v2_observations SET provider_bytes=? WHERE entry_id=?",
                        (raw, verified_good[0]["entryId"]))
            archive.load_verified(LocalRPC(RPC_URL), authority, verified_good[0]["entryId"])

            if anvil.read_uint(
                manifest["controller"], "withdrawable(address)",
                (int(manifest["provider"], 16),)) != 0:
                raise AssertionError("raw authenticated evidence credited the provider")
            fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(
                trusted_crt.read_text(encoding="ascii"))).hexdigest()
            report = {
                "schema": "sse-wp17-docker-tls-bridge-lab-v1",
                "chainId": CHAIN_ID, "singlePhysicalHost": True,
                "containerNetworkNamespaces": True,
                "administrativelyIndependentHosts": False,
                "providerHttpsVerifiedByPinnedCertificate": True,
                "tlsServerCertificateSha256": fingerprint,
                "anvilRpcIndependentlyAuthenticated": False,
                "transportScheme": "loopback HTTP to certificate-checked TLS tunnel",
                "realVRF": False, "physicalDeliveryProven": False,
                "consumerReceiptVerified": False,
                "qualifiedFact": False, "automaticPayout": False,
                "cases": results, "caseCount": len(results),
                "authenticatedRawObservations": archive.count(),
                "historicReverifiedAfterClose": True,
                "tamperedHttpBytesRejected": True,
                "providerCredit": 0,
                "leaseId": manifest["leaseId"],
                "assignmentId": manifest["assignmentId"],
                "selectedMonitors": selected,
                "transactionReceipts": manifest["txReceipts"] + anvil.receipts,
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            return report
        finally:
            _stop_provider(network + "-provider")
            _docker("network", "rm", network, timeout=20, check=False)


def main():
    parser = argparse.ArgumentParser(description="WP17 Docker TLS isolated agent lab")
    parser.add_argument("--output", default="artifacts/wp17-docker-tls-lab.json")
    args = parser.parse_args()
    report = run(Path(args.output))
    print(json.dumps({
        "status": "PASSED_WP17_CONTAINER_TLS_LAB",
        "scenarios": report["caseCount"],
        "signedRawObservations": report["authenticatedRawObservations"],
        "providerCredit": report["providerCredit"],
        "historicalReverified": report["historicReverifiedAfterClose"],
        "independentHosts": False,
        "realVRF": False,
        "trace": args.output,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
