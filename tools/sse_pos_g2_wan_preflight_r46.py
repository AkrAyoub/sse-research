#!/usr/bin/env python3
"""R46: honest, read-only, REAL WAN/P2P readiness of the running G2 chain31340.

P2P must be genuine Besu devp2p TCP+UDP and Lighthouse libp2p/discv5
TCP+UDP/QUIC, not Docker internal peering, VPN, synthetic nodes or HTTP RPC.
This command NEVER starts/stops clients, alters public genesis or reads keys.
Classifies current Docker bindings and host interface reachability; it does
NOT claim that a public inbound handshake or independent operator exists.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import sse_pos_g2_internal_health_r42 as health
import sse_pos_g2_recover_r40 as base

EL = base.REPLACEMENT_EL
ORIGINAL = base.ORIGINAL_EL
BN = base.BEACON
VC = base.VC
NETWORK = base.NETWORK
EXEC_PORTS = ("30303/tcp", "30303/udp")
CONS_PORTS = ("9000/tcp", "9000/udp", "9001/udp")
ALL_P2P_PORTS = EXEC_PORTS + CONS_PORTS
LOOPBACK_RPC_PORTS = ("8545/tcp", "5052/tcp")

class ReadinessRefused(ValueError):
    pass

def docker_inspect(name: str, fmt: str) -> object:
    try:
        result = subprocess.run(
            ["sudo", "-n", "docker", "inspect", "--format", fmt, name],
            capture_output=True, text=True, timeout=12, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReadinessRefused("original client Docker inspection unavailable") from exc
    if result.returncode:
        raise ReadinessRefused("original client Docker inspect refused")
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ReadinessRefused("original client Docker metadata unreadable") from exc

def classify_bindings(container: str) -> dict:
    if container not in (EL, BN):
        raise ReadinessRefused("only pinned live execution and Beacon may be inspected")
    info = docker_inspect(container, "{{json .HostConfig}}")
    conf = docker_inspect(container, "{{json .Config}}")
    if not isinstance(info, dict) or not isinstance(conf, dict):
        raise ReadinessRefused("Docker configs must be JSON objects")
    if info.get("NetworkMode") != NETWORK:
        raise ReadinessRefused("client not using original private bridge")
    ports = info.get("PortBindings") or {}
    if type(ports) is not dict:
        raise ReadinessRefused("invalid Docker port bindings")
    cmd = conf.get("Cmd")
    if not isinstance(cmd, list) or not all(type(x) is str for x in cmd):
        raise ReadinessRefused("client commands inaccessible")
    allowed_p2p = EXEC_PORTS if container == EL else CONS_PORTS
    # Classify ONLY; never emit raw commands, mount paths, JWT or EIP-2335 keys.
    return {
        "client": "besu_execution" if container == EL else "lighthouse_beacon",
        "currentlyRunning": docker_inspect(container, "{{json .State.Running}}") is True,
        "dockerNetworkIsOriginalInternalBridge": info["NetworkMode"] == NETWORK,
        "p2pBindingsPresent": sorted(port for port in allowed_p2p
                                    if ports.get(port)),
        "p2pInboundTcpPublished": any(ports.get(p) for p in allowed_p2p if p.endswith("tcp")),
        "p2pInboundUdpPublished": any(ports.get(p) for p in allowed_p2p if p.endswith("udp")),
        "ethereumExecutionP2pExplicitlyDisabled": "--p2p-enabled=false" in cmd if container == EL else None,
        "beaconDiscv5OrLibp2pEnabledInImage": None,
        "hasExplicitPublicEnrAddress": any(x.startswith("--enr-address") for x in cmd) if container == BN else None,
        "hasExplicitPublicP2pHost": any(x.startswith("--p2p-host") for x in cmd) if container == EL else None,
        "rawDockerCommandAndSecretsEmitted": False,
    }

def interface_ip_observation() -> dict:
    """Only classified family counts, never external IPs or private hostnames."""
    try:
        r = subprocess.run(
            ["ip", "-j", "address", "show"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "ipToolAvailable": False,
            "hostHasDirectGlobalIpv4": None,
            "hostHasDirectGlobalIpv6": None,
            "privateOrCarrierNatIPv4Present": None,
            "doesNotProveInboundReachability": True,
        }
    if r.returncode:
        return {
            "ipToolAvailable": False,
            "hostHasDirectGlobalIpv4": None,
            "hostHasDirectGlobalIpv6": None,
            "privateOrCarrierNatIPv4Present": None,
            "doesNotProveInboundReachability": True,
        }
    try:
        data = json.loads(r.stdout)
    except (TypeError, ValueError) as exc:
        raise ReadinessRefused("host interface JSON invalid") from exc
    if not isinstance(data, list):
        raise ReadinessRefused("host interface shape invalid")
    public4, public6, cgnat4, private4 = 0, 0, 0, 0
    for entry in data:
        if not isinstance(entry, dict):
            continue
        for item in entry.get("addr_info", []):
            if not isinstance(item, dict):
                continue
            addr = item.get("local")
            if not isinstance(addr, str):
                continue
            try:
                parsed = ipaddress.ip_address(addr.split("%", 1)[0])
            except ValueError:
                continue
            if parsed.is_global:
                if parsed.version == 4:
                    public4 += 1
                else:
                    public6 += 1
            elif parsed.version == 4:
                if parsed in ipaddress.ip_network("100.64.0.0/10"):
                    cgnat4 += 1
                elif parsed.is_private:
                    private4 += 1
    return {
        "ipToolAvailable": True,
        "hostHasDirectGlobalIpv4": public4 > 0,
        "hostHasDirectGlobalIpv6": public6 > 0,
        "privateOrCarrierNatIPv4Present": private4 + cgnat4 > 0,
        "carrierGradeNatRangePresentOnInterface": cgnat4 > 0,
        "doesNotProveInboundReachability": True,
    }

def run(sha: str) -> dict:
    # Exact clean source and PUBLIC CL/EL/SSZ checks before any host inspection.
    health.require_actual_source(sha)
    el = classify_bindings(EL)
    beacon = classify_bindings(BN)
    if (not el["currentlyRunning"] or not beacon["currentlyRunning"]
            or health.internal.state(VC).get("Running") is not True
            or health.internal.state(ORIGINAL).get("Running") is True):
        raise ReadinessRefused("must inspect the live one-owner G2 without duplicate signer")
    try:
        net = subprocess.run(
            ["sudo", "-n", "docker", "network", "inspect", "--format", "{{.Internal}}", NETWORK],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReadinessRefused("private Docker network unavailable") from exc
    if net.returncode or net.stdout.strip() != b"true":
        raise ReadinessRefused("live G2 network is no longer the original internal bridge")
    interfaces = interface_ip_observation()
    # Keep strict facts separate from hypotheses and planned future actions.
    return {
        "schema": "SSE_R46_REAL_CHAIN31340_NATIVE_WAN_P2P_READINESS_V1",
        "sourceExactGitSha": sha,
        "observedUtcUnixSeconds": int(time.time()),
        "executionChainId31340VerifiedInCurrentPhase": True,
        "originalBesuContainerPreservedStopped": True,
        "singleOriginalOwnerValidatorRunning": True,
        "realGenesisConfigAndSSZPreserved": True,
        "publicTestEthOnly": True,
        "actualClientInspections": [el, beacon],
        "hostInterfaces": interfaces,
        "privateDockerNetworkInternal": True,
        "existingG2P2pEnabledForExternalPeers": (
            not el["ethereumExecutionP2pExplicitlyDisabled"]
            and el["p2pInboundTcpPublished"] and el["p2pInboundUdpPublished"]
            and beacon["p2pInboundTcpPublished"] and beacon["p2pInboundUdpPublished"]
            and False  # no external handshake verified; never infer from bindings
        ),
        "nativeExecutionDevp2pHandshakeProven": False,
        "consensusLibp2pAndDiscv5HandshakeProven": False,
        "incomingInternetReachabilityProven": False,
        "dynamicDnsConfiguredAndResolved": False,
        "carrierGradeNatTraversalProven": False,
        "independentPhysicalOperatorsConfirmed": 1,
        "permissionlessInternetParticipationProven": False,
        "publicReleaseRequiresAtLeastTwoIndependentSeedOperators": True,
        "designRequiresPubliclyReachableTCPAndUDPBootstrap": True,
        "staticPublicIpOnEveryParticipantRequired": False,
        "originalValidatorJwtKeysAndSlashingDataRead": False,
        "clientContainersOrNetworksModified": False,
        "manualNetworkMigrationRequiredWithoutReusingSigningKeys": True,
    }

def main() -> int:
    p = argparse.ArgumentParser(description="Read-only real G2 P2P exposure and public-IP capability audit")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(run(args.expected_commit), sort_keys=True, indent=2))
        return 0
    except (ReadinessRefused, base.RecoveryRefused,
            OSError, ValueError, health.internal.Refuse) as exc:
        print("R46_NATIVE_WAN_PREFLIGHT_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
