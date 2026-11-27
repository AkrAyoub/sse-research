#!/usr/bin/env python3
"""SSE V4 read model, durable finalized-event cursor and transaction journal.

SOURCE-ONLY (2026-11-27): never executed. Design rules:
  * All decisions that authorize work (provider execution, monitor voting)
    are taken from FINALIZED state only.
  * The cursor stores (height, hash) of the last processed finalized block and
    refuses to continue if that block is no longer canonical (fail closed).
  * The journal records every signed transaction BEFORE broadcast, keyed by
    (sender, nonce) and by a stable task id. An absent receipt is UNKNOWN and
    blocks further sends from that wallet until reconciled (never blind resend).
  * State files are owner-private (0700 directory) and written atomically.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import sse_v4_abi as abi

CHAIN_ID = 31340
GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
ADDR = re.compile(r"0x[0-9a-f]{40}")
HASH = re.compile(r"0x[0-9a-f]{64}")
MAX_LOG_RANGE = 2000


class StateError(ValueError):
    pass


def require(ok, msg):
    if not ok:
        raise StateError(msg)


# ------------------------------------------------------------------ files
def private_dir(path):
    p = Path(path)
    require(p.is_absolute(), "absolute state directory required")
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not p.is_symlink() and p.is_dir(), "state directory must be a real directory")
    st = p.stat()
    require(st.st_uid == os.geteuid() and not st.st_mode & 0o077, "state directory not owner-private")
    return p


def atomic_write_json(path, obj):
    path = Path(path)
    raw = (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    dfd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def read_json(path, limit=4 * 1024 * 1024):
    path = Path(path)
    if not path.exists():
        return None
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= limit, "bad state file " + str(path))
    return json.loads(path.read_text())


# --------------------------------------------------------------- manifest
def load_manifest(path):
    m = read_json(path, 65536)
    require(isinstance(m, dict) and m.get("schema") == "SSE_V4_DEPLOYMENT_MANIFEST_V1", "wrong manifest schema")
    require(m.get("chainId") == CHAIN_ID and m.get("genesisHash") == GENESIS, "wrong chain identity")
    mods = m.get("modules")
    require(isinstance(mods, dict) and set(mods) == set(abi.MODULES), "manifest must list all five modules")
    for k, v in mods.items():
        require(isinstance(v, str) and ADDR.fullmatch(v.lower() if v else ""), "bad address for " + k)
    require(type(m.get("deploymentBlock")) is int and m["deploymentBlock"] > 0, "deploymentBlock required")
    m["modules"] = {k: v.lower() for k, v in mods.items()}
    return m


def block_identity(block):
    require(isinstance(block, dict), "missing block")
    h, n = block.get("hash"), block.get("number")
    require(isinstance(h, str) and HASH.fullmatch(h.lower()), "bad block hash")
    require(isinstance(n, str) and re.fullmatch(r"0x[0-9a-fA-F]+", n), "bad block number")
    return int(n, 16), h.lower()


def finalized(ask):
    return block_identity(ask("eth_getBlockByNumber", ["finalized", False]))


def verify_deployment(ask, manifest):
    """Read-only identity + wiring check at the finalized block."""
    require(ask("eth_chainId", []) == hex(CHAIN_ID), "wrong chain id")
    require(ask("eth_getBlockByNumber", ["0x0", False])["hash"].lower() == GENESIS, "wrong genesis")
    height, fhash = finalized(ask)
    require(height >= manifest["deploymentBlock"], "deployment not finalized")
    tag = hex(height)
    mods = manifest["modules"]
    expected_hashes = manifest.get("runtimeSha256")
    require(isinstance(expected_hashes, dict) and set(expected_hashes) == set(mods) and
            all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x) for x in expected_hashes.values()),
            "complete verified runtime hashes required")
    hashes = {}
    for name, address in mods.items():
        code = bytes.fromhex(ask("eth_getCode", [address, tag])[2:])
        require(len(code) > 0, name + " has no code")
        hashes[name] = hashlib.sha256(code).hexdigest()
        require(hashes[name] == expected_hashes[name], name + " runtime hash mismatch")
    m = mods["market"]
    for getter, module in (("board()", "board"), ("registry()", "registry"), ("standby()", "standby"),
                           ("votes()", "ledger")):
        require(abi.view(ask, m, getter, out=("address",), tag=tag)[0].lower() == mods[module], "wiring " + getter)
    for module, getter in (("board", "market()"), ("registry", "market()"), ("standby", "market()"),
                           ("ledger", "settlement()")):
        require(abi.view(ask, mods[module], getter, out=("address",), tag=tag)[0].lower() == m, "back-wiring " + module)
    return {"finalizedHeight": height, "finalizedHash": fhash, "runtimeSha256": hashes,
            "manifestRuntimeHashesMatched": True}


# ------------------------------------------------------------- read model
class Reader:
    """Bounded, paginated reads at one pinned block tag."""

    def __init__(self, ask, manifest, tag="finalized"):
        self.ask, self.m, self.tag = ask, manifest["modules"], tag

    def _v(self, module, sig, types=(), args=(), out=("uint256",)):
        return abi.view(self.ask, self.m[module], sig, types, args, out, self.tag)

    def counts(self):
        return {"requests": self._v("board", "nextRequestId()")[0] - 1,
                "leases": self._v("market", "nextLeaseId()")[0] - 1,
                "rosterEntries": self._v("registry", "rosterLength()")[0],
                "activeMonitors": self._v("registry", "activeEntries()")[0]}

    def request(self, rid):
        return abi.read_struct(self.ask, self.m["board"], "request(uint256)", ("uint256",), (rid,),
                               abi.REQUEST_FIELDS, self.tag)

    def bids(self, rid, offset=0, limit=50):
        limit = max(1, min(limit, 100))
        t = abi.tuple_type(abi.BID_FIELDS)
        rows = self._v("board", "bidsInRange(uint256,uint256,uint256)", ("uint256", "uint256", "uint256"),
                       (rid, offset, limit), (t + "[]",))[0]
        return [dict(abi.as_dict(abi.BID_FIELDS, r), index=offset + i) for i, r in enumerate(rows)]

    def lease(self, lid):
        return abi.read_struct(self.ask, self.m["market"], "lease(uint256)", ("uint256",), (lid,),
                               abi.LEASE_FIELDS, self.tag)

    def market_epoch(self, lid, e):
        return abi.read_struct(self.ask, self.m["market"], "epoch(uint256,uint256)", ("uint256", "uint256"),
                               (lid, e), abi.MARKET_EPOCH_FIELDS, self.tag)

    def scientific_epoch(self, lid, e):
        return abi.read_struct(self.ask, self.m["market"], "scientificEpoch(uint256,uint256)",
                               ("uint256", "uint256"), (lid, e), abi.SCIENTIFIC_EPOCH_FIELDS, self.tag)

    def accounting(self, lid):
        v = self._v("market", "scientificAccounting(uint256)", ("uint256",), (lid,),
                    ("uint256",) * 6 + ("bool",))
        return dict(zip(("funded", "available", "exposure", "budget", "providerCredit", "consumerCredit",
                         "conserved"), v))

    def ledger_epoch(self, lid, e):
        return abi.read_struct(self.ask, self.m["ledger"], "epoch(uint256,uint256)", ("uint256", "uint256"),
                               (lid, e), abi.LEDGER_EPOCH_FIELDS, self.tag)

    def committee(self, lid):
        return abi.read_struct(self.ask, self.m["ledger"], "committee(uint256)", ("uint256",), (lid,),
                               abi.COMMITTEE_FIELDS, self.tag)

    def members(self, lid):
        return [a.lower() for a in self._v("ledger", "selected(uint256)", ("uint256",), (lid,), ("address[]",))[0]]

    def assignment(self, lid):
        return abi.read_struct(self.ask, self.m["standby"], "assignment(uint256)", ("uint256",), (lid,),
                               abi.ASSIGNMENT_FIELDS, self.tag)

    def reserved(self, lid):
        return [a.lower() for a in self._v("registry", "reservedFor(uint256)", ("uint256",), (lid,), ("address[]",))[0]]

    def position(self, who):
        v = self._v("registry", "position(address)", ("address",), (who,), ("uint256", "uint256", "uint256", "uint256", "bool"))
        return dict(zip(("bond", "capacity", "reserved", "entryIndexPlusOne", "exiting"), v),
                    available=self._v("registry", "available(address)", ("address",), (who,))[0])

    def eligible(self, exclude_a, exclude_b, page=200):
        total = self._v("registry", "rosterLength()")[0]
        eligible = 0
        for off in range(0, total, page):
            e, _ = self._v("registry", "eligibleInRange(uint256,uint256,address,address)",
                           ("uint256", "uint256", "address", "address"), (off, page, exclude_a, exclude_b),
                           ("uint256", "uint256"))
            eligible += e
        return {"population": total, "eligible": eligible}

    def withdrawable(self, who):
        return {mod: self._v(mod, "withdrawable(address)", ("address",), (who,))[0]
                for mod in ("market", "registry", "ledger")}

    def lease_bundle(self, lid):
        l = self.lease(lid)
        out = {"lease": l, "phase": abi.LEASE_PHASES[l["phase"]], "accounting": self.accounting(lid), "epochs": []}
        if l["phase"] >= 2:
            a = self.assignment(lid)
            out["assignment"] = dict(a, phaseName=abi.STANDBY_PHASES[a["phase"]])
        if l["monitorBudgetTransferred"] and l["phase"] in (3, 4):
            out["committee"] = self.committee(lid)
            out["members"] = self.members(lid)
        # The contract caps leases at 64 epochs. Include older open evidence.
        require(0 <= l["nextEpoch"] <= 64, "invalid epoch count")
        for e in range(l["nextEpoch"]):
            out["epochs"].append({"id": e, "market": self.market_epoch(lid, e), "science": self.scientific_epoch(lid, e),
                                  "votes": self.ledger_epoch(lid, e)})
        out["epochsTruncated"] = False
        return out


# ----------------------------------------------------------------- cursor
class Cursor:
    """Durable finalized-log cursor over the five V4 modules."""

    def __init__(self, ask, manifest, state_dir):
        self.ask, self.manifest = ask, manifest
        self.path = private_dir(state_dir) / "v4-cursor.json"

    def load(self):
        s = read_json(self.path)
        if s is None:
            start = self.manifest["deploymentBlock"] - 1
            block = self.ask("eth_getBlockByNumber", [hex(start), False])
            return {"height": start, "hash": block_identity(block)[1]}
        require(type(s.get("height")) is int and HASH.fullmatch(s.get("hash", "")), "corrupt cursor")
        return s

    def poll(self, max_blocks=MAX_LOG_RANGE):
        """Return (events, new_state). Caller persists via commit() AFTER handling."""
        s = self.load()
        canon = block_identity(self.ask("eth_getBlockByNumber", [hex(s["height"]), False]))
        require(canon == (s["height"], s["hash"]), "cursor block no longer canonical: manual reconciliation required")
        fin, _ = finalized(self.ask)
        if fin <= s["height"]:
            return [], s
        end = min(fin, s["height"] + max_blocks)
        logs = self.ask("eth_getLogs", [{"fromBlock": hex(s["height"] + 1), "toBlock": hex(end),
                                         "address": list(self.manifest["modules"].values())}])
        require(isinstance(logs, list), "bad getLogs result")
        events = []
        for log in logs:
            require(not log.get("removed", False), "removed log in finalized range")
            ev = abi.decode_log(log, self.manifest["modules"])
            if ev is not None:
                events.append(ev)
        events.sort(key=lambda e: (e["blockNumber"], e["logIndex"]))
        end_id = block_identity(self.ask("eth_getBlockByNumber", [hex(end), False]))
        return events, {"height": end_id[0], "hash": end_id[1]}

    def commit(self, state):
        atomic_write_json(self.path, state)


# ---------------------------------------------------------------- journal
class Journal:
    """Signed-intent journal. One file per (sender, nonce) plus a task index."""

    def __init__(self, state_dir):
        self.root = private_dir(Path(state_dir) / "journal")

    @staticmethod
    def task_id(module_address, data, value, key=""):
        return hashlib.sha256(json.dumps([CHAIN_ID, module_address.lower(), data.lower(), value, key]).encode()).hexdigest()

    def entries(self):
        out = []
        for p in sorted(self.root.glob("0x*-*.json")):
            out.append(read_json(p, 65536))
        return out

    def find_task(self, task):
        return [e for e in self.entries() if e["taskId"] == task]

    def unresolved(self, sender):
        return [e for e in self.entries() if e["sender"] == sender.lower() and not e.get("terminal")]

    BLOCKING = ("SIGNED", "UNKNOWN_NO_RECEIPT", "BROADCAST_ERROR_UNKNOWN", "NONCANONICAL_RECEIPT")

    def blocking(self, sender):
        """Entries whose outcome is unknown: no further send from this wallet."""
        return [e for e in self.unresolved(sender) if e.get("status") in self.BLOCKING]

    def record(self, sender, nonce, tx_hash, task, target, data, value, action):
        path = self.root / f"{sender.lower()}-{nonce}.json"
        require(not path.exists(), "nonce already journaled: refusing")
        atomic_write_json(path, {"schema": "SSE_V4_TX_INTENT_V1", "chainId": CHAIN_ID, "sender": sender.lower(),
            "nonce": nonce, "transactionHash": tx_hash.lower(), "taskId": task, "target": target.lower(),
            "calldata": data.lower(), "valueWei": value, "action": action, "terminal": False, "status": "SIGNED"})
        return path

    def update(self, entry, **fields):
        path = self.root / f"{entry['sender']}-{entry['nonce']}.json"
        entry = dict(entry, **fields)
        atomic_write_json(path, entry)
        return entry

    def reconcile(self, ask, entry):
        """Only FINALIZED receipts become terminal. Absent receipts stay UNKNOWN."""
        r = ask("eth_getTransactionReceipt", [entry["transactionHash"]])
        if r is None:
            tx = ask("eth_getTransactionByHash", [entry["transactionHash"]])
            return self.update(entry, status="KNOWN_PENDING" if tx else "UNKNOWN_NO_RECEIPT")
        n = int(r["blockNumber"], 16)
        canon = block_identity(ask("eth_getBlockByNumber", [hex(n), False]))
        if canon[1] != r["blockHash"].lower():
            return self.update(entry, status="NONCANONICAL_RECEIPT")
        fin, _ = finalized(ask)
        ok = int(r["status"], 16) == 1
        status = ("FINALIZED_" if fin >= n else "CANONICAL_") + ("SUCCESS" if ok else "REVERTED")
        return self.update(entry, status=status, terminal=fin >= n, includedHeight=n)
