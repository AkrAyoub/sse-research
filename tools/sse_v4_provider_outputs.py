#!/usr/bin/env python3
"""SSE V4 provider output endpoint (serves results; NEVER executes work).

SOURCE-ONLY (2026-11-27): never executed or served.

Execution happens only in the provider agent after a finalized admitted epoch.
This server only reads the agent's content-addressed outputs:
  POST /v1/compute  {"leaseId","epochId","requestHash"}  -> stored output, for
       committee monitors' probes (output is the deterministic workload result;
       it is also bound to the signed on-chain responseHash, so serving it to
       monitors discloses nothing beyond what the committed policy requires).
  POST /v1/output   {"leaseId","epochId","expiry","signature"} -> stored output
       only for the lease CONSUMER: signature is an EIP-191 personal_sign over
       "SSE_V4_OUTPUT|<chainId>|<market>|<leaseId>|<epochId>|<expiry>", expiry
       at most 10 minutes ahead; consumer address read from FINALIZED chain.
Behind the existing TLS front (R304) on loopback. Bounded bodies; no paths
from clients reach the filesystem except validated hex hashes.
"""
import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct

import sse_v4_state as st
from sse_v4_adapters import response_hash

HEX32 = re.compile(r"^0x[0-9a-f]{64}$")
MAX_BODY = 2048


def output_message(chain_id, market, lease_id, epoch_id, expiry):
    return f"SSE_V4_OUTPUT|{chain_id}|{market}|{lease_id}|{epoch_id}|{expiry}"


class Outputs:
    def __init__(self, ask, manifest, state_dir):
        self.ask, self.manifest = ask, manifest
        self.jobs = Path(state_dir) / "v4-jobs.json"
        self.outdir = Path(state_dir) / "outputs"

    def _job(self, lid, eid):
        jobs = st.read_json(self.jobs) or {}
        for j in jobs.values():
            if j["leaseId"] == lid and j["epochId"] == eid and j.get("state") == "DONE":
                return j
        return None

    def _load(self, j):
        h = j["responseHash"].lower()
        st.require(HEX32.fullmatch(h), "bad stored hash")
        out = st.read_json(self.outdir / (h + ".json"), 65536)
        st.require(out is not None and response_hash(out) == h, "stored output corrupted")
        return out

    def compute(self, body):
        lid, eid, req = body["leaseId"], body["epochId"], body["requestHash"].lower()
        st.require(type(lid) is int and type(eid) is int and HEX32.fullmatch(req), "bad request")
        j = self._job(lid, eid)
        st.require(j is not None and j["requestHash"].lower() == req, "no delivered output for this epoch")
        return self._load(j)

    def output(self, body):
        lid, eid, exp, sig = body["leaseId"], body["epochId"], body["expiry"], body["signature"]
        st.require(type(lid) is int and type(eid) is int and type(exp) is int, "bad request")
        now = int(time.time())
        st.require(now <= exp <= now + 600, "expired or too-distant authorization")
        market = self.manifest["modules"]["market"]
        msg = encode_defunct(text=output_message(st.CHAIN_ID, market, lid, eid, exp))
        signer = Account.recover_message(msg, signature=sig).lower()
        lease = st.Reader(self.ask, self.manifest, tag="finalized").lease(lid)
        st.require(signer == lease["consumer"], "only the lease consumer may download outputs")
        j = self._job(lid, eid)
        st.require(j is not None, "no delivered output for this epoch")
        return {"output": self._load(j), "responseHash": j["responseHash"],
                "note": "Compare responseHash with the on-chain ProviderResponseVerified event."}


def make_handler(outputs):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
                if n < 0 or self.headers.get("Transfer-Encoding") is not None:
                    raise ValueError("invalid body framing")
            except ValueError:
                return self._send(400, {"error": "invalid body framing"})
            if n > MAX_BODY:
                return self._send(413, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(n))
                if self.path == "/v1/compute":
                    return self._send(200, outputs.compute(body))
                if self.path == "/v1/output":
                    return self._send(200, outputs.output(body))
                return self._send(404, {"error": "not found"})
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, {"error": str(exc)[:200]})
            except Exception:  # noqa: BLE001
                return self._send(500, {"error": "internal error"})

    return H


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--rpc", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--port", type=int, default=8881)
    a = p.parse_args()
    from sse_chain_read import LocalRPC
    ask = LocalRPC(a.rpc).request
    manifest = st.load_manifest(a.manifest)
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(Outputs(ask, manifest, a.state))).serve_forever()


if __name__ == "__main__":
    main()
