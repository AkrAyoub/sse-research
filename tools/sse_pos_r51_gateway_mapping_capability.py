#!/usr/bin/env python3
"""R51: safe NAT gateway mapping-PROTOCOL discovery for real chain31340.

The owner VM4706 has real outbound TCP and STUN/UDP through NAT, but no
inbound native Ethereum P2P. Before allocating another VM, determine whether
the actual host default GATEWAY supports PCP (RFC6887) and/or NAT-PMP (RFC6886).

--plan: read-only original G2 + OS route metadata, NO network packets.
--probe-gateway: two opt-in, NON-MUTATING UDP inquiries to the local default
IPv4 gateway, UDP/5351 only:
    PCP v2 ANNOUNCE, opcode 0, requested lifetime ZERO (NOT MAP/PEER)
    NAT-PMP v0 public-address, opcode 0 (NOT UDP/TCP port mapping)
Print NO gateway IP, public IP, ports, Docker CLI, credentials or raw packets.
Even successful replies DO NOT create mapping, prove public ingress, or imply
provider policy allows inbound P2P. No Docker changes, keys, genesis edits,
signing, filesystem writes, UPnP configuration, or permanent network listeners.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import struct
import subprocess
import sys
import time

import sse_pos_g2_wan_preflight_r46 as owner

PORT = 5351
PCP_VERSION = 2
PCP_ANNOUNCE_OPCODE = 0
NATPMP_VERSION = 0
NATPMP_PUBLIC_ADDRESS_OPCODE = 0
MAX_REPLY = 1100

class GatewayRefused(ValueError):
    pass

def gateway_route() -> str | None:
    """Only unique private default-route IPv4 gateway, never prints the value."""
    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "route", "show", "default"],
            capture_output=True, text=True, timeout=6, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        routes = json.loads(result.stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(routes, list):
        return None
    unique = set()
    for route in routes:
        if type(route) is not dict or route.get("dst") != "default":
            continue
        name = route.get("gateway")
        if not isinstance(name, str):
            continue
        try:
            addr = ipaddress.IPv4Address(name)
        except ipaddress.AddressValueError:
            continue
        if (addr.is_loopback or addr.is_multicast or addr.is_link_local
                or addr.is_unspecified or addr.is_reserved):
            continue
        # Limit packet destinations to directly connected PRIVATE or CGNAT
        # gateway IPs on the operator's VM. Never probe arbitrary public IPs.
        if (addr.is_private or addr in ipaddress.ip_network("100.64.0.0/10")):
            unique.add(str(addr))
    return next(iter(unique)) if len(unique) == 1 else None

def is_private_source(value: str) -> bool:
    try:
        addr = ipaddress.IPv4Address(value)
    except (ValueError, ipaddress.AddressValueError):
        return False
    return (not addr.is_loopback and not addr.is_multicast
            and not addr.is_unspecified and not addr.is_reserved
            and (addr.is_private or addr in ipaddress.ip_network("100.64.0.0/10")))

def pcp_announce_request(source_ipv4: str) -> bytes:
    if not is_private_source(source_ipv4):
        raise GatewayRefused("PCP source must be local private IPv4")
    # RFC6887 request: version=2, opcode=ANNOUNCE=0,
    # reserved=0, lifetime=0, 128-bit IPv4-mapped IPv6 SOURCE address.
    return (struct.pack("!BBHI", PCP_VERSION, PCP_ANNOUNCE_OPCODE, 0, 0)
            + ipaddress.IPv6Address("::ffff:" + source_ipv4).packed)

def parse_pcp_announce(response: bytes) -> dict:
    ok = (len(response) >= 24 and len(response) <= MAX_REPLY
          and len(response) % 4 == 0 and response[0] == 2
          and response[1] == 0x80)
    result_code = response[3] if ok else None
    return {
        "pcpAnnounceProtocolResponseRecognized": ok,
        "pcpAnnounceSucceededWithoutMapping": result_code == 0 if ok else False,
        "pcpResultCode": result_code,
        "pcpMapOrPeerOpcodeSent": False,
        "pcpGatewayIngressReachabilityProven": False,
    }

def parse_natpmp_public_address(response: bytes) -> dict:
    ok = (len(response) == 12 and response[0] == 0 and response[1] == 0x80)
    code = struct.unpack_from("!H", response, 2)[0] if ok else None
    public_address = None
    if ok and code == 0:
        try:
            public_address = ipaddress.IPv4Address(response[8:12])
        except ValueError:
            public_address = None
    return {
        "natPmpPublicAddressResponseRecognized": ok,
        "natPmpQuerySucceededWithoutMapping": (ok and code == 0),
        "natPmpResultCode": code,
        "natPmpGatewayReportedGlobalIPv4": (
            public_address.is_global if public_address is not None else False
        ),
        "natPmpPortMappingOpcodeSent": False,
        "rawMappedAddressEmitted": False,
        "natPmpGatewayIngressReachabilityProven": False,
    }

def query_gateway(gateway: str) -> dict:
    try:
        parsed = ipaddress.IPv4Address(gateway)
    except (ValueError, ipaddress.AddressValueError) as exc:
        raise GatewayRefused("target not a private IPv4 gateway") from exc
    if not (parsed.is_private or parsed in ipaddress.ip_network("100.64.0.0/10")):
        raise GatewayRefused("never send probes to an arbitrary public IP")
    def single_query(request_type: str) -> bytes:
        # Separate ephemeral UDP sockets: a delayed PCP response cannot be
        # accidentally interpreted as the NAT-PMP public address response.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(2)
            probe.connect((gateway, PORT))
            local = probe.getsockname()[0]
            if not is_private_source(local):
                raise GatewayRefused("local source is not owner private IPv4")
            if request_type == "pcp":
                payload = pcp_announce_request(local)
            elif request_type == "natpmp":
                payload = bytes((NATPMP_VERSION, NATPMP_PUBLIC_ADDRESS_OPCODE))
            else:
                raise GatewayRefused("only metadata-only gateway query allowed")
            probe.send(payload)
            try:
                return probe.recv(MAX_REPLY + 1)
            except (OSError, TimeoutError):
                return b""
    try:
        pcp_response = single_query("pcp")
        natpmp_response = single_query("natpmp")
    except (OSError, TimeoutError) as exc:
        raise GatewayRefused("gateway UDP metadata query inaccessible") from exc
    return {
        "pcp": parse_pcp_announce(pcp_response),
        "natPmp": parse_natpmp_public_address(natpmp_response),
        "exactlyTwoMetadataOnlyUdpQueriesSent": True,
        "allQueriesDirectedOnlyToPrivateDefaultGatewayPort5351": True,
        "neitherPcpMapNorPcpPeerNorNatPmpPortMappingSent": True,
        "actualExternalInternetP2pReachabilityProven": False,
        "noRouterMappingCreatedOrRequested": True,
    }

def report(commit: str, probe: bool) -> dict:
    baseline = owner.run(commit)
    if not baseline["privateDockerNetworkInternal"]:
        raise GatewayRefused("original VM owner network changed")
    gw = gateway_route()
    report = {
        "schema": "SSE_R51_CHAIN31340_PRIVATE_GATEWAY_PCP_NATPMP_READINESS_V1",
        "sourceExactGitSha": commit,
        "observationUnixUtc": int(time.time()),
        "realChain31340AndSingleExistingBlsVCVerifiedByOriginalR46": True,
        "defaultPrivateIpv4GatewayFound": gw is not None,
        "defaultGatewayAddressNeverEmitted": True,
        "probeGatewayExplicitlyRequested": probe,
        "noExternalNetworkTrafficDuringPlan": not probe,
        "noMappingOrNATConfigurationChanged": True,
        "noDockerClientsStartedOrStopped": True,
        "noOriginalValidatorJwtKeysOrSlashingFilesRead": True,
        "noNewVmsCreated": True,
        "nativeInternetInboundTcpUdpProven": False,
        "providerPolicyPermitsActualPortForwarding": "UNKNOWN",
        "permanentOrStaticIpv4RequiredForEveryNode": False,
        "morePrivateVmsAloneProvidePublicBootstrap": False,
    }
    if probe:
        if gw is None:
            report["probeStatus"] = "PRIVATE_DEFAULT_GATEWAY_NOT_DETERMINED"
        else:
            report["probeStatus"] = "TWO_NON_MUTATING_GATEWAY_METADATA_QUERIES_ATTEMPTED"
            report.update(query_gateway(gw))
    else:
        report["probeStatus"] = "READ_ONLY_NO_GATEWAY_PACKETS"
    return report

def main() -> int:
    p = argparse.ArgumentParser(description="Non-mutating real PCP/NAT-PMP gateway discovery")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--probe-gateway", action="store_true")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(report(args.expected_commit, args.probe_gateway),
                         indent=2, sort_keys=True))
        return 0
    except (GatewayRefused, owner.ReadinessRefused,
            owner.base.RecoveryRefused, OSError, ValueError, TimeoutError):
        print("R51_GATEWAY_METADATA_REFUSED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
