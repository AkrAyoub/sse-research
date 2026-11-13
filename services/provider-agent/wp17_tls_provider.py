"""WP-17 lab-only TLS HTTP provider in a separate Docker network namespace.

The protocol payload is the *legacy* off-chain V1 ProviderResponse, bound to the
V2 controller deployment as an EIP-712 domain; it is not a V2 payout signature.
TLS key is injected by a read-only container mount and never checked into Git.
This endpoint listens on 0.0.0.0:9443 INSIDE an unexposed bridge container only.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import ssl
import sys
import time
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))
sys.path.insert(0, str(ROOT / "services" / "provider-agent"))
from signed_http_service import make_server
from typed_evidence import Domain


def main():
    parser = argparse.ArgumentParser(description="WP17 isolated HTTPS signed provider")
    parser.add_argument("--chain-id", type=int, required=True)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--lease-id", type=int, required=True)
    parser.add_argument("--epoch-id", type=int, required=True)
    parser.add_argument("--request-hash", required=True)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--mode", choices=("healthy", "delay", "http503"), default="healthy")
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    args = parser.parse_args()
    if args.chain_id != 31337 or os.getenv("SSE_WP17_CONTAINER_LAB") != "yes":
        parser.error("only WP17 isolated Anvil container mode is permitted")
    if not 0 <= args.delay_seconds <= 5:
        parser.error("bounded delay must be between 0 and 5 seconds")
    private_key = os.getenv("SSE_WP17_LAB_PROVIDER_KEY")
    if not private_key:
        parser.error("set SSE_WP17_LAB_PROVIDER_KEY (public Anvil test key only)")
    for file in (args.cert, args.key):
        if not Path(file).is_file():
            parser.error("TLS credential file does not exist")

    # Reuse the *exact* existing response constructor and signing semantics,
    # without modifying the loopback-only WP08B provider in the main protocol.
    fixture = make_server(0, private_key,
                          Domain(args.chain_id, args.controller),
                          args.lease_id, args.epoch_id, args.request_hash)
    base_handler = fixture.RequestHandlerClass
    fixture.server_close()

    class LabHTTPSHandler(base_handler):
        def do_POST(self):
            if args.mode == "http503":
                return self._json(503, {"error": "lab fault injection"})
            if args.mode == "delay":
                time.sleep(args.delay_seconds)
            return super().do_POST()

    server = ThreadingHTTPServer(("0.0.0.0", 9443), LabHTTPSHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=args.cert, keyfile=args.key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
