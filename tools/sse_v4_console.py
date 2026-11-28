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
from sse_v4_adapters import endpoint_hash, response_hash

MAX_JSON = 64 * 1024
MAX_UPLOAD = 8 * 1024 * 1024
MAX_FILES = 32
INT = re.compile(r"^[0-9]{1,20}$")
HEX32 = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
PROVIDER_URL = re.compile(r"^(https://[A-Za-z0-9.-]{1,253}(:[0-9]{2,5})?(/[A-Za-z0-9._~/-]{0,200})?|http://127\.0\.0\.1:[0-9]{2,5}(/[A-Za-z0-9._~/-]{0,200})?)$")
ZERO32 = "0x" + "00" * 32
MAX_OUTPUT = 4 * 1024 * 1024
OUTPUT_AUTH_SECONDS = 300
SUPPORTED_SERVICES = ("SHA256_CHAIN_8192",)  # must match tools/sse_v4_adapters.py
HISTORY_RANGE = 2000  # same bound as the agent cursor (sse_v4_state.MAX_LOG_RANGE)
STALE_REWARDS_SECONDS = 300  # collector timer runs every ~24 s (scripts/sse_install_native_reward_timer.py)
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
    def __init__(self, ask, manifest, mode, state_dir=None, beacon=None, rewards_dir=None):
        self.ask, self.deployment, self.mode = ask, manifest, mode
        if beacon is not None and not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{2,5}", beacon):
            raise ValueError("beacon API must be a loopback URL")
        self.beacon = beacon
        self.rewards_dir = rewards_dir
        self.mods = manifest["modules"]
        self.uploads = st.private_dir(Path(state_dir) / "artifacts") if mode == "local" and state_dir else None

    def _reader(self, finality):
        if finality == "latest":
            tag = hex(st.block_identity(self.ask("eth_getBlockByNumber", ["latest", False]))[0])
        else:
            tag = hex(st.finalized(self.ask)[0])
        return st.Reader(self.ask, self.deployment, tag=tag), tag

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
        off, lim = _int(q, "offset", 0), _int(q, "limit", 50, 1, 100)
        bid_count = r._v("board", "bidCount(uint256)", ("uint256",), (rid,))[0]
        bids = r.bids(rid, off, lim) if off < bid_count else []
        now = int(self.ask("eth_getBlockByNumber", [tag, False])["timestamp"], 16)
        for b in bids:
            b["valid"] = (not b["withdrawn"]) and b["expiry"] >= now and x["statusName"] == "Open"
            b["fundingWei"] = b["epochFee"] * b["epochs"] + x["seats"] * b["epochs"] * x["perReportReward"]
        # Filters apply within the fetched page (on-chain bids are unbounded and never iterated on-chain).
        if q.get("validOnly", ["0"])[0] == "1":
            bids = [b for b in bids if b["valid"]]
        max_fee = _int(q, "maxFee", 2 ** 256, 0, 2 ** 256)
        bids = [b for b in bids if b["epochFee"] <= max_fee]
        return dict(self._meta(tag), request=x, bids=bids, bidCount=bid_count, offset=off, limit=lim,
                    note="Any valid bid may be awarded; no minimum number of bids; cheapest is not auto-selected.")

    def lease(self, lid, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        return dict(self._meta(tag), bundle=r.lease_bundle(lid), reserved=r.reserved(lid))

    def account(self, who, q):
        r, tag = self._reader(q.get("finality", ["finalized"])[0])
        code = self.ask("eth_getCode", [who, tag])
        return dict(self._meta(tag), address=who, withdrawable=r.withdrawable(who), monitor=r.position(who),
                    balanceWei=int(self.ask("eth_getBalance", [who, tag]), 16),
                    nonce=int(self.ask("eth_getTransactionCount", [who, tag]), 16),
                    codeBytes=(len(code) - 2) // 2 if isinstance(code, str) else None)


    def history(self, who, q):
        """Finalized SSE V4 events that name this address (provider/monitor/account
        topics), over at most HISTORY_RANGE blocks ending at `toBlock` (default:
        finalized). Read only; older history is paged by the caller."""
        fin = st.finalized(self.ask)[0]
        to = min(_int(q, "toBlock", fin), fin)
        frm = max(0, to - HISTORY_RANGE + 1)
        topic = "0x" + "00" * 12 + who[2:]
        rows = []
        # The address can sit in topic 1, 2 or 3 depending on the event; one query per position.
        for pos in (1, 2, 3):
            flt = {"fromBlock": hex(frm), "toBlock": hex(to), "address": list(self.mods.values()),
                   "topics": [None] * pos + [topic]}
            for log in self.ask("eth_getLogs", [flt]) or []:
                ev = abi.decode_log(log, self.mods)
                if ev is not None and who in (str(v).lower() for v in ev.values()):
                    rows.append(ev)
        uniq = {(e["blockNumber"], e["logIndex"]): e for e in rows}
        events = [uniq[k] for k in sorted(uniq, reverse=True)]
        return {"address": who, "fromBlock": frm, "toBlock": to, "finalized": True, "events": events,
                "earlierPage": frm - 1 if frm > 0 else None,
                "note": "Only events naming this address in an indexed field are listed; amounts are wei."}
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
        canonical = self.ask("eth_getBlockByNumber", [b["number"], False])
        out["finalized"] = int(b["number"], 16) <= fin and bool(canonical) and canonical["hash"].lower() == b["hash"].lower()
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
        canonical = self.ask("eth_getBlockByNumber", [rc["blockNumber"], False]) if rc else None
        if rc and "effectiveGasPrice" in rc:
            blk = self.ask("eth_getBlockByNumber", [rc["blockNumber"], False])
            if blk and blk.get("baseFeePerGas"):
                prio = int(rc["effectiveGasPrice"], 16) - int(blk["baseFeePerGas"], 16)
        return {"transaction": t, "receipt": rc, "decodedEvents": events, "priorityFeePerGasWei": prio,
                "finalized": inc is not None and inc <= fin and bool(canonical) and canonical["hash"].lower() == rc["blockHash"].lower()}

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
        st.require(resp["address"].lower() == addr.lower(), "proof address mismatch")
        returned_slots = [int(s["key"], 16) for s in resp.get("storageProof", [])]
        st.require(sorted(returned_slots) == sorted(int(s, 16) for s in slots), "proof slot set mismatch")
        rep = proof.verify_get_proof(blk["stateRoot"], resp)
        rep.update(block=blk["number"], blockHash=blk["hash"],
                   note="Only nodes returned by eth_getProof are shown; the full trie is not enumerated.")
        return rep

    # ------------------------------------------------------ node / validator
    def node(self):
        """Execution-layer node facts from the configured RPC (no secrets, no paths)."""
        out = {"source": "configured RPC endpoint", "observedAt": int(time.time())}
        for k, m in (("peerCount", "net_peerCount"), ("syncing", "eth_syncing"), ("client", "web3_clientVersion")):
            try:
                out[k] = self.ask(m, [])
            except ValueError as exc:
                out[k] = {"unavailable": str(exc)[:120]}
        for tag in ("latest", "safe", "finalized"):
            b = self.ask("eth_getBlockByNumber", [tag, False])
            out[tag] = {"number": b["number"], "hash": b["hash"], "timestamp": b["timestamp"]} if b else None
        # Historical-state capability probe: genesis-era balance query succeeds only on archive nodes.
        try:
            self.ask("eth_getBalance", [self.mods["market"], "0x1"])
            out["historicalStateAtBlock1"] = "served"
        except ValueError:
            out["historicalStateAtBlock1"] = "unavailable (pruned full node or method restricted) - not zero"
        out["beacon"] = self._beacon_summary() if self.beacon else {"configured": False}
        return out

    def _bn(self, path):
        from urllib.request import urlopen
        with urlopen(self.beacon + path, timeout=4) as r:
            st.require(r.status == 200, "beacon HTTP " + str(r.status))
            return json.loads(r.read(1024 * 1024))

    def _beacon_summary(self):
        out = {"configured": True, "source": "local beacon node API"}
        for k, p in (("syncing", "/eth/v1/node/syncing"), ("peers", "/eth/v1/node/peer_count"),
                     ("finality", "/eth/v1/beacon/states/head/finality_checkpoints"),
                     ("headHeader", "/eth/v1/beacon/headers/head")):
            try:
                out[k] = self._bn(p).get("data")
            except Exception as exc:  # noqa: BLE001
                out[k] = {"unavailable": type(exc).__name__}
        return out

    def validators(self, q):
        if not self.beacon:
            return {"available": False, "reason": "no local beacon node configured"}
        ids = q.get("id", [])
        if not 1 <= len(ids) <= 64:
            raise ValueError("1..64 validator ids required")
        for i in ids:
            if not (INT.fullmatch(i) or re.fullmatch(r"^0x[0-9a-fA-F]{96}$", i)):
                raise ValueError("validator ids must be indices or 48-byte pubkeys")
        state = q.get("state", ["finalized"])[0]
        if state not in ("head", "finalized", "justified") and not INT.fullmatch(state):
            raise ValueError("bad state id")
        data = self._bn(f"/eth/v1/beacon/states/{state}/validators?id=" + ",".join(ids))
        return {"state": state, "validators": data.get("data"), "executionOptimistic": data.get("execution_optimistic"),
                "finalized": data.get("finalized"), "note": "Balances in Gwei as reported by the local beacon node. "
                "Rewards history comes from the R424 collector archive, not recomputed here."}

    def rewards(self):
        """Summary written by the historically execution-tested R424/R425 native
        reward collector timer (tools/sse_native_reward_collector.py --tick).
        Read only; this console never queries reward endpoints itself."""
        if not self.rewards_dir:
            return {"available": False, "reason": "no reward collector directory configured"}
        latest = st.read_json(Path(self.rewards_dir) / "latest.json")
        if latest is None:
            return {"available": False, "reason": "collector has not written latest.json yet"}
        per = {}
        unavailable = []
        for r in latest.get("attestationRewards", []):
            if "validator" not in r:
                unavailable.append(r.get("epoch"))
                continue
            v = per.setdefault(str(r["validator"]), {"validator": str(r["validator"]), "epochs": 0, "netGwei": 0})
            v["epochs"] += 1
            v["netGwei"] += int(r["netGwei"])
        blocks = [b for b in latest.get("blockRewards", []) if "totalGwei" in b]
        age = int(time.time()) - int(latest.get("observedUnixNs", 0)) // 10 ** 9
        return {"available": True, "source": "local native reward collector (beacon API, read only)",
                "observedAgeSeconds": age, "stale": age > STALE_REWARDS_SECONDS, "headSlot": latest.get("headSlot"),
                "finalizedEpoch": latest.get("finalizedEpoch"), "gapBeforeStart": latest.get("gapBeforeStart"),
                "attestationByValidator": sorted(per.values(), key=lambda v: int(v["validator"])),
                "epochsUnavailable": unavailable,
                "blockRewards": blocks, "blocksUnavailable": len(latest.get("blockRewards", [])) - len(blocks),
                "note": "Unavailable rewards are unknown, not zero. Values are beacon-API reports in Gwei."}
    # -------------------------------------------------------------- intents
    def residual_preview(self, body):
        """Unsigned typed data for two independently consenting EOA parties."""
        lid, eid = body["leaseId"], body["epochId"]
        st.require(type(lid) is int and lid > 0 and type(eid) is int and eid >= 0, "invalid epoch identity")
        supplied = body["allocation"]
        allocation = {}
        for name, _ in abi.ALLOCATION_FIELDS:
            v = supplied[name]
            if isinstance(v, str):
                st.require(re.fullmatch(r"[0-9]{1,78}", v), "invalid allocation integer")
                v = int(v)
            st.require(type(v) is int and 0 <= v < 2**256, "invalid allocation integer")
            allocation[name] = v
        r, tag = self._reader("finalized")
        lease, epoch, science = r.lease(lid), r.market_epoch(lid, eid), r.scientific_epoch(lid, eid)
        st.require(epoch["exists"] and not epoch["resolved"] and science["evidenceClosed"] and not science["residualAllocated"], "residual not eligible")
        st.require(allocation["unresolvedAmount"] == science["unresolved"] and allocation["nonce"] == epoch["nonce"], "stale residual or nonce")
        st.require(allocation["expiry"] > int(time.time()), "allocation expired")
        domain = terms.domain_separator(terms.MARKET_NAME, st.CHAIN_ID, self.mods["market"])
        digest = terms.allocation_digest(domain, lid, eid, epoch["requestHash"], allocation)
        message = {"leaseId": str(lid), "epochId": str(eid), "requestHash": epoch["requestHash"],
                   **{k: str(v) for k, v in allocation.items()}}
        typed = {"primaryType": "ResidualAgreement",
                 "types": {"EIP712Domain": [{"name": k, "type": t} for k,t in
                           (("name","string"),("version","string"),("chainId","uint256"),("verifyingContract","address"))],
                           "ResidualAgreement": [{"name": k,"type": t} for k,t in
                           (("leaseId","uint256"),("epochId","uint256"),("requestHash","bytes32")) + abi.ALLOCATION_FIELDS]},
                 "domain": {"name": terms.MARKET_NAME, "version": "1", "chainId": st.CHAIN_ID,
                            "verifyingContract": self.mods["market"]}, "message": message}
        return {"typedData": typed, "digest": "0x" + digest.hex(), "consumer": lease["consumer"],
                "provider": lease["provider"], "allocation": allocation,
                "note": "Bilateral consent allocates uncertainty; it does not prove SLA truth."}

    def intent(self, action, body):
        # Browser inputs carry monetary uint256 values as exact decimal strings.
        body = dict(body)
        for field in ("maxEpochFee", "perReportReward", "epochFee"):
            if field in body and isinstance(body[field], str):
                st.require(re.fullmatch(r"[0-9]{1,78}", body[field]), "invalid wei value")
                body[field] = int(body[field])
        if "terms" in body and isinstance(body["terms"], dict):
            body["terms"] = dict(body["terms"])
            for field in ("reservationFee", "exposureBudget"):
                val = body["terms"].get(field)
                if isinstance(val, str):
                    st.require(re.fullmatch(r"[0-9]{1,78}", val), "invalid wei value")
                    body["terms"][field] = int(val)
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
        elif action == "resolveResidual":
            preview = self.residual_preview(body)
            from eth_account import Account
            from eth_account.messages import encode_typed_data
            msg = encode_typed_data(full_message=preview["typedData"])
            signatures = []
            for role in ("consumer", "provider"):
                raw = body[role + "Signature"]
                st.require(isinstance(raw, str) and re.fullmatch(r"0x[0-9a-fA-F]{130}", raw), "invalid signature")
                sig = bytes.fromhex(raw[2:])
                st.require(Account.recover_message(msg, signature=sig).lower() == preview[role].lower(), role + " signature mismatch")
                signatures.append(sig)
            call = abi.resolve_residual(body["leaseId"], body["epochId"], preview["allocation"], *signatures)
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


    def terms_check(self, body):
        """Provider helper (D-10 fallback for contract-wallet consumers): recompute
        termsHash from finalized public views + the Terms the consumer handed over,
        and emit the policy snippet the provider agent needs. Read only."""
        lid, t = body["leaseId"], body["terms"]
        if type(lid) is not int or lid < 1 or not isinstance(t, dict):
            raise ValueError("leaseId and terms object required")
        clean = {}
        for name, kind in abi.TERMS_FIELDS:
            v = t.get(name)
            if name in ("reservationFee", "exposureBudget") and isinstance(v, str):
                st.require(re.fullmatch(r"[0-9]{1,78}", v), "invalid wei value")
                v = int(v)
            if kind == "bool":
                if type(v) is not bool:
                    raise ValueError(name + " must be true/false")
            elif type(v) is not int or v < 0 or v >= 2 ** (64 if kind == "uint64" else 256):
                raise ValueError(name + " must be a " + kind)
            clean[name] = v
        r, tag = self._reader("finalized")
        lease = r.lease(lid)
        q = r.request(lease["requestId"])
        bid = r.bids(lease["requestId"], lease["bidIndex"], 1)[0]
        bid.pop("index", None)
        got = "0x" + terms.terms_hash(st.CHAIN_ID, self.mods["market"], lid, lease["bidIndex"], q, bid, clean).hex()
        match = got.lower() == lease["termsHash"].lower()
        return dict(self._meta(tag), onchainTermsHash=lease["termsHash"], recomputedTermsHash=got, match=match,
                    policySnippet={"provider": {"leaseTerms": {str(lid): clean}, "approvedTermsHashes": [got]}} if match else None,
                    note="Review every lease term before explicitly approving the exact terms hash in policy. "
                         "A hash match is integrity, not consent. Acceptance also requires approvedOfferHashes.")

    # ------------------------------------------------------- structured manifests
    def manifest(self, kind, body):
        """Build a canonical manifest and its keccak commitment. Pure, read only.
        profile  (consumer): service + resource needs + measurable SLA -> profileHash
        policy   (consumer): monitoring/evidence policy -> policyHash
        offer    (provider): actual resources advertised -> offerHash; endpoint URL -> endpointHash
        Supported service in this release is SHA256_CHAIN_8192 only (fail closed otherwise)."""
        def num(name, lo, hi):
            v = body.get(name)
            if type(v) is not int or not lo <= v <= hi:
                raise ValueError(f"{name} must be an integer in [{lo}, {hi}]")
            return v
        if kind == "profile":
            if body.get("service") not in SUPPORTED_SERVICES:
                raise ValueError("unsupported service (supported: " + ", ".join(SUPPORTED_SERVICES) + ")")
            m = {"schema": "SSE_V4_PROFILE_V1", "service": body["service"],
                 "resources": {"cpuCores": num("cpuCores", 1, 256), "memoryMiB": num("memoryMiB", 64, 1 << 20),
                               "storageMiB": num("storageMiB", 0, 1 << 24)},
                 "sla": {"responseSeconds": num("responseSeconds", 1, 86400),
                         "maxRuntimeSeconds": num("maxRuntimeSeconds", 1, 86400)}}
        elif kind == "policy":
            m = {"schema": "SSE_V4_POLICY_V1", "probe": body.get("probe"),
                 "probeTimeoutSeconds": num("probeTimeoutSeconds", 1, 3600),
                 "failureEvidence": body.get("failureEvidence")}
            if m["probe"] not in SUPPORTED_SERVICES:
                raise ValueError("probe must be a supported deterministic service")
            if m["failureEvidence"] not in ("conditional-quorum", "none"):
                raise ValueError("failureEvidence must be conditional-quorum or none")
        elif kind == "offer":
            url = body.get("endpointUrl")
            if not isinstance(url, str) or not PROVIDER_URL.fullmatch(url) or url.startswith("http://"):
                raise ValueError("endpointUrl must be a public https URL")
            m = {"schema": "SSE_V4_OFFER_V1", "services": sorted(set(body.get("services") or [])),
                 "resources": {"cpuCores": num("cpuCores", 1, 1024), "memoryMiB": num("memoryMiB", 64, 1 << 24),
                               "storageMiB": num("storageMiB", 0, 1 << 30)},
                 "maxConcurrentLeases": num("maxConcurrentLeases", 1, 1024), "endpointUrl": url}
            if not m["services"] or any(s not in SUPPORTED_SERVICES for s in m["services"]):
                raise ValueError("services must be a non-empty subset of the supported services")
        else:
            raise ValueError("unknown manifest kind")
        raw = json.dumps(m, sort_keys=True, separators=(",", ":")).encode()
        out = {"kind": kind, "manifest": m, "canonical": raw.decode(), "hash": "0x" + keccak256(raw).hex(),
               "note": "Publish the canonical manifest with your request or bid; the chain stores only the hash."}
        if kind == "offer":
            out["endpointHash"] = endpoint_hash(m["endpointUrl"])
        return out
    # ---------------------------------------------------------- consumer outputs
    def output_message(self, q):
        """Message the consumer signs (EIP-191 personal_sign) to download an
        epoch output from the provider. Pure string; nothing is signed here."""
        lid, eid = _int(q, "lease"), _int(q, "epoch")
        expiry = int(time.time()) + OUTPUT_AUTH_SECONDS
        market = self.deployment["modules"]["market"]
        return {"message": f"SSE_V4_OUTPUT|{st.CHAIN_ID}|{market}|{lid}|{eid}|{expiry}", "expiry": expiry,
                "note": "Sign in your wallet; the signature authorizes only this lease/epoch until expiry."}

    def output_verify(self, body):
        """Check an output against the FINALIZED on-chain responseHash. Read only."""
        lid, eid, output = body["leaseId"], body["epochId"], body["output"]
        if type(lid) is not int or type(eid) is not int or lid < 0 or eid < 0:
            raise ValueError("bad lease/epoch")
        r, tag = self._reader("finalized")
        onchain = r.market_epoch(lid, eid)["responseHash"].lower()
        got = response_hash(output).lower()
        return dict(self._meta(tag), onchainResponseHash=onchain, outputResponseHash=got,
                    verified=onchain != ZERO32 and got == onchain,
                    meaning="Match proves this is the output the provider signed on-chain; it does not prove the "
                            "output is correct beyond what the committed monitor policy measured.")

    def output_fetch(self, body):
        """Local mode only: fetch the consumer's output from the provider endpoint
        committed in the awarded bid (keccak(url) must equal lease.endpointHash),
        then verify it against the finalized responseHash."""
        if self.mode != "local":
            raise PermissionError("provider fetch is owner-local only; use output-verify in public mode")
        url, lid, eid = body["providerUrl"], body["leaseId"], body["epochId"]
        if not isinstance(url, str) or not PROVIDER_URL.fullmatch(url):
            raise ValueError("provider URL must be https://host[:port][/path] or http://127.0.0.1:port")
        if type(lid) is not int or type(eid) is not int:
            raise ValueError("bad lease/epoch")
        lease = self._reader("finalized")[0].lease(lid)
        st.require(endpoint_hash(url).lower() == lease["endpointHash"].lower(),
                   "URL does not match the endpoint committed in the awarded bid")
        req = {"leaseId": lid, "epochId": eid, "expiry": int(body["expiry"]), "signature": str(body["signature"])}
        from urllib.request import Request, build_opener
        from sse_v4_adapters import NoRedirect
        rq = Request(url.rstrip("/") + "/v1/output", data=json.dumps(req).encode(), method="POST",
                     headers={"Content-Type": "application/json"})
        with build_opener(NoRedirect()).open(rq, timeout=15) as resp:
            raw = resp.read(MAX_OUTPUT + 1)
        if len(raw) > MAX_OUTPUT:
            raise ValueError("provider output exceeds console limit")
        got = json.loads(raw)
        check = self.output_verify({"leaseId": lid, "epochId": eid, "output": got["output"]})
        return dict(check, output=got["output"], providerClaimedResponseHash=got.get("responseHash"))


def make_handler(console):
    class H(BaseHTTPRequestHandler):
        server_version = "SSEV4Console"

        def _send(self, code, obj, ctype="application/json"):
            def exact_numbers(value):
                if type(value) is int and abs(value) > 2 ** 53 - 1:
                    return str(value)
                if isinstance(value, dict):
                    return {k: exact_numbers(v) for k, v in value.items()}
                if isinstance(value, (tuple, list)):
                    return [exact_numbers(v) for v in value]
                return value
            body = obj if isinstance(obj, bytes) else json.dumps(exact_numbers(obj), default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

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
                if p == ["public-instance"] and console.mode == "public":
                    return self._send(200, {"instance": getattr(console, "public_instance", None), "chainId": st.CHAIN_ID})
                if p == ["requests"]:
                    return self._send(200, console.requests(q))
                if len(p) == 2 and p[0] == "request" and INT.fullmatch(p[1]):
                    return self._send(200, console.request(int(p[1]), q))
                if len(p) == 2 and p[0] == "lease" and INT.fullmatch(p[1]):
                    return self._send(200, console.lease(int(p[1]), q))
                if len(p) == 3 and p[0] == "account" and ADDR.fullmatch(p[1]) and p[2] == "history":
                    return self._send(200, console.history(p[1].lower(), q))
                if len(p) == 2 and p[0] == "account" and ADDR.fullmatch(p[1]):
                    return self._send(200, console.account(p[1].lower(), q))
                if p == ["node"]:
                    return self._send(200, console.node())
                if p == ["rewards"]:
                    return self._send(200, console.rewards())
                if p == ["validators"]:
                    return self._send(200, console.validators(q))
                if p == ["output-message"]:
                    return self._send(200, console.output_message(q))
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
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
                if n < 0 or self.headers.get("Transfer-Encoding") is not None:
                    raise ValueError("invalid body framing")
            except ValueError:
                return self._send(400, {"error": "invalid body framing"})
            # CSRF / DNS-rebinding guard: only same-origin JSON posts from this console.
            origin, host = self.headers.get("Origin"), self.headers.get("Host", "")
            local_host = re.fullmatch(r"(127\.0\.0\.1|localhost):[0-9]{2,5}", host) is not None
            if (console.mode == "local" and not local_host) or \
                    (origin is not None and origin not in ("http://" + host, "https://" + host)) or \
                    not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._send(403, {"error": "same-origin application/json requests only"})
            try:
                if len(parts) == 3 and parts[:2] == ["api", "intent"]:
                    if n > MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    body = json.loads(self.rfile.read(n) or b"{}")
                    return self._send(200, console.intent(parts[2], body))
                if len(parts) == 3 and parts[:2] == ["api", "manifest"]:
                    if n > MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    return self._send(200, console.manifest(parts[2], json.loads(self.rfile.read(n) or b"{}")))
                if parts == ["api", "residual-preview"]:
                    if n > MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    return self._send(200, console.residual_preview(json.loads(self.rfile.read(n) or b"{}")))
                if parts == ["api", "terms-check"]:
                    if n > MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    return self._send(200, console.terms_check(json.loads(self.rfile.read(n) or b"{}")))
                if parts in (["api", "output-verify"], ["api", "output-fetch"]):
                    if n > MAX_OUTPUT + MAX_JSON:
                        return self._send(413, {"error": "too large"})
                    body = json.loads(self.rfile.read(n) or b"{}")
                    fn = console.output_verify if parts[1] == "output-verify" else console.output_fetch
                    return self._send(200, fn(body))
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
            except st.StateError as exc:
                return self._send(400, {"error": str(exc)[:300]})
            except PermissionError as exc:
                return self._send(403, {"error": str(exc)})
            except OSError:
                return self._send(502, {"error": "upstream endpoint (provider or RPC) unreachable or refused the request"})
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
    p.add_argument("--public-instance", help="nonsecret per-host public console identity")
    p.add_argument("--beacon", help="local beacon API, e.g. http://127.0.0.1:25052")
    p.add_argument("--rewards-dir", help="native reward collector output, e.g. ~/.local/share/sse-native-rewards")
    a = p.parse_args()
    from sse_chain_read import LocalRPC
    ask = LocalRPC(a.rpc, timeout=20).request
    manifest = st.load_manifest(a.manifest)
    st.verify_deployment(ask, manifest)
    console = Console(ask, manifest, a.mode, a.state, a.beacon, a.rewards_dir)
    if a.public_instance is not None and (a.mode != "public" or not re.fullmatch(r"[0-9a-f]{32}", a.public_instance)):
        p.error("invalid public instance")
    console.public_instance = a.public_instance
    # Public exposure happens only through the separate tunnel/reverse proxy,
    # which must point at a --mode public instance. Always bind loopback.
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(console)).serve_forever()


if __name__ == "__main__":
    main()
