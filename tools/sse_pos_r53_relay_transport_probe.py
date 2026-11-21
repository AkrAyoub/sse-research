#!/usr/bin/env python3
"""R53: real TCP+UDP relay smoke-test with ZERO blockchain or Docker changes.

Purpose: determine if an actual third-party PUBLIC raw TCP and UDP relay
carries bidirectional payload between an independent public endpoint and
VM4707's LOCAL loopback. We MUST NOT mistake "tunnel created" for functional
Ethereum devp2p/discv5 connectivity. This is harmless echo traffic only.

Modes:
 --server: bind ONLY 127.0.0.1 TCP 23353 and UDP 23354 for up to 12 min,
          no root, disk writes, Ethereum ports, Docker or private credentials.
 --check:  connect to supplied relay-assigned public TCP/UDP host:port from
          another machine, require exact original probe/response for BOTH.
          Only global IPv4 destinations allowed; no local/private reflection.

This is a test, not an installer, blockchain node, or proof of remote
administrative independence. Do not publish Engine RPC or validator keys.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import selectors
import socket
import sys
import time

TCP_LOCAL_PORT = 23353
UDP_LOCAL_PORT = 23354
REQUEST = b"SSE_R53_PUBLIC_RAW_TRANSPORT_TEST_31340"
REPLY = b"SSE_R53_RAW_TRANSPORT_ACK_31340"
MAX_RUNTIME_SECONDS = 720

class RelayRefused(ValueError):
    pass

def validate_port(port: int) -> int:
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise RelayRefused("relay public port must be 1..65535")
    return port

def public_ips(host: str, port: int, kind: int) -> list[tuple]:
    if not isinstance(host, str) or not host or len(host) > 253:
        raise RelayRefused("public relay host required")
    validate_port(port)
    try:
        values = socket.getaddrinfo(host, port, socket.AF_INET, kind)
    except socket.gaierror as exc:
        raise RelayRefused("relay host cannot resolve globally") from exc
    candidates = []
    for family, socktype, protocol, _, sockaddr in values:
        if family != socket.AF_INET:
            continue
        addr = ipaddress.IPv4Address(sockaddr[0])
        if addr.is_global:
            candidates.append((family, socktype, protocol, sockaddr))
    if not candidates:
        raise RelayRefused("relay resolves only to nonpublic IPv4")
    return candidates[:4]

def serve() -> dict:
    sel = selectors.DefaultSelector()
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tcp_count = udp_count = 0
    try:
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind(("127.0.0.1", TCP_LOCAL_PORT))
        tcp.listen(4)
        tcp.setblocking(False)
        udp.bind(("127.0.0.1", UDP_LOCAL_PORT))
        udp.setblocking(False)
        sel.register(tcp, selectors.EVENT_READ, "tcp")
        sel.register(udp, selectors.EVENT_READ, "udp")
        print(json.dumps({
            "schema": "SSE_R53_LOOPBACK_ONLY_TEST_SERVER_V1",
            "tcpLocalPort": TCP_LOCAL_PORT, "udpLocalPort": UDP_LOCAL_PORT,
            "boundOnlyToLocalLoopback": True,
            "noBlockchainClientsOrDockerCreated": True,
            "maxRunSeconds": MAX_RUNTIME_SECONDS,
            "realPublicInternetReachabilityNotYetProven": True,
        }), flush=True)
        deadline = time.monotonic() + MAX_RUNTIME_SECONDS
        while time.monotonic() < deadline and (tcp_count == 0 or udp_count == 0):
            for event, _ in sel.select(timeout=1):
                if event.data == "tcp":
                    client, _ = tcp.accept()
                    with client:
                        client.settimeout(3)
                        try:
                            payload = client.recv(256)
                            if payload == REQUEST:
                                client.sendall(REPLY)
                                tcp_count += 1
                        except (OSError, TimeoutError):
                            pass
                else:
                    payload, address = udp.recvfrom(256)
                    if payload == REQUEST:
                        udp.sendto(REPLY, address)
                        udp_count += 1
        return {
            "schema": "SSE_R53_RELAY_LOOPBACK_RECEIVER_V1",
            "receivedActualTCPRequests": tcp_count,
            "receivedActualUDPRequests": udp_count,
            "receivedBothTransports": tcp_count > 0 and udp_count > 0,
            "noNativeEthereumPeerHandshakeProven": True,
            "noDockerGenesisJwtValidatorOrKeysTouched": True,
        }
    finally:
        sel.close()
        tcp.close()
        udp.close()

def send_tcp(host: str, port: int) -> bool:
    for family, kind, protocol, sockaddr in public_ips(host, port, socket.SOCK_STREAM):
        try:
            with socket.socket(family, kind, protocol) as sock:
                sock.settimeout(5)
                sock.connect(sockaddr)
                sock.sendall(REQUEST)
                received = sock.recv(256)
                if received == REPLY:
                    return True
        except (OSError, TimeoutError):
            pass
    return False

def send_udp(host: str, port: int) -> bool:
    for family, kind, protocol, sockaddr in public_ips(host, port, socket.SOCK_DGRAM):
        try:
            with socket.socket(family, kind, protocol) as sock:
                sock.settimeout(5)
                sock.sendto(REQUEST, sockaddr)
                received, remote = sock.recvfrom(256)
                if received == REPLY and remote == sockaddr:
                    return True
        except (OSError, TimeoutError):
            pass
    return False

def check(tcp_host: str, tcp_port: int, udp_host: str, udp_port: int) -> dict:
    t = send_tcp(tcp_host, tcp_port)
    u = send_udp(udp_host, udp_port)
    return {
        "schema": "SSE_R53_REAL_PUBLIC_RAW_TCP_UDP_TUNNEL_CHECK_V1",
        "realRemoteTcpEchoRoundTripObserved": t,
        "realRemoteUdpEchoRoundTripObserved": u,
        "bothPublicTransportsActuallyWorked": t and u,
        "externalEndpointMayBeEphemeral": True,
        "noBesuDevp2pOrLighthouseDiscv5HandshakeYet": True,
        "noGenesisJwtBlsValidatorOrDockerTouched": True,
        "operatorIndependenceNotEstablished": True,
        "tcpAndUdpSameRelayIPv4OrAdvertisedPortProven": False,
        "permissionlessNetworkReleaseReady": False,
    }

def main() -> int:
    p = argparse.ArgumentParser(description="Real raw TCP+UDP relay verification, no blockchain")
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--server", action="store_true")
    modes.add_argument("--check", action="store_true")
    p.add_argument("--tcp-host")
    p.add_argument("--tcp-port", type=int)
    p.add_argument("--udp-host")
    p.add_argument("--udp-port", type=int)
    args = p.parse_args()
    try:
        if args.server:
            if any(v is not None for v in (args.tcp_host, args.tcp_port,
                                            args.udp_host, args.udp_port)):
                raise RelayRefused("test receiver does not need remote relay endpoint")
            result = serve()
            print(json.dumps(result, indent=2, sort_keys=True), flush=True)
            return 0 if result["receivedBothTransports"] else 2
        if (args.tcp_host is None or args.tcp_port is None or
                args.udp_host is None or args.udp_port is None):
            raise RelayRefused("both public TCP and UDP relay endpoints required")
        result = check(args.tcp_host, args.tcp_port, args.udp_host, args.udp_port)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["bothPublicTransportsActuallyWorked"] else 2
    except (RelayRefused, OSError, ValueError, KeyboardInterrupt):
        print("R53_TRANSPORT_PROBE_REFUSED_OR_INTERRUPTED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
