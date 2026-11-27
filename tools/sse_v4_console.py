#!/usr/bin/env python3
"""SSE V4 node console: marketplace, role pages, committee planner, explorer.

SOURCE-ONLY (2026-11-27): never executed or served.

Modes
  local  (default) bind 127.0.0.1 only. Adds bounded artifact upload that
         computes content commitments (files stay on this host).
  public read-only: every GET view + UNSIGNED intent preparation. No uploads,
         no host writes, no signing, no arbitrary RPC passthrough.
Authorization is wallet-based: intents return {to,data,value,chainId} which the
user signs in their own wallet (browser EIP-1193 provider) or with the
owner-local agent CLI. There is no account/login system.
All chain reads are pinned to one block tag per request and labeled with
source, finality and observation time. Nothing here fabricates data.
"""
import argparse
import hashlib
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import sse_v4_abi as abi
import sse_v4_proof as proof
import sse_v4_state as st
import sse_v4_terms as terms
from sse_v4_committee_planner import plan as plan_committee, _render
from sse_challenge import keccak256

MAX_JSON = 64 * 1024
MAX_UPLOAD = 8 * 1024 * 1024
MAX_FILES = 32
INT = re.compile(r"^[0-9]{1,20}$")
HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
STATIC = Path(__file__).resolve().parent / "sse_v4_console_static"


def _int(q, name, default=None, lo=0, hi=2 ** 63):
    v = q.get(name, [None])[0]
    if v is None:
        if default is None:
            raise ValueError("missing " + name)
        return default
    if not INT.fullmatch(v):
        raise ValueError("bad integer " + name)
    v = int(v)
    if not lo <= v <= hi:
        raise ValueError(name + " out of range")
    return v


class Console:
    def __init__(self, ask, manifest, mode, state_dir=None):
        self.ask, self.manifest, self.mode = ask, manifest, mode
        self.mods = manifest["modules"]
        self.uploads = st.private_dir(Path(state_dir) / "artifacts") if mode == "local" and state_dir else None

    def _reader(self, finality):
        if finality == "latest":
            tag = "latest"
        else:
            tag = hex(st.finalized(self.ask)[0])
        return st.Reader(self.ask, self.manifest, tag=tag), tag

    def _meta(self, tag):
        b = self.ask("eth_getBlockByNumber", [tag, False])
        fin = st.finalized(self.ask)[0]
        n = int(b["number"], 16)
        return {"observedBlock": n, "blockHash": b["hash"], "finalized": n <= fin, "finalizedHeight": fin,
                "source": "configured RPC endpoint", "observedAt": int(time.time()), "physicalSlaTruthProved": False}

    # ---------------------------------------------------------------- views
    def overview(self, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        return dict(self._meta(tag), counts=r.counts(), modules=self.mods)

    def requests(self, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        total = r.counts()["requests"]
        off, lim = _int(q, "offset", 0), _int(q, "limit", 20, 1, 50)
        status = q.get("status", [None])[0]
        rows = []
        for rid in range(max(1, total - off - lim + 1), total - off + 1):
            x = r.request(rid)
            x["id"], x["statusName"] = rid, abi.REQUEST_STATUS[x["status"]]
            x["bidCount"] = r._v("board", "bidCount(uint256)", ("uint256",), (rid,))[0]
            if status is None or x["statusName"] == status:
                rows.append(x)
        return dict(self._meta(tag), total=total, offset=off, rows=list(reversed(rows)))

    def request(self, rid, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        x = r.request(rid)
        x["statusName"] = abi.REQUEST_STATUS[x["status"]]
        bids = r.bids(rid, _int(q, "offset", 0), _int(q, "limit", 50, 1, 100))
        now = int(self.ask("eth_getBlockByNumber", [tag, False])["timestamp"], 16)
        for b in bids:
            b["valid"] = (not b["withdrawn"]) and b["expiry"] >= now and x["statusName"] == "Open"
            b["fundingWei"] = b["epochFee"] * b["epochs"] + x["seats"] * b["epochs"] * x["perReportReward"]
        return dict(self._meta(tag), request=x, bids=bids,
                    note="Any valid bid may be awarded; no minimum number of bids; cheapest is not auto-selected.")

    def lease(self, lid, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        return dict(self._meta(tag), bundle=r.lease_bundle(lid), reserved=r.reserved(lid))

    def account(self, who, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        return dict(self._meta(tag), address=who, withdrawable=r.withdrawable(who), monitor=r.position(who))

    def plan(self, q):
        r, tag = self._reader("finalized")
        ex_a = q.get("consumer", ["0x" + "0" * 40])[0]
        ex_b = q.get("provider", ["0x" + "0" * 40])[0]
        for a in (ex_a, ex_b):
            if not ADDR.fullmatch(a):
                raise ValueError("bad address")
        e = r.eligible(ex_a, ex_b)
        res = plan_committee(_int(q, "seats", lo=4, hi=64), _int(q, "b", lo=1, hi=21), _int(q, "standbys", 0, 0, 60),
                             e["population"], e["eligible"], _int(q, "epochs", lo=1, hi=64), _int(q, "fee", lo=1),
                             _int(q, "reward", lo=1), q.get("adversarial") and _int(q, "adversarial"))
        return dict(self._meta(tag), observation=e, plan=_render(res),
                    warning="Eligibility is re-checked on chain at draw time; insufficiency refunds, never weakens.")

    # ------------------------------------------------------------ explorer
    def block(self, ident, q):
        if HEX32.fullmatch(ident):
            b = self.ask("eth_getBlockByHash", [ident, q.get("full", ["0"])[0] == "1"])
        else:
            b = self.ask("eth_getBlockByNumber", [hex(int(ident)) if INT.fullmatch(ident) else ident,
                                                  q.get("full", ["0"])[0] == "1"])
        if b is None:
            return {"available": False, "reason": "node returned no block (pruned, unknown, or not yet produced)"}
        fin = st.finalized(self.ask)[0]
        keep = ("number", "hash", "parentHash", "timestamp", "stateRoot", "transactionsRoot", "receiptsRoot",
                "gasUsed", "gasLimit", "baseFeePerGas", "miner", "withdrawalsRoot", "withdrawals", "transactions",
                "parentBeaconBlockRoot", "blobGasUsed", "excessBlobGas", "logsBloom", "extraData", "size")
        out = {k: b[k] for k in keep if k in b}
        out["finalized"] = int(b["number"], 16) <= fin
        out["source"] = "configured RPC endpoint"
        return out

    def tx(self, h):
        if not HEX32.fullmatch(h):
            raise ValueError("bad tx hash")
        t = self.ask("eth_getTransactionByHash", [h])
        if t is None:
            return {"available": False, "reason": "unknown to this node"}
        rc = self.ask("eth_getTransactionReceipt", [h])
        events = []
        if rc:
            for log in rc.get("logs", []):
                try:
                    ev = abi.decode_log(log, self.mods)
                except ValueError:
                    ev = None
                events.append(ev or {"raw": log})
        fin = st.finalized(self.ask)[0]
        inc = int(rc["blockNumber"], 16) if rc else None
        prio = None
        if rc and "effectiveGasPrice" in rc:
            blk = self.ask("eth_getBlockByNumber", [rc["blockNumber"], False])
            if blk and blk.get("baseFeePerGas"):
                prio = int(rc["effectiveGasPrice"], 16) - int(blk["baseFeePerGas"], 16)
        return {"transaction": t, "receipt": rc, "decodedEvents": events, "priorityFeePerGasWei": prio,
                "finalized": inc is not None and inc <= fin}

    def proof(self, q):
        addr = q.get("address", [""])[0]
        if not ADDR.fullmatch(addr):
            raise ValueError("bad address")
        slots = q.get("slot", [])[:16]
        for s in slots:
            if not HEX32.fullmatch(s):
                raise ValueError("slots must be 32-byte hex")
        tag = q.get("block", ["finalized"])[0]
        if tag not in ("finalized", "latest", "safe") and not INT.fullmatch(tag):
            raise ValueError("bad block")
        tag = hex(int(tag)) if INT.fullmatch(tag) else tag
        blk = self.ask("eth_getBlockByNumber", [tag, False])
        try:
            resp = self.ask("eth_getProof", [addr, slots, blk["number"]])
        except ValueError as exc:
            return {"available": False, "reason": "node refused eth_getProof (historical state pruned or method "
                    "disabled): " + str(exc)[:160], "block": blk["number"]}
        rep = proof.verify_get_proof(blk["stateRoot"], resp)
        rep.update(block=blk["number"], blockHash=blk["hash"],
                   note="Only nodes returned by eth_getProof are shown; the full trie is not enumerated.")
        return rep

    # -------------------------------------------------------------- intents
    def intent(self, action, body):
        r, tag = self._reader("latest")
        if action == "createRequest":
            call = abi.create_request(body)
        elif action == "placeBid":
            call = abi.place_bid(body["requestId"], body["epochFee"], body["epochs"], body["expiry"],
                                 body["endpointHash"], body["offerHash"])
        elif action == "withdrawBid":
            call = abi.withdraw_bid(body["requestId"], body["index"])
        elif action == "cancelRequest":
            call = abi.cancel_request(body["requestId"])
        elif action == "awardAndFund":
            q = r.request(body["requestId"])
            b = r.bids(body["requestId"], body["bidIndex"], 1)[0]
            call = abi.award_and_fund(body["requestId"], body["bidIndex"], body["terms"], q, b)
        elif action == "acceptLease":
            l = r.lease(body["leaseId"])
            call = abi.accept_lease(body["leaseId"], l["termsHash"])
        elif action == "startEpoch":
            call = abi.start_epoch(body["leaseId"], body["requestHash"])
        elif action in ("drawCommittee", "activateCommittee", "cancelExpiredDraw", "cancelUnformed",
                        "cancelUnaccepted", "closeLease", "forceCloseIdle"):
            call = abi.lease_call(action, body["leaseId"])
        elif action in ("finalizeEpoch", "closeEpochEvidence"):
            call = abi.epoch_call(action, body["leaseId"], body["epochId"])
        elif action == "registerMonitor":
            bond = r._v("registry", "perSeatBond()")[0] * body["capacity"]
            call = abi.register_monitor(body["capacity"], bond)
        elif action in ("requestExit", "completeExit"):
            call = abi.registry_call(action)
        elif action in ("confirm", "advance"):
            call = abi.standby_call(action, body["leaseId"])
        elif action == "withdraw":
            call = abi.withdraw(body["module"])
        else:
            raise ValueError("unknown action")
        module, data, value = call
        return {"unsigned": True, "chainId": st.CHAIN_ID, "to": self.mods[module], "data": data,
                "value": hex(value), "valueWei": str(value), "action": action,
                "warning": "Review in your wallet. Nothing is sent by this console."}

    def upload(self, files):
        """Local mode only: store files content-addressed and return a manifest
        commitment. Files never leave this host; on-chain only the commitment."""
        if self.uploads is None:
            raise PermissionError("uploads disabled in public mode")
        if not files or len(files) > MAX_FILES:
            raise ValueError("1..32 files required")
        entries, total = [], 0
        for name, data in files:
            if not SAFE_NAME.fullmatch(name) or name.startswith("."):
                raise ValueError("unsafe file name (no paths, no hidden files)")
            total += len(data)
            if total > MAX_UPLOAD:
                raise ValueError("upload too large")
            sha = hashlib.sha256(data).hexdigest()
            dest = self.uploads / sha
            if not dest.exists():
                dest.write_bytes(data)
                dest.chmod(0o600)
            entries.append({"name": name, "size": len(data), "sha256": sha})
        manifest = {"schema": "SSE_V4_ARTIFACT_MANIFEST_V1", "files": sorted(entries, key=lambda e: e["name"])}
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        commitment = "0x" + keccak256(raw).hex()
        (self.uploads / (commitment + ".manifest.json")).write_bytes(raw)
        return {"artifactCommitment": commitment, "manifest": manifest,
                "privacy": "Provider will see plaintext inputs once authorized; confidentiality against the "
                           "executing provider is not provided."}


def make_handler(console):
    class H(BaseHTTPRequestHandler):
        server_version = "SSEV4Console"

        def _send(self, code, obj, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # no client IPs or query strings in logs
            pass

        def do_GET(self):
            u = urlsplit(self.path)
            q = parse_qs(u.query)
            parts = [p for p in u.path.split("/") if p]
            try:
                if not parts:
                    return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                if parts == ["app.js"]:
                    return self._send(200, (STATIC / "app.js").read_bytes(), "text/javascript")
                if parts == ["app.css"]:
                    return self._send(200, (STATIC / "app.css").read_bytes(), "text/css")
                if parts[0] != "api":
                    return self._send(404, {"error": "not found"})
                p = parts[1:]
                if p == ["overview"]:
                    return self._send(200, console.overview(q))
                if p == ["mode"]:
                    return self._send(200, {"mode": console.mode})
                if p == ["requests"]:
                    return self._send(200, console.requests(q))
                if len(p) == 2 and p[0] == "request" and INT.fullmatch(p[1]):
                    return self._send(200, console.request(int(p[1]), q))
                if len(p) == 2 and p[0] == "lease" and INT.fullmatch(p[1]):
                    return self._send(200, console.lease(int(p[1]), q))
                if len(p) == 2 and p[0] == "account" and ADDR.fullmatch(p[1]):
                    return self._send(200, console.account(p[1].lower(), q))
                if p == ["plan"]:
                    return self._send(200, console.plan(q))
                if len(p) == 2 and p[0] == "block":
                    return self._send(200, console.block(p[1], q))
                if len(p) == 2 and p[0] == "tx":
                    return self._send(200, console.tx(p[1]))
                if p == ["proof"]:
                    return self._send(200, console.proof(q))
                return self._send(404, {"error": "not found"})
            except (ValueError, KeyError, IndexError, proof.ProofError) as exc:
                return self._send(400, {"error": str(exc)[:300]})
            except Exception:  # noqa: BLE001 - never leak tracebacks
                return self._send(500, {"error": "internal error"})

        def do_POST(self):
            u = urlsplit(self.path)
            parts = [p for p in u.path.split("/") if p]
            n = int(self.headers.get("Content-Length", "0") or 0)
            try:
                if len(parts) == 3 and parts[:2] == ["api", "intent"]:
                    if n > MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    body = json.loads(self.rfile.read(n) or b"{}")
                    return self._send(200, console.intent(parts[2], body))
                if parts == ["api", "upload"]:
                    if console.mode != "local":
                        return self._send(403, {"error": "uploads are owner-local only"})
                    if n > MAX_UPLOAD + MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    # JSON body {"files":[{"name":..,"base64":..}]} keeps parsing simple and bounded.
                    import base64
                    body = json.loads(self.rfile.read(n))
                    files = [(f["name"], base64.b64decode(f["base64"], validate=True)) for f in body["files"]]
                    return self._send(200, console.upload(files))
                return self._send(404, {"error": "not found"})
            except PermissionError as exc:
                return self._send(403, {"error": str(exc)})
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                return self._send(400, {"error": str(exc)[:300]})
            except Exception:  # noqa: BLE001
                return self._send(500, {"error": "internal error"})

    return H


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--rpc", required=True)
    p.add_argument("--mode", choices=("local", "public"), default="local")
    p.add_argument("--port", type=int, default=8790)
    p.add_argument("--state", type=Path)
    a = p.parse_args()
    from sse_chain_read import LocalRPC
    ask = LocalRPC(a.rpc).request
    manifest = st.load_manifest(a.manifest)
    st.verify_deployment(ask, manifest)
    console = Console(ask, manifest, a.mode, a.state)
    # Public exposure happens only through the separate tunnel/reverse proxy,
    # which must point at a --mode public instance. Always bind loopback.
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(console)).serve_forever()


if __name__ == "__main__":
    main()
