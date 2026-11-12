"""WP-16 separately running experimental HTTP provider, localhost ONLY.

Uses legacy WP-08B EIP-712 ProviderResponse signing; not physical service proof.
Never deploy with a real-world key or bind to a public network interface.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "provider-agent"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))
sys.path.insert(0, str(ROOT / "tools"))

from signed_http_service import make_server
from typed_evidence import Domain


def main():
    p = argparse.ArgumentParser(description="WP16 isolated Anvil HTTP provider process")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--controller", required=True)
    p.add_argument("--lease-id", type=int, required=True)
    p.add_argument("--epoch-id", type=int, required=True)
    p.add_argument("--request-hash", required=True)
    p.add_argument("--mode", choices=("healthy", "delay", "http503"), default="healthy")
    p.add_argument("--delay-seconds", type=float, default=0)
    a = p.parse_args()
    if a.chain_id != 31337 or a.delay_seconds < 0 or a.delay_seconds > 5:
        p.error("isolated Anvil chain 31337 and delay in [0,5] are mandatory")
    key = os.getenv("SSE_WP16_LAB_PROVIDER_KEY")
    if not key:
        p.error("SSE_WP16_LAB_PROVIDER_KEY must be set (Anvil lab key only)")
    server = make_server(a.port, key, Domain(a.chain_id, a.controller),
                         a.lease_id, a.epoch_id, a.request_hash)
    original_handler = server.RequestHandlerClass
    delay = a.delay_seconds if a.mode == "delay" else 0
    mode = a.mode

    class FaultHandler(original_handler):
        def do_POST(self):
            if mode == "http503":
                return self._json(503, {"error": "injected provider unavailable"})
            if delay:
                time.sleep(delay)
            return super().do_POST()

    server.RequestHandlerClass = FaultHandler
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
