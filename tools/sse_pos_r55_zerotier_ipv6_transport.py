#!/usr/bin/env python3
"""R55: REAL controllerless ZeroTier IPv6 TCP+UDP cross-host proof.

Only on a participant that has already joined ff2328775f000000.
No Docker, EL, CL, validator, genesis, JWT, sysctl or firewall changes.
Server binds ONLY that machine's own ad-hoc 6plane IPv6, never :: or IPv4.
Client checks an EXPLICIT remote 6plane IPv6, with real packet roundtrips.
Important official ZeroTier ad-hoc spec: UDP is filtered by DESTINATION
port both directions. Bind UDP client source 29002 so response can arrive;
don't use an ephemeral >30303 source port! TCP SYN to server port 29000.
Research helper, not proof of Ethereum sync, independence or overlay SLA.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import selectors
import socket
import subprocess
import sys
import time
from pathlib import Path

NETWORK = "ff2328775f000000"
ZERO_PREFIX = ipaddress.IPv6Network("fca0::/16")
TCP_PORT = 29000
UDP_PORT = 29001
UDP_CLIENT_PORT = 29002
PROBE = b"SSE_R55_GENUINE_ADHOC_IPV6_PROBE_31340"
ACK = b"SSE_R55_GENUINE_ADHOC_IPV6_ACK_31340"
MAX_DURATION = 600

class R55Refused(ValueError):
    pass

def guarded_ip(value: str) -> str:
    try:
        ip = ipaddress.IPv6Address(value)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise R55Refused("expected valid pure IPv6 6plane overlay address") from exc
    if ip not in ZERO_PREFIX or ip.is_multicast:
        raise R55Refused("IPv6 target is not ZeroTier ad-hoc 6plane fca0::/16")
    return str(ip)

def cli_json(*args: str):
    try:
        proc = subprocess.run(["sudo", "-n", "zerotier-cli", "-j", *args],
                              capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise R55Refused("ZeroTier CLI not available without operator password") from exc
    if proc.returncode != 0:
        raise R55Refused("ZeroTier CLI command unsuccessful")
    try:
        return json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise R55Refused("ZeroTier CLI did not return valid JSON") from exc

def membership() -> dict:
    nets = cli_json("listnetworks")
    if not isinstance(nets, list):
        raise R55Refused("unexpected ZeroTier network list")
    candidates = [n for n in nets if isinstance(n, dict) and n.get("nwid") == NETWORK]
    if len(candidates) != 1:
        raise R55Refused("not joined to exact controllerless ad-hoc network")
    n = candidates[0]
    if n.get("status") != "OK" or n.get("type") != "PUBLIC":
        raise R55Refused("network not OK and PUBLIC")
    addresses = n.get("assignedAddresses")
    if not isinstance(addresses, list):
        raise R55Refused("no assigned IPv6 addresses")
    local = None
    for addr in addresses:
        try:
            candidate = ipaddress.ip_interface(str(addr)).ip
            local = guarded_ip(str(candidate))
            break
        except (R55Refused, ValueError):
            continue
    if not local:
        raise R55Refused("no valid assigned controllerless 6plane IPv6")
    return {
        "localOverlayIpv6": local,
        "zeroTierInterface": n.get("portDeviceName"),
        "networkId": NETWORK,
        "networkIsPublicControllerless": True,
    }

def plan() -> dict:
    info = membership()
    return {
        "schema": "SSE_R55_ZERO_TIER_OPEN_OVERLAY_REAL_TCP_UDP_PREFLIGHT_V1",
        **info,
        "serverTcp": TCP_PORT,
        "serverUdp": UDP_PORT,
        "clientBoundUdpSource": UDP_CLIENT_PORT,
        "zeroTierAdHocAllowedPortRange": "9000..30303",
        "noHostOrBlockchainChange": True,
        "actualCrossHostTcpUdpObserved": False,
        "realBesuOrLighthousePeerHandshakeObserved": False,
    }

def server() -> dict:
    me = plan()
    ip = me["localOverlayIpv6"]
    sel = selectors.DefaultSelector()
    t = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    u = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    tcp_count = udp_count = 0
    try:
        t.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        u.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.bind((ip, TCP_PORT))
        t.listen(3)
        t.setblocking(False)
        u.bind((ip, UDP_PORT))
        u.setblocking(False)
        sel.register(t, selectors.EVENT_READ, "tcp")
        sel.register(u, selectors.EVENT_READ, "udp")
        print(json.dumps({**me, "mode": "ephemeral_ipv6_echo_server",
                          "serverBoundOnlyToAssignedOverlayIpv6": True,
                          "timeoutSeconds": MAX_DURATION}), flush=True)
        deadline = time.monotonic() + MAX_DURATION
        while time.monotonic() < deadline and (tcp_count == 0 or udp_count == 0):
            for event, _ in sel.select(timeout=1):
                if event.data == "tcp":
                    client, remote = t.accept()
                    with client:
                        client.settimeout(3)
                        try:
                            if client.recv(256) == PROBE:
                                client.sendall(ACK)
                                tcp_count += 1
                        except OSError:
                            pass
                else:
                    data, peer = u.recvfrom(256)
                    if data == PROBE:
                        u.sendto(ACK, peer)
                        udp_count += 1
        return {
            "schema": "SSE_R55_REAL_ADHOC_IPV6_OVERLAY_ECHO_SERVER_RESULT_V1",
            "realRemoteTcpRequestReceived": tcp_count > 0,
            "realRemoteUdpRequestReceived": udp_count > 0,
            "bothTransportRequestsReceived": tcp_count > 0 and udp_count > 0,
            "actualIndependentISPNotProvenByServer": True,
            "EthereumP2PFinalityNotProven": True,
        }
    finally:
        sel.close()
        t.close()
        u.close()

def client(peer: str) -> dict:
    me = plan()
    ip = guarded_ip(peer)
    if ip == me["localOverlayIpv6"]:
        raise R55Refused("self-target is not real cross-machine traffic")
    tcp_ok = udp_ok = False
    tcp_rtt_ms = udp_rtt_ms = None
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as t:
        t.settimeout(7)
        try:
            stamp = time.monotonic()
            t.connect((ip, TCP_PORT))
            t.sendall(PROBE)
            tcp_ok = t.recv(256) == ACK
            if tcp_ok:
                tcp_rtt_ms = round(1000 * (time.monotonic() - stamp), 2)
        except OSError:
            pass
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as u:
        u.settimeout(7)
        try:
            u.bind((me["localOverlayIpv6"], UDP_CLIENT_PORT))
            stamp = time.monotonic()
            u.sendto(PROBE, (ip, UDP_PORT))
            data, remote = u.recvfrom(256)
            udp_ok = data == ACK and remote[0] == ip and remote[1] == UDP_PORT
            if udp_ok:
                udp_rtt_ms = round(1000 * (time.monotonic() - stamp), 2)
        except OSError:
            pass
    return {
        "schema": "SSE_R55_REAL_CONTROLLERLESS_IPV6_UNICAST_TCP_UDP_RESULT_V1",
        "localNodeOverlayIpv6": me["localOverlayIpv6"],
        "remoteNodeOverlayIpv6": ip,
        "realRemoteTcpPayloadRoundTrip": tcp_ok,
        "realRemoteUdpPayloadRoundTrip": udp_ok,
        "realBothTransportPayloadRoundTrips": tcp_ok and udp_ok,
        "tcpRttMs": tcp_rtt_ms,
        "udpRttMs": udp_rtt_ms,
        "udpReplyDestinationPortWithinNetworkPolicy": UDP_CLIENT_PORT,
        "independentPhysicalNetworkNotAttestedByTool": True,
        "noEthereumClientPeerOrConsensusClaimed": True,
    }

def main() -> int:
    p=argparse.ArgumentParser(description="R55 zero-change real ad-hoc IPv6 TCP+UDP cross-host check")
    opt=p.add_mutually_exclusive_group(required=True)
    opt.add_argument("--plan",action="store_true")
    opt.add_argument("--server",action="store_true")
    opt.add_argument("--check",metavar="REMOTE_6PLANE_IPV6")
    args=p.parse_args()
    try:
        result = plan() if args.plan else server() if args.server else client(args.check)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        if args.server:
            return 0 if result["bothTransportRequestsReceived"] else 2
        if args.check:
            return 0 if result["realBothTransportPayloadRoundTrips"] else 2
        return 0
    except (R55Refused, OSError, KeyboardInterrupt):
        print("R55_REAL_IPV6_OVERLAY_TEST_REFUSED_OR_INTERRUPTED",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
