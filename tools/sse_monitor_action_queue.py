"""R5 owner-local, nonexecuting monitor work queue over a saved R4 event journal.

Reads (never mutates) existing scanner SQLite notifications using SQLite
mode=ro; rechecks block hashes, chain, selected monitor and lease state
against a fresh read-only hash-pinned EVM snapshot. This outputs REVIEW
suggestions, not monitor signing authorizations, physical SLA judgments,
operator-independence certificates, or Ethereum transactions.

The backed-up event archive is NOT authoritative: only the current chain
inspection determines whether a task is still relevant. Trust in RPC
canonicality is distinct from independently verified PoS finality.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from sse_chain_read import inspect_chain
from sse_monitor_discovery import DiscoveryError, _block, _quantity
from sse_node_role_policy import role_manifest

ZERO = "0x" + "00" * 32
KINDS = frozenset(("COMMITTEE_ASSIGNED", "EPOCH_ADMITTED"))
STATES = frozenset(("REVIEW_CONFIRMATION", "REVIEW_EVIDENCE_CAPTURE"))
MAX_ITEMS = 64


def _safe_snapshot(snapshot, *, chain_id, settlement, lease_id):
    if (type(snapshot) is not dict or
            snapshot.get("schema") != "sse-onchain-inspection-v1" or
            snapshot.get("readOnly") is not True or
            snapshot.get("domainSeparatorMatches") is not True or
            snapshot.get("blockHashPinned") is not True or
            snapshot.get("chainId") != chain_id or
            snapshot.get("settlementAddress", "").lower() != settlement.lower() or
            snapshot.get("leaseId") != lease_id):
        raise DiscoveryError("work-queue inspection is not chain-bound")
    lease = snapshot.get("lease")
    if type(lease) is not dict:
        raise DiscoveryError("work-queue inspection missing lease")
    return lease


def _task(node, record, snapshot, chain_id, settlement):
    lease = _safe_snapshot(snapshot,chain_id=chain_id,
                           settlement=settlement,lease_id=record["leaseId"])
    parties = [lease.get("consumer"),lease.get("provider")]
    if any(type(x) is not str or len(x) != 42 or
           not x.lower().startswith("0x") for x in parties):
        raise DiscoveryError("invalid lease counterparties")
    owners = {x.lower() for x in parties}
    me = node["wallets"]["monitor"]
    monitors = lease.get("monitors")
    selected = (type(monitors) is list and len(monitors) == 4 and
                all(type(x) is str for x in monitors) and
                len({x.lower() for x in monitors}) == 4 and
                me in {x.lower() for x in monitors})
    funded = (type(lease.get("marketplaceRequestId")) is int and
              lease["marketplaceRequestId"] > 0 and
              type(lease.get("totalEscrow")) is int and lease["totalEscrow"] > 0 and
              lease.get("slaPolicyHash") not in (None, ZERO) and
              lease.get("resourceProfileHash") not in (None, ZERO))
    usable = funded and selected and not owners.intersection(node["wallets"].values())

    action = "NO_LONGER_ACTIONABLE"
    proposal = None
    if usable and record["kind"] == "COMMITTEE_ASSIGNED":
        if (lease.get("assignmentId") == record["sequenceId"] and
                lease.get("stateName") == "Accepted" and
                type(lease.get("monitorConfirmations")) is int and
                lease["monitorConfirmations"] < 4):
            action = "REVIEW_CONFIRMATION"
            proposal = {"role": "monitor", "action": "monitor-confirm",
                        "params": {"lease_id":record["leaseId"]}}
    elif usable and record["kind"] == "EPOCH_ADMITTED":
        epoch = snapshot.get("epoch")
        if (snapshot.get("status") == "EPOCH_FOUND" and
                snapshot.get("epochId") == record["sequenceId"] and
                type(epoch) is dict and epoch.get("exists") is True and
                lease.get("stateName") == "Active" and
                lease.get("monitorConfirmations") == 4 and
                epoch.get("monitoringSealed") is False and
                epoch.get("evidenceClosed") is False and
                type(snapshot.get("blockTimestamp")) is int and
                type(epoch.get("monitoringClose")) is int and
                snapshot["blockTimestamp"] <= epoch["monitoringClose"]):
            action = "REVIEW_EVIDENCE_CAPTURE"
            proposal = {"role": "monitor", "action": "monitor-capture-once",
                        "params": {"leaseId":record["leaseId"],
                                   "epochId":record["sequenceId"]}}
    return {
        "kind":record["kind"], "leaseId":record["leaseId"],
        "sequenceId":record["sequenceId"], "eventBlockNumber":record["blockNumber"],
        "eventBlockHash":record["blockHash"], "status":action,
        "proposal":proposal, "monitor":me,
        "approvalRequired":True, "roleSignerLoaded":False,
        "individualConfirmationKnown":False,
        "physicalSlaVerified":False,"operatorIndependenceVerified":False,
        "finalityVerified":False,"votesSubmitted":False,
    }


class MonitorActionQueue:
    """Read-only review over an existing monitor-discovery SQLite journal."""

    def __init__(self, node_manifest, journal, chain_id, settlement, limit=MAX_ITEMS):
        self.node=role_manifest(node_manifest)
        if "monitor" not in self.node["roles"]:
            raise DiscoveryError("monitor role not configured on this VM")
        if (type(chain_id) is not int or not 0 < chain_id < 2**63 or
                type(settlement) is not str or
                not settlement.startswith("0x") or len(settlement) != 42 or
                type(limit) is not int or not 1 <= limit <= MAX_ITEMS):
            raise DiscoveryError("invalid monitor queue chain, contract or limit")
        self.chain_id,self.settlement,self.limit=chain_id,settlement.lower(),limit
        self.path=Path(journal)
        if (not self.path.is_absolute() or self.path.is_symlink() or
                not self.path.is_file() or self.path.parent.is_symlink()):
            raise DiscoveryError("queue requires existing nonsymlink monitor journal")
        if os.name=="posix":
            parent=self.path.parent.stat()
            child=self.path.stat()
            if (parent.st_uid!=os.geteuid() or
                    stat.S_IMODE(parent.st_mode)&0o077 or
                    child.st_uid!=os.geteuid() or
                    not stat.S_ISREG(child.st_mode) or
                    stat.S_IMODE(child.st_mode)&0o077):
                raise DiscoveryError("queue journal permissions must be owner-only")

    def _read(self):
        # mode=ro forbids checkpoint, schema, cursor or notification writes.
        try:
            with closing(sqlite3.connect(self.path.as_uri()+"?mode=ro",
                                         uri=True,timeout=10)) as db:
                db.execute("PRAGMA query_only=ON")
                row=db.execute("SELECT chain_id,settlement,monitor,last_block,last_hash "
                               "FROM cursor WHERE id=1").fetchone()
                total=db.execute("SELECT COUNT(*) FROM monitor_notifications").fetchone()[0]
                entries=db.execute("""SELECT kind,lease_id,sequence_id,state,
                     block_number,block_hash FROM monitor_notifications
                     ORDER BY block_number DESC,lease_id DESC,sequence_id DESC
                     LIMIT ?""",(self.limit,)).fetchall()
        except sqlite3.Error as exc:
            raise DiscoveryError("monitor review journal unavailable or damaged") from exc
        if (row is None or row[0] != self.chain_id or
                row[1] != self.settlement or
                row[2] != self.node["wallets"]["monitor"] or
                type(row[3]) is not int or type(row[4]) is not str):
            raise DiscoveryError("review journal belongs to another chain or monitor")
        decoded=[]
        for kind,lease,seq,state,n,h in entries:
            if (kind not in KINDS or state not in STATES or
                    type(lease) is not int or lease < 1 or
                    type(seq) is not int or seq < 0 or
                    type(n) is not int or n < 0 or
                    type(h) is not str or not h.startswith("0x") or len(h)!=66):
                raise DiscoveryError("invalid stored monitor event")
            decoded.append({"kind":kind,"leaseId":lease,"sequenceId":seq,
                            "state":state,"blockNumber":n,"blockHash":h})
        return row[3],row[4],total,decoded

    def review(self,rpc,inspector=inspect_chain):
        last,hash_at_last,total,entries=self._read()
        if _quantity(rpc.request("eth_chainId",[])) != self.chain_id:
            raise DiscoveryError("queue RPC is on the wrong chain")
        if hash_at_last and _block(rpc,last) != hash_at_last:
            raise DiscoveryError("queue scan cursor was reorged; no task review")
        if entries and max(x["blockNumber"] for x in entries) > last:
            raise DiscoveryError("notification newer than durable scan cursor")
        # Check EVERY displayed event block, not just the final cursor.
        for n in sorted({x["blockNumber"] for x in entries}):
            canonical=_block(rpc,n)
            if any(x["blockHash"] != canonical
                   for x in entries if x["blockNumber"]==n):
                raise DiscoveryError("previously archived monitor event reorged")
        tasks=[]
        for event in entries:
            snap=inspector(rpc,self.settlement,event["leaseId"],
                           event["sequenceId"] if event["kind"]=="EPOCH_ADMITTED" else 0,
                           expected_chain_id=self.chain_id,pin_block_hash=True)
            tasks.append(_task(self.node,event,snap,self.chain_id,self.settlement))
        if hash_at_last and _block(rpc,last) != hash_at_last:
            raise DiscoveryError("queue cursor reorged while reviewing tasks")
        return {
            "schema":"sse-monitor-work-queue-v1",
            "nodeId":self.node["nodeId"],"monitor":self.node["wallets"]["monitor"],
            "cursorBlock":last,"cursorBlockHash":hash_at_last,
            "totalNotifications":total,"visibleNotifications":len(tasks),
            "moreNotificationsExist":total>len(tasks),
            "tasks":tasks,"readOnly":True,
            "signerLoaded":False,"transactionsSent":False,
            "autoCapturePerformed":False,"finalityVerified":False,
        }
