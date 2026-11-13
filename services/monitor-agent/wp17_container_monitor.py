"""WP-17 container-only TLS tunnel around *unchanged* WP-16 V2 verifier.

Anvil is forwarded to 127.0.0.1:8545 from the explicitly trusted host
laboratory node. The chain RPC side of this tunnel is NOT independently
authenticated; it remains a trusted-lab assumption.

The provider's contract-committed ROOT stays numeric IPv4 loopback.
The monitor opens that root over a local relay which enforces certificate
chain AND DNS-name verification for provider.wp17:9443 on a Docker bridge.
This is a TRANSPORT EXPERIMENT, not a new production remote-endpoint policy.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import socketserver
import ssl
import sys
from threading import Thread
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))
sys.path.insert(0, str(ROOT / "tools"))
from wp16_v2_monitor import run as run_wp16


def _copy(source: socket.socket, target: socket.socket):
    try:
        while True:
            chunk = source.recv(65536)
            if not chunk:
                break
            target.sendall(chunk)
    except (OSError, ssl.SSLError):
        pass
    try:
        target.shutdown(socket.SHUT_WR)
    except OSError:
        pass


class LoopbackRelay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port: int, upstream_host: str, upstream_port: int,
                 *, tls_context: ssl.SSLContext | None = None,
                 tls_name: str | None = None):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.tls_context = tls_context
        self.tls_name = tls_name
        super().__init__(("127.0.0.1", port), RelayHandler)


class RelayHandler(socketserver.BaseRequestHandler):
    def handle(self):
        server: LoopbackRelay = self.server
        try:
            with socket.create_connection(
                (server.upstream_host, server.upstream_port), timeout=4
            ) as initial:
                if server.tls_context is not None:
                    remote = server.tls_context.wrap_socket(
                        initial, server_hostname=server.tls_name)
                else:
                    remote = initial
                with remote:
                    remote.settimeout(12)
                    self.request.settimeout(12)
                    outbound = Thread(target=_copy,
                                      args=(self.request, remote), daemon=True)
                    outbound.start()
                    _copy(remote, self.request)
                    outbound.join(timeout=0.5)
        except (OSError, ssl.SSLError):
            # A failed TLS handshake or disconnected provider must manifest as
            # a monitor-local transport failure, NEVER as a Failure verdict.
            return

    def finish(self):
        # No unexpected plaintext exposure outside the container's loopback.
        return super().finish()


def main():
    parser = argparse.ArgumentParser(description="WP17 container TLS-backed V2 monitor")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--timeout", type=float, default=0.65)
    parser.add_argument("--ca-cert", required=True)
    args = parser.parse_args()

    if os.getenv("SSE_WP17_CONTAINER_LAB") != "yes":
        parser.error("WP17 lab-container mode must be explicitly opted in")
    m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    root = m.get("serviceRoot")
    u = urlsplit(root)
    if (m.get("testOnly") is not True or m.get("chainId") != 31337
            or u.scheme != "http" or u.hostname != "127.0.0.1"
            or u.path not in ("", "/") or u.query or u.fragment
            or u.port is None or u.port == 8545):
        parser.error("unexpected on-chain loopback endpoint or lab manifest")
    if not Path(args.ca_cert).is_file():
        parser.error("missing pinned lab TLS trust anchor")

    tls = ssl.create_default_context(cafile=args.ca_cert)
    tls.check_hostname = True
    tls.verify_mode = ssl.CERT_REQUIRED
    tls.minimum_version = ssl.TLSVersion.TLSv1_2

    # These are intentionally restrictive lab-only forwarding targets.
    rpc_proxy = LoopbackRelay(8545, "host.docker.internal", 8545)
    provider_proxy = LoopbackRelay(
        u.port, "provider.wp17", 9443,
        tls_context=tls, tls_name="provider.wp17")
    workers = [
        Thread(target=rpc_proxy.serve_forever, kwargs={"poll_interval":0.1}, daemon=True),
        Thread(target=provider_proxy.serve_forever, kwargs={"poll_interval":0.1}, daemon=True),
    ]
    for t in workers:
        t.start()
    try:
        # Reuse original WP16 monitor: WP13 real EIP1898 state authorization,
        # WP08B signed provider HTTP and WP14 atomic signed provenance archive.
        result = run_wp16(argparse.Namespace(
            manifest=args.manifest, archive=args.archive,
            rpc_url="http://127.0.0.1:8545", nonce=args.nonce,
            timeout=args.timeout))
    finally:
        rpc_proxy.shutdown()
        provider_proxy.shutdown()
        rpc_proxy.server_close()
        provider_proxy.server_close()
        for t in workers:
            t.join(timeout=1.0)
    raise SystemExit(result)


if __name__ == "__main__":
    main()
