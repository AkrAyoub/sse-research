#!/usr/bin/env python3
"""R50: original-owner VM4706 REAL outbound/NAT feasibility before public peering.

WHY: owner has only private addresses and may provision MORE private VMs, but
no globally reachable public EL/CL P2P seed yet. Never claim that outbound NAT
or more VMs is equivalent to public permissionless TCP+UDP peering.

--plan: only existing read-only Docker/chain + host network metadata.
--probe-outbound: EXPLICIT opt-in to two real egress probes:
  (1) TCP connect to Cloudflare 1.1.1.1:443 (NO HTTP request);
  (2) RFC 5389 STUN Binding request to stun.l.google.com:19302/UDP.
Third parties necessarily learn the VM's outbound NAT address. No raw address,
mapped port, Docker argument, engine JWT or validator key is ever printed.
No Docker/container/filesystem changes, no signer stop/restart.
STUN only classifies outbound NAT mapping, NEVER proves native inbound P2P,
port forwarding, CGNAT traversal or Ethereum handshakes.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import struct
import sys
import time

import sse_pos_g2_wan_preflight_r46 as owner

MAGIC = 0x2112A442
TCP_ENDPOINT = ("1.1.1.1", 443)
STUN_ENDPOINT = ("stun.l.google.com", 19302)
MAX_RESPONSE = 1024

class EgressRefused(ValueError):
    pass

def unpack_stun(packet: bytes, txid: bytes) -> dict:
    """Parse only transaction-bound RFC5389 XOR-MAPPED-ADDRESS, never emit it."""
    result = {
        "validStunBindingSuccess": False,
        "outboundMappedGlobalIPv4Observed": False,
        "outboundMappedGlobalIPv6Observed": False,
        "rawExternalAddressOrPortEmitted": False,
        "nativeP2pInboundReachabilityProven": False,
    }
    if (len(txid) != 12 or not 20 <= len(packet) <= MAX_RESPONSE
            or len(packet) % 4 != 0):
        return result
    kind, length, cookie = struct.unpack_from("!HHI", packet, 0)
    if (kind != 0x0101 or cookie != MAGIC or packet[8:20] != txid
            or length > MAX_RESPONSE - 20 or length % 4
            or len(packet) != length + 20):
        return result
    result["validStunBindingSuccess"] = True
    offset = 20
    while offset < len(packet):
        if offset + 4 > len(packet):
            break
        attr_type, attr_length = struct.unpack_from("!HH", packet, offset)
        offset += 4
        padded = (attr_length + 3) & ~3
        if offset + padded > len(packet):
            break
        value = packet[offset:offset + attr_length]
        offset += padded
        if attr_type != 0x0020 or len(value) not in (8, 20):
            continue
        if value[0] != 0:
            continue
        family = value[1]
        address_size = 4 if family == 1 else 16 if family == 2 else 0
        if address_size == 0 or len(value) != 4 + address_size:
            continue
        obfuscation = MAGIC.to_bytes(4, "big") + txid
        decoded = bytes(a ^ b for a, b in zip(value[4:], obfuscation))
        try:
            ip = ipaddress.ip_address(decoded)
        except ValueError:
            continue
        if ip.is_global:
            if ip.version == 4:
                result["outboundMappedGlobalIPv4Observed"] = True
            else:
                result["outboundMappedGlobalIPv6Observed"] = True
    return result

def tcp_egress() -> dict:
    try:
        with socket.create_connection(TCP_ENDPOINT, timeout=3):
            reachable = True
    except (OSError, TimeoutError):
        reachable = False
    return {
        "endpoint": "Cloudflare_1.1.1.1:443_TCP",
        "tcpConnectionEstablished": reachable,
        "responsePayloadRequested": False,
        "internetNativeExecutionDevp2pConfirmed": False,
    }

def udp_stun_egress() -> dict:
    transaction_id = os.urandom(12)  # Only ephemeral protocol nonce; NEVER a validator key.
    request = struct.pack("!HHI", 0x0001, 0, MAGIC) + transaction_id
    response = None
    resolved = False
    try:
        candidates = socket.getaddrinfo(
            STUN_ENDPOINT[0], STUN_ENDPOINT[1],
            family=socket.AF_INET, type=socket.SOCK_DGRAM
        )
        for family, socktype, protocol, _, sockaddr in candidates[:2]:
            with socket.socket(family, socktype, protocol) as endpoint:
                endpoint.settimeout(3)
                resolved = True
                try:
                    endpoint.sendto(request, sockaddr)
                    packet, remote = endpoint.recvfrom(MAX_RESPONSE + 1)
                except (OSError, TimeoutError):
                    continue
                if remote[0] != sockaddr[0]:
                    continue
                result = unpack_stun(packet, transaction_id)
                if result["validStunBindingSuccess"]:
                    response = result
                    break
    except (OSError, TimeoutError):
        pass
    data = response if response is not None else unpack_stun(b"", transaction_id)
    return {
        "endpoint": "Google_stun.l.google.com:19302_UDP",
        "dnsIPv4ResolutionSucceeded": resolved,
        "bindingResponseReceivedAndMatchedNonce": data["validStunBindingSuccess"],
        "outboundMappedGlobalIPv4Observed": data["outboundMappedGlobalIPv4Observed"],
        "outboundMappedGlobalIPv6Observed": data["outboundMappedGlobalIPv6Observed"],
        "rawExternalAddressOrPortEmitted": False,
        "natTypeOrInboundPortMappingDetermined": False,
        "consensusDiscv5HandshakeObserved": False,
    }

def report(commit: str, probe_outbound: bool) -> dict:
    # R46 verifies genuine live EL chain ID, Beacon genesis, original VC,
    # unchanged SSZ/config and actual unmodified internal-only bridge.
    baseline = owner.run(commit)
    if not baseline["privateDockerNetworkInternal"]:
        raise EgressRefused("original live private bridge changed; refuse owner WAN audit")
    host = baseline["hostInterfaces"]
    output = {
        "schema": "SSE_R50_CHAIN31340_NO_PUBLIC_IP_REAL_NAT_OPTIONS_V1",
        "sourceExactGitSha": commit,
        "ownerG2StillRealChain31340WithOriginalSigner": True,
        "ownerNativeP2pCurrentlyAccessibleOverPublicInternet": False,
        "ownerHostHasDirectGlobalIPv4": host["hostHasDirectGlobalIpv4"],
        "ownerHostHasDirectGlobalIPv6": host["hostHasDirectGlobalIpv6"],
        "ownerHasPrivateOrNatAddresses": host["privateOrCarrierNatIPv4Present"],
        "newVMsBehindSameProviderNatDoNotProveIndependentOperators": True,
        "additionalPrivateVMsCannotAloneProvidePublicInternetIngress": True,
        "staticPublicAddressOnEveryPeerNotRequired": True,
        "publicBootstrapStillNeedsRealReachableNativeTcpAndUdp": True,
        "providerIngressPortForwardingOrGlobalIpv6Capability": "UNKNOWN_NOT_PROBED",
        "actualNativeExternalP2pPeerHandshakeObserved": False,
        "publicNetworkReleaseReady": False,
        "probeOutboundExplicitlyRequested": probe_outbound,
        "probeStatus": "NETWORK_PROBES_EXECUTED" if probe_outbound else "NO_NETWORK_PROBES",
        "rawPublicIpOrMappedPortPrinted": False,
        "originalValidatorKeysJwtOrSlashingDatabaseRead": False,
        "dockerClientsContainersOrFilesModified": False,
        "observedUtcUnixSeconds": int(time.time()),
    }
    if probe_outbound:
        output["tcp"] = tcp_egress()
        output["stun"] = udp_stun_egress()
        output["outboundTcpUdpProvenToCarryNativeEthereumP2p"] = False
    return output

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strict no-public-IP real owner NAT egress audit; no chain modifications"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--probe-outbound", action="store_true")
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(report(args.expected_commit, args.probe_outbound),
                         indent=2, sort_keys=True))
        return 0
    except (EgressRefused, owner.ReadinessRefused, owner.base.RecoveryRefused,
            OSError, ValueError, TimeoutError):
        print("R50_NAT_EGRESS_AUDIT_REFUSED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
