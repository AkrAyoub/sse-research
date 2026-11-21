#!/usr/bin/env python3
"""R92: host-only, explicit-address TCP/UDP relay for ORIGINAL VM4706 EL/CL.

This avoids Docker Engine 29 publishing through an internal-only bridge.
The original Besu/Lighthouse/validator containers, mounts, networks, and
Engine JWT are NOT inspected, modified, or exposed. No wildcard listeners.
The remote Ethereum protocols remain native (Besu + Lighthouse).
UDP peers get independent upstream sockets so QUIC/discovery replies return
to the correct source. This is a transport relay, not a blockchain simulator.
"""
from __future__ import annotations
import argparse
import ipaddress
import selectors
import socket
import sys
import threading
import time

OWNER = "fca0:2328:776e:4750:395b::1"
EL = "172.18.0.2"
BN = "172.18.0.3"
# Protocol, listen IP, listen port, internal-only destination IP, destination port.
FORWARDS = (
    ("tcp", "127.0.0.1", 18545, EL, 8545),
    ("tcp", "127.0.0.1", 15052, BN, 5052),
    ("tcp", OWNER, 30404, EL, 30404),
    ("udp", OWNER, 30404, EL, 30404),
    ("tcp", OWNER, 9000, BN, 9000),
    ("udp", OWNER, 9000, BN, 9000),
    ("udp", OWNER, 9001, BN, 9001),
)
IDLE_SECONDS = 300
MAX_UDP_SESSIONS = 1024

def validate() -> None:
    assert len(FORWARDS) == 7
    assert len({(p, ip, n) for p, ip, n, _, _ in FORWARDS}) == len(FORWARDS)
    assert not any(n in (8551, 8550) or dst_port in (8551, 8550)
                   for _, _, n, _, dst_port in FORWARDS)
    assert all(ip in ("127.0.0.1", OWNER) for _, ip, _, _, _ in FORWARDS)
    assert all(dst in (EL, BN) for _, _, _, dst, _ in FORWARDS)
    assert ipaddress.ip_address(OWNER).version == 6

def bind_socket(proto: str, host: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    kind = socket.SOCK_STREAM if proto == "tcp" else socket.SOCK_DGRAM
    sock = socket.socket(family, kind)
    if family == socket.AF_INET6:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    if proto == "tcp":
        sock.listen(128)
    return sock

def copy_stream(source: socket.socket, dest: socket.socket) -> None:
    try:
        while True:
            chunk = source.recv(65536)
            if not chunk:
                break
            dest.sendall(chunk)
    except (OSError, TimeoutError):
        pass
    finally:
        try:
            dest.shutdown(socket.SHUT_WR)
        except OSError:
            pass

def handle_tcp(client: socket.socket, destination: str, port: int) -> None:
    try:
        with client:
            with socket.create_connection((destination, port), timeout=10) as upstream:
                client.settimeout(3600)
                upstream.settimeout(3600)
                t = threading.Thread(target=copy_stream, args=(client, upstream), daemon=True)
                t.start()
                copy_stream(upstream, client)
                t.join(timeout=3)
    except OSError:
        pass

def run_tcp(sock: socket.socket, destination: str, port: int) -> None:
    while True:
        client, _ = sock.accept()
        threading.Thread(target=handle_tcp, args=(client, destination, port),
                         daemon=True).start()

def run_udp(listener: socket.socket, destination: str, port: int) -> None:
    selector = selectors.DefaultSelector()
    selector.register(listener, selectors.EVENT_READ, data=None)
    sessions: dict[tuple, tuple[socket.socket, float]] = {}
    upstream_to_peer: dict[socket.socket, tuple] = {}
    try:
        while True:
            now = time.monotonic()
            for key, (upstream, last) in list(sessions.items()):
                if now - last > IDLE_SECONDS:
                    selector.unregister(upstream)
                    upstream.close()
                    del sessions[key]
                    upstream_to_peer.pop(upstream, None)
            for registered, _ in selector.select(timeout=1):
                if registered.fileobj is listener:
                    payload, peer = listener.recvfrom(65535)
                    if peer not in sessions:
                        if len(sessions) >= MAX_UDP_SESSIONS:
                            continue
                        upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        upstream.connect((destination, port))
                        selector.register(upstream, selectors.EVENT_READ, data=peer)
                        upstream_to_peer[upstream] = peer
                    else:
                        upstream = sessions[peer][0]
                    sessions[peer] = (upstream, time.monotonic())
                    try:
                        upstream.send(payload)
                    except OSError:
                        pass
                else:
                    upstream = registered.fileobj
                    peer = upstream_to_peer.get(upstream)
                    if peer is None:
                        continue
                    try:
                        payload = upstream.recv(65535)
                        listener.sendto(payload, peer)
                        sessions[peer] = (upstream, time.monotonic())
                    except OSError:
                        pass
    finally:
        selector.close()
        for upstream, _ in sessions.values():
            upstream.close()

def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="validate ports/address; no lasting listeners")
    action.add_argument("--serve", action="store_true", help="run fixed host relay")
    args = parser.parse_args()
    validate()
    sockets: list[socket.socket] = []
    try:
        # All-or-nothing bind. A duplicate listener or missing overlay IP refuses startup.
        for proto, source, port, _, _ in FORWARDS:
            sockets.append(bind_socket(proto, source, port))
    except OSError as exc:
        for sock in sockets:
            sock.close()
        print("R92_BIND_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2
    if args.check:
        for sock in sockets:
            sock.close()
        print("R92_HOST_RELAY_FIXED_BINDINGS_AVAILABLE=true")
        return 0
    for sock, (proto, _, _, destination, port) in zip(sockets, FORWARDS):
        worker = run_tcp if proto == "tcp" else run_udp
        threading.Thread(target=worker, args=(sock, destination, port),
                         daemon=True).start()
    print("R92_OWNER_INTERNAL_BRIDGE_RELAY_STARTED=true", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    raise SystemExit(main())
