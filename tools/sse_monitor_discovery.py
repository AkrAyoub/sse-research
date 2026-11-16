"""Read-only, checkpointed SSE monitor assignment / epoch event discovery.

Discovers on-chain CommitteeAssigned and EpochAdmitted events for the *local*
monitor wallet. It never signs or sends an Ethereum transaction, probes a
provider, starts containers, or adjudicates an SLA. The output is a durable
list of *candidates* for human-reviewed role-owned execution.

RPC remains a trusted source; a pinned RPC block hash is NOT consensus
finality or physical monitor/operator independence.
"""
from __future__ import annotations

import os
import re
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from sse_challenge import keccak256
from sse_chain_read import inspect_chain
from sse_node_role_policy import (RolePolicyError, role_manifest,
                                  authorize_selected_monitor)

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")
TOPIC_COMMITTEE = "0x" + keccak256(b"CommitteeAssigned(uint256,uint256)").hex()
TOPIC_EPOCH = "0x" + keccak256(b"EpochAdmitted(uint256,uint256,bytes32)").hex()
KIND = {TOPIC_COMMITTEE: "COMMITTEE_ASSIGNED", TOPIC_EPOCH: "EPOCH_ADMITTED"}
ZERO = "0x" + "00" * 32
MAX_LOGS = 1024


class DiscoveryError(ValueError):
    pass


def _quantity(v):
    if type(v) is not str or not re.fullmatch(r"0x[0-9a-fA-F]+", v):
        raise DiscoveryError("RPC returned malformed block/log quantity")
    return int(v, 16)


def _hash(v):
    if type(v) is not str or not HASH.fullmatch(v) or int(v, 16) == 0:
        raise DiscoveryError("RPC returned malformed block/transaction hash")
    return v.lower()


def _block(rpc, n):
    data = rpc.request("eth_getBlockByNumber", [hex(n), False])
    if type(data) is not dict or _quantity(data.get("number")) != n:
        raise DiscoveryError("RPC block number changed during scan")
    return _hash(data.get("hash"))


def parse_log(item, settlement, start, end):
    if type(item) is not dict or type(item.get("address")) is not str or (
            item["address"].lower() != settlement.lower()):
        raise DiscoveryError("foreign event origin")
    if item.get("removed") is not False:
        raise DiscoveryError("removed or ambiguous event")
    topics = item.get("topics")
    if type(topics) is not list or len(topics) != 3:
        raise DiscoveryError("unexpected indexed event schema")
    sig = topics[0].lower() if type(topics[0]) is str else ""
    if sig not in KIND or any(type(t) is not str or not HASH.fullmatch(t) for t in topics):
        raise DiscoveryError("unknown or malformed SSE event signature")
    lease, value = int(topics[1], 16), int(topics[2], 16)
    # SQLite INTEGER is signed int64; reject huge EVM indices rather than
    # silently corrupting the local cursor/notification state.
    if not 0 < lease < 2**63 or not 0 <= value < 2**63:
        raise DiscoveryError("indexed lease/epoch/assignment exceeds journal range")
    payload = item.get("data")
    if type(payload) is not str or (len(payload) != (66 if sig == TOPIC_EPOCH else 2)) or (
            sig == TOPIC_EPOCH and (not HASH.fullmatch(payload) or payload.lower() == ZERO)) or (
            sig == TOPIC_COMMITTEE and payload != "0x"):
        raise DiscoveryError("malformed event data")
    block = _quantity(item.get("blockNumber"))
    if not start <= block <= end:
        raise DiscoveryError("event outside requested range")
    index = _quantity(item.get("logIndex"))
    tx = _hash(item.get("transactionHash"))
    return {
        "kind": KIND[sig], "leaseId": lease,
        "epochId": value if sig == TOPIC_EPOCH else None,
        "assignmentId": value if sig == TOPIC_COMMITTEE else None,
        "requestHash": payload.lower() if sig == TOPIC_EPOCH else None,
        "blockNumber": block, "blockHash": _hash(item.get("blockHash")),
        "txHash": tx, "logIndex": index,
    }


def _locally_unconflicted(node, lease):
    parties = [lease.get("consumer"), lease.get("provider")]
    if any(type(x) is not str or not ADDRESS.fullmatch(x) for x in parties):
        raise DiscoveryError("invalid lease counterparty address")
    counterparty = {x.lower() for x in parties}
    return not counterparty.intersection(node["wallets"].values())


def candidate_for_event(node, record, snapshot, *, chain_id, settlement):
    """Return an owner-visible event or None; never a voting authorization."""
    if (type(snapshot) is not dict or
            snapshot.get("schema") != "sse-onchain-inspection-v1" or
            snapshot.get("readOnly") is not True or
            snapshot.get("blockHashPinned") is not True or
            snapshot.get("domainSeparatorMatches") is not True or
            snapshot.get("chainId") != chain_id or
            snapshot.get("settlementAddress", "").lower() != settlement.lower() or
            snapshot.get("leaseId") != record["leaseId"]):
        raise DiscoveryError("on-chain inspection did not authenticate scope")
    lease = snapshot.get("lease")
    if type(lease) is not dict:
        raise DiscoveryError("on-chain inspection missing lease")
    if (lease.get("marketplaceRequestId", 0) < 1 or
            lease.get("totalEscrow", 0) < 1 or
            lease.get("resourceProfileHash") in (None, ZERO) or
            lease.get("slaPolicyHash") in (None, ZERO)):
        return None
    if not _locally_unconflicted(node, lease):
        return None
    selected = lease.get("monitors")
    me = node["wallets"]["monitor"]
    if (type(selected) is not list or len(selected) != 4 or
            len({str(x).lower() for x in selected}) != 4 or
            me not in {str(x).lower() for x in selected}):
        return None
    if record["kind"] == "COMMITTEE_ASSIGNED":
        if (lease.get("assignmentId") != record["assignmentId"] or
                lease.get("stateName") not in ("Accepted", "Active")):
            return None
        state = "REVIEW_CONFIRMATION"
    else:
        if (snapshot.get("status") != "EPOCH_FOUND" or
                snapshot.get("epochId") != record["epochId"] or
                type(snapshot.get("epoch")) is not dict or
                snapshot["epoch"].get("requestHash") != record["requestHash"]):
            raise DiscoveryError("admission event does not match pinned epoch")
        try:
            authorize_selected_monitor(node, snapshot, me)
        except RolePolicyError:
            # Closed, unconfirmed or conflicted epoch is not actionable.
            return None
        if (type(snapshot.get("blockTimestamp")) is not int or
                type(snapshot["epoch"].get("monitoringClose")) is not int or
                snapshot["blockTimestamp"] > snapshot["epoch"]["monitoringClose"]):
            return None
        state = "REVIEW_EVIDENCE_CAPTURE"
    return {**record, "state": state, "monitor": me,
            "localConflictChecked": True, "operatorIndependenceVerified": False,
            "monitorVoteAuthorized": False, "physicalSlaVerified": False,
            "chainFinalityVerified": False}


class MonitorDiscovery:
    """Crash-safe scan cursor + bounded, reorg-checked public event notifications."""

    def __init__(self, db_file, node_manifest, chain_id, settlement,
                 start_block, confirmations=2, max_blocks=128):
        self.node = role_manifest(node_manifest)
        if "monitor" not in self.node["roles"]:
            raise DiscoveryError("node has no monitor role")
        if (type(chain_id) is not int or chain_id < 1 or
                type(settlement) is not str or not ADDRESS.fullmatch(settlement) or
                int(settlement, 16) == 0):
            raise DiscoveryError("invalid SSE chain/settlement")
        if (type(start_block) is not int or start_block < 0 or
                type(confirmations) is not int or not 0 <= confirmations <= 256 or
                type(max_blocks) is not int or not 1 <= max_blocks <= 256):
            raise DiscoveryError("unsafe scan block range")
        self.chain_id, self.settlement = chain_id, settlement.lower()
        self.start_block, self.confirmations, self.max_blocks = (
            start_block, confirmations, max_blocks)
        self.path = Path(db_file)
        if not self.path.is_absolute() or self.path.is_symlink():
            raise DiscoveryError("monitor journal must be an absolute nonsymlink path")
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            raise DiscoveryError("monitor journal directory must preexist")
        if os.name == "posix":
            st = self.path.parent.stat()
            if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) & 0o077:
                raise DiscoveryError("monitor journal parent must be owner-only")
            if self.path.exists():
                st = self.path.stat()
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or stat.S_IMODE(st.st_mode) & 0o077):
                    raise DiscoveryError("monitor journal must be owner-only regular file")
        if not self.path.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(self.path, flags, 0o600)
            except FileExistsError as exc:
                raise DiscoveryError("monitor journal created concurrently") from exc
            else:
                os.close(fd)
        self._init_db()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _init_db(self):
        with closing(self._connect()) as db:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS cursor (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    chain_id INTEGER NOT NULL, settlement TEXT NOT NULL,
                    monitor TEXT NOT NULL, start_block INTEGER NOT NULL,
                    last_block INTEGER NOT NULL, last_hash TEXT NOT NULL)""")
                db.execute("""CREATE TABLE IF NOT EXISTS monitor_notifications (
                    kind TEXT NOT NULL, lease_id INTEGER NOT NULL,
                    sequence_id INTEGER NOT NULL, state TEXT NOT NULL,
                    block_number INTEGER NOT NULL, block_hash TEXT NOT NULL,
                    tx_hash TEXT NOT NULL, log_index INTEGER NOT NULL,
                    PRIMARY KEY(kind, lease_id, sequence_id))""")
                row = db.execute("SELECT chain_id,settlement,monitor,start_block FROM cursor "
                                 "WHERE id=1").fetchone()
                expected = (self.chain_id, self.settlement,
                            self.node["wallets"]["monitor"], self.start_block)
                if row is None:
                    db.execute("INSERT INTO cursor VALUES(1,?,?,?,?,?,?)",
                               (*expected, self.start_block - 1, ""))
                elif tuple(row) != expected:
                    raise DiscoveryError("journal belongs to different chain/node/start block")

    def status(self):
        with closing(self._connect()) as db:
            last = db.execute("SELECT last_block,last_hash FROM cursor WHERE id=1").fetchone()
            total = db.execute("SELECT COUNT(*) FROM monitor_notifications").fetchone()[0]
            notifications = db.execute(
                "SELECT kind,lease_id,sequence_id,state,block_number,block_hash "
                "FROM monitor_notifications ORDER BY block_number DESC,lease_id DESC,"
                "sequence_id DESC LIMIT 128"
            ).fetchall()
        return {"lastBlock": last[0], "lastBlockHash": last[1],
                "totalNotifications": total,
                "notifications": [
                    dict(zip(("kind","leaseId","sequenceId","state","blockNumber","blockHash"), x))
                    for x in notifications]}

    def scan(self, rpc, inspector=inspect_chain):
        if _quantity(rpc.request("eth_chainId", [])) != self.chain_id:
            raise DiscoveryError("monitor RPC chain ID mismatch")
        cursor = self.status()
        last, last_hash = cursor["lastBlock"], cursor["lastBlockHash"]
        if last_hash and _block(rpc, last) != last_hash:
            raise DiscoveryError("stored cursor block reorged; manual review required")
        head = _quantity(rpc.request("eth_blockNumber", []))
        if head < self.confirmations:
            return {"new": [], "status": self.status(), "waitingForBlocks": True}
        safe = head - self.confirmations
        begin = max(self.start_block, last + 1)
        if begin > safe:
            return {"new": [], "status": self.status(), "waitingForBlocks": True}
        end = min(safe, begin + self.max_blocks - 1)
        raw = rpc.request("eth_getLogs", [{"address": self.settlement,
               "fromBlock":hex(begin), "toBlock":hex(end),
               "topics":[[TOPIC_COMMITTEE,TOPIC_EPOCH]]}])
        if type(raw) is not list or len(raw) > MAX_LOGS:
            raise DiscoveryError("RPC event batch malformed or oversized")
        parsed = [parse_log(item,self.settlement,begin,end) for item in raw]
        if len({(x["txHash"],x["logIndex"]) for x in parsed}) != len(parsed):
            raise DiscoveryError("duplicated log identity")
        for n in {x["blockNumber"] for x in parsed}:
            canonical = _block(rpc,n)
            if any(x["blockHash"] != canonical for x in parsed if x["blockNumber"] == n):
                raise DiscoveryError("RPC log block is not canonical at observed height")
        found = []
        for event in parsed:
            state = inspector(rpc,self.settlement,event["leaseId"],
                   event["epochId"] if event["epochId"] is not None else 0,
                   expected_chain_id=self.chain_id,pin_block_hash=True)
            candidate = candidate_for_event(
                self.node,event,state,chain_id=self.chain_id,settlement=self.settlement)
            if candidate is not None:
                found.append(candidate)
        end_hash = _block(rpc,end)
        # Check the original cursor again: no commits after detected reorg.
        if last_hash and _block(rpc,last) != last_hash:
            raise DiscoveryError("scan cursor reorged during RPC calls")
        with closing(self._connect()) as db:
            with db:
                observed=db.execute("SELECT last_block,last_hash FROM cursor "
                                    "WHERE id=1").fetchone()
                if observed != (last,last_hash):
                    raise DiscoveryError("concurrent monitor journal writer; refuse to advance")
                inserted=[]
                for candidate in found:
                    sequence=(candidate["assignmentId"] if
                              candidate["kind"] == "COMMITTEE_ASSIGNED" else candidate["epochId"])
                    row=db.execute("SELECT block_hash FROM monitor_notifications WHERE "
                           "kind=? AND lease_id=? AND sequence_id=?",
                           (candidate["kind"],candidate["leaseId"],sequence)).fetchone()
                    if row is not None:
                        if row[0] != candidate["blockHash"]:
                            raise DiscoveryError("conflicting persisted monitor event")
                        continue
                    db.execute("""INSERT INTO monitor_notifications VALUES(?,?,?,?,?,?,?,?)""",
                               (candidate["kind"],candidate["leaseId"],sequence,
                                candidate["state"],candidate["blockNumber"],candidate["blockHash"],
                                candidate["txHash"],candidate["logIndex"]))
                    inserted.append(candidate)
                db.execute("UPDATE cursor SET last_block=?, last_hash=? WHERE id=1",
                           (end,end_hash))
        return {"new": inserted, "status": self.status(),
                "waitingForBlocks": False, "confirmedThrough": end,
                "finalityVerified": False, "transactionsSent": False}
