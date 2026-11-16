"""Safe public monitor work-review snapshot handoff (stdlib-only).

A separately authorized monitor review process exports a *public, non-secret*
view of its recent, read-only chain work queue. The node-local UI can display
it without importing blockchain dependencies, accessing signer files, polling
Ethereum, or opening the monitor's private SQLite journal.

A local file and RPC view are NOT chain finality, physically qualified SLA
evidence, operator independence, owner approval or transaction authority.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "sse-monitor-work-display-v1"
MAX_BYTES = 65536
MAX_AGE_SECONDS = 120
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
STATES = frozenset(("REVIEW_CONFIRMATION",
                    "REVIEW_EVIDENCE_CAPTURE", "NO_LONGER_ACTIONABLE"))
KIND = frozenset(("COMMITTEE_ASSIGNED", "EPOCH_ADMITTED"))


class SnapshotError(ValueError):
    pass


def _pairs(items):
    result = {}
    for k, v in items:
        if k in result:
            raise SnapshotError("duplicate monitor snapshot JSON field")
        result[k] = v
    return result


def _check_path(path, *, writing):
    value = Path(path)
    if not value.is_absolute() or ".." in value.parts:
        raise SnapshotError("monitor display path must be absolute")
    if not value.parent.is_dir() or value.parent.is_symlink() or value.is_symlink():
        raise SnapshotError("monitor display path must use an ordinary directory/file")
    if value.exists() and not value.is_file():
        raise SnapshotError("monitor display path must be a regular file")
    if writing and os.name == "posix":
        parent = value.parent.stat()
        if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o002:
            raise SnapshotError("monitor display export parent must be owned and not world writable")
    return value


def _clean_tasks(tasks):
    if type(tasks) is not list or len(tasks) > 64:
        raise SnapshotError("invalid bounded monitor work tasks")
    out = []
    for task in tasks:
        if type(task) is not dict or task.get("kind") not in KIND or (
                task.get("status") not in STATES):
            raise SnapshotError("unsupported monitor work task")
        lease, sequence = task.get("leaseId"), task.get("sequenceId")
        if (type(lease) is not int or not 1 <= lease < 2**63 or
                type(sequence) is not int or not 0 <= sequence < 2**63):
            raise SnapshotError("invalid monitor work lease/sequence index")
        if (task["status"] == "REVIEW_CONFIRMATION" and
                task["kind"] != "COMMITTEE_ASSIGNED") or (
                task["status"] == "REVIEW_EVIDENCE_CAPTURE" and
                task["kind"] != "EPOCH_ADMITTED"):
            raise SnapshotError("task status mismatches event kind")
        # Public display deliberately discards raw proposed calldata,
        # unverified wallet fields and arbitrary task metadata.
        out.append({"kind": task["kind"], "leaseId": lease,
                    "sequenceId": sequence, "status": task["status"]})
    return out


def make_snapshot(review, *, generated_at=None):
    if (type(review) is not dict or
            review.get("schema") != "sse-monitor-work-queue-v1" or
            review.get("readOnly") is not True or
            review.get("signerLoaded") is not False or
            review.get("transactionsSent") is not False or
            review.get("autoCapturePerformed") is not False or
            review.get("finalityVerified") is not False):
        raise SnapshotError("only nonexecuting review state may be published")
    node, monitor = review.get("nodeId"), review.get("monitor")
    if (type(node) is not str or
            re.fullmatch(r"[a-z][a-z0-9-]{0,62}",node) is None or
            type(monitor) is not str or ADDR.fullmatch(monitor) is None or
            int(monitor, 16) == 0):
        raise SnapshotError("invalid node public monitor identity")
    cursor, total = review.get("cursorBlock"), review.get("totalNotifications")
    if (type(cursor) is not int or cursor < -1 or type(total) is not int or
            total < 0 or total > 2**63 - 1):
        raise SnapshotError("invalid monitor display cursor and count")
    tasks = _clean_tasks(review.get("tasks"))
    if total < len(tasks):
        raise SnapshotError("monitor work count contradicts visible tasks")
    at = generated_at if generated_at is not None else datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise SnapshotError("snapshot requires timezone-aware generation time")
    snapshot = {
        "schema": SCHEMA, "nodeId": node, "monitor": monitor.lower(),
        "generatedAtUtc": at.astimezone(timezone.utc).isoformat(),
        "cursorBlock": cursor, "totalNotifications": total,
        "moreNotificationsExist": total > len(tasks),
        "tasks": tasks, "readOnly": True,
        "signerLoaded": False, "transactionsSent": False,
        "votesSubmitted": False, "physicalSlaVerified": False,
        "operatorIndependenceVerified": False, "finalityVerified": False,
        "ownerApprovalGranted": False,
    }
    if len(json.dumps(snapshot, sort_keys=True).encode("utf-8")) > MAX_BYTES:
        raise SnapshotError("public monitor snapshot is too large")
    return snapshot


def validate_snapshot(data, *, node_id, monitor_address, now=None):
    """Return only a bounded, fresh public schema; never authorize an action."""
    if type(data) is not dict or set(data) != {
            "schema","nodeId","monitor","generatedAtUtc","cursorBlock",
            "totalNotifications","moreNotificationsExist","tasks","readOnly",
            "signerLoaded","transactionsSent","votesSubmitted",
            "physicalSlaVerified","operatorIndependenceVerified",
            "finalityVerified","ownerApprovalGranted"}:
        raise SnapshotError("unexpected monitor display fields")
    if (type(node_id) is not str or data["schema"] != SCHEMA or
            data["nodeId"] != node_id or type(monitor_address) is not str or
            not ADDR.fullmatch(monitor_address) or
            data["monitor"] != monitor_address.lower()):
        raise SnapshotError("monitor snapshot belongs to another node/wallet")
    if any(data[key] is not False for key in
           ("signerLoaded","transactionsSent","votesSubmitted",
            "physicalSlaVerified","operatorIndependenceVerified",
            "finalityVerified","ownerApprovalGranted")) or data["readOnly"] is not True:
        raise SnapshotError("monitor snapshot cannot claim executable authority")
    if type(data["generatedAtUtc"]) is not str:
        raise SnapshotError("monitor snapshot timestamp absent")
    try:
        stamp = datetime.fromisoformat(data["generatedAtUtc"])
        if stamp.tzinfo is None:
            raise ValueError("naive timestamp")
    except (ValueError, OverflowError) as exc:
        raise SnapshotError("invalid monitor snapshot generation time") from exc
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise SnapshotError("current time must be timezone aware")
    age = (current - stamp).total_seconds()
    if not -15 <= age <= MAX_AGE_SECONDS:
        raise SnapshotError("monitor snapshot expired or clock skewed; refresh before review")
    if type(data["tasks"]) is not list:
        raise SnapshotError("invalid monitor display task list")
    if (type(data["cursorBlock"]) is not int or data["cursorBlock"] < -1 or
            type(data["totalNotifications"]) is not int or
            data["totalNotifications"] < 0 or
            data["totalNotifications"] < len(data["tasks"])):
        raise SnapshotError("invalid monitor display counts")
    if _clean_tasks(data["tasks"]) != data["tasks"]:
        raise SnapshotError("monitor display contains unapproved task fields")
    if (type(data["moreNotificationsExist"]) is not bool or
            data["moreNotificationsExist"] != (
                data["totalNotifications"] > len(data["tasks"]))):
        raise SnapshotError("inconsistent monitor display pagination")
    return data


def write_snapshot(path, review, *, generated_at=None):
    """Atomic public snapshot export only after fresh verified queue review."""
    target = _check_path(path, writing=True)
    data = make_snapshot(review, generated_at=generated_at)
    raw = (json.dumps(data,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False)+"\n").encode("ascii")
    if len(raw) > MAX_BYTES:
        raise SnapshotError("monitor snapshot exceeds maximum export size")
    fd, staged = tempfile.mkstemp(prefix=".sse-monitor-display-",dir=target.parent)
    try:
        with os.fdopen(fd,"wb") as stream:
            if hasattr(os,"fchmod"):
                os.fchmod(stream.fileno(),0o600)
            else:
                os.chmod(staged,0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # The parent is owner-controlled; never replace a preexisting symlink.
        if target.is_symlink():
            raise SnapshotError("monitor display symlink cannot be replaced")
        os.replace(staged,target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return data


def read_snapshot(path, *, node_id, monitor_address, now=None):
    target = _check_path(path, writing=False)
    if not target.is_file() or target.stat().st_size > MAX_BYTES:
        raise SnapshotError("monitor display snapshot is missing or oversized")
    try:
        with target.open("rb") as f:
            raw=f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise SnapshotError("monitor display snapshot too large")
        data=json.loads(raw.decode("utf-8"),object_pairs_hook=_pairs)
    except (UnicodeError,ValueError,TypeError) as exc:
        raise SnapshotError("monitor display snapshot is malformed") from exc
    return validate_snapshot(data,node_id=node_id,monitor_address=monitor_address,now=now)
