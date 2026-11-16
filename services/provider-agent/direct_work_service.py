#!/usr/bin/env python3
"""Winning-provider-only SSE direct workload responder, bound to active EVM lease.

The service listens on *loopback only*. An Ubuntu Tailscale Serve HTTPS
configuration (not provided here) can publish it to authorized peers. Requests
and receipts are checked against a fresh pinned on-chain state. This early
lab service keeps replay/receipt state in memory and intentionally performs
NO on-chain transactions, settlement votes, or independent SLA certification.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services" / "monitor-agent"))

from sse_chain_read import inspect_chain, ChainReadError
from sse_node_marketplace import RPC, _load_signer
from sse_sla_manifest import validate_policy
from sse_direct_delivery import (
    ExchangeError, MAX_WIRE, authenticate_request, create_response,
    parse_bytes, json_bytes, verify_receipt,
)

def make_server(port, signer, policy, endpoint, chain_inspector):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("bad provider port")
    validate_policy(policy)
    if not callable(chain_inspector):
        raise ValueError("chain inspector required")
    lock = threading.RLock()
    pending = {}
    receipts = {}

    def inspect(lease, epoch):
        return chain_inspector(lease, epoch)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, data):
            raw = json_bytes(data)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def body(self):
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ExchangeError("JSON content type required")
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except (ValueError, TypeError):
                raise ExchangeError("invalid Content-Length") from None
            if not 1 <= size <= MAX_WIRE:
                raise ExchangeError("bounded message required")
            self.connection.settimeout(6)
            return parse_bytes(self.rfile.read(size))

        def do_GET(self):
            if self.path != "/healthz":
                return self.respond(404, {"error": "not found"})
            return self.respond(200, {
                "role": "provider", "online": True,
                "chosenProviderAuthRequired": True,
                "chainLeaseVerification": "PER_REQUEST_PINNED",
                "processed": len(pending), "receipts": len(receipts),
                "physicalSlaQualified": False,
            })

        def do_POST(self):
            if self.path not in ("/v1/work", "/v1/receipt"):
                return self.respond(404, {"error": "not found"})
            try:
                payload = self.body()
                if type(payload) is not dict or type(payload.get("message")) is not dict:
                    raise ExchangeError("invalid signed exchange envelope")
                msg = payload["message"]
                lease, epoch = msg.get("leaseId"), msg.get("epochId")
                if type(lease) is not int or type(epoch) is not int:
                    raise ExchangeError("invalid lease epoch indices")
                if self.path == "/v1/work":
                    with lock:
                        if len(pending) >= 1000:
                            raise ExchangeError("provider replay cache full")
                        state = inspect(lease, epoch)
                        authenticate_request(payload, state, policy, endpoint, signer)
                        key = (lease, epoch, msg["nonce"])
                        if key in pending:
                            raise ExchangeError("duplicate consumer workload nonce")
                        reply = create_response(payload, state, policy, endpoint, signer)
                        pending[key] = (payload, reply)
                    return self.respond(200, reply)
                with lock:
                    key = (lease, epoch, msg.get("nonce"))
                    if key not in pending or key in receipts:
                        raise ExchangeError("unknown or duplicate consumer receipt")
                    original, response = pending[key]
                    state = inspect(lease, epoch)
                    # Verify the original provider reply and consumer signature
                    # under this fresh pinned chain view before acknowledging.
                    from sse_direct_delivery import validate_response
                    validate_response(response, original, state, policy, endpoint)
                    verified = verify_receipt(payload, response, state, policy, endpoint)
                    receipts[key] = payload
                return self.respond(200, {"receiptSignatureVerified": verified["validSignature"],
                                          "physicalDeliveryTimeCertified": False})
            except (ExchangeError, ChainReadError, OSError, ValueError, TypeError):
                return self.respond(422, {"error": "invalid or unauthorized exchange"})
        def log_message(self, fmt, *args):
            return

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Node-owned SSE provider workload responder")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--endpoint", required=True,
                        help="exact committed public HTTPS Tailscale Serve origin")
    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--signer-file", required=True)
    parser.add_argument("--port", type=int, default=8881)
    parser.add_argument("--serve", action="store_true",
                        help="explicitly start loopback-only signer-backed service")
    args = parser.parse_args(argv)
    try:
        if args.policy.stat().st_size > 8192:
            raise ValueError("SLA manifest too large")
        policy = json.loads(args.policy.read_text("utf-8"))
        validate_policy(policy)
        from sse_direct_delivery import validate_endpoint_url
        validate_endpoint_url(args.endpoint)
        if not args.serve:
            print(json.dumps({"kind": "SSE_PROVIDER_DIRECT_SERVICE_PLAN",
                              "port": args.port, "endpoint": args.endpoint,
                              "slaPolicyHash": __import__("sse_sla_manifest").policy_hash(policy),
                              "running": False, "ethereumTransactionsSent": False}))
            return 0
        signer = _load_signer(args.signer_file)
        rpc = RPC(args.rpc_url)
        if int(rpc.request("eth_chainId", []), 16) != policy["chainId"]:
            raise ValueError("provider RPC chain mismatch")
        server = make_server(args.port, signer, policy, args.endpoint,
                             lambda lease, epoch: inspect_chain(
                                 rpc, policy["settlement"], lease, epoch,
                                 expected_chain_id=policy["chainId"],
                                 pin_block_hash=True))
        print("SSE provider work responder on http://127.0.0.1:" + str(server.server_port),
              flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("SSE_PROVIDER_WORK_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
