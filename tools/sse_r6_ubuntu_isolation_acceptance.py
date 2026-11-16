#!/usr/bin/env python3
"""Read-only R6 Ubuntu separation acceptance; never install or start anything.

Use --layout as a privileged *observer* to check ownership/modes of already
provisioned service files. Then run --as-ui as the actual sseagent account
to prove kernel-level access to only the sanitized monitor display and
DENIAL for the monitor's private journal/dir.

Neither check reads file contents: os.open(O_RDONLY|O_NOFOLLOW) then closes.
Even passing these checks does NOT certify ACL absence, process isolation,
RPC integrity, operator independence or SLA settlement correctness.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import stat
import sys
from pathlib import Path

JOURNAL = "/var/lib/sse-monitor/events.sqlite"
DISPLAY = "/run/sse-monitor-display/tasks.json"


class IsolationError(ValueError):
    pass


def _linux():
    if not sys.platform.startswith("linux"):
        raise IsolationError("Linux/Ubuntu is required for real UID/GID acceptance")


def _path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise IsolationError("only absolute paths without parent traversal are permitted")
    return path


def _entry(path, *, directory):
    """Stat the actual node; no symlink target is accepted."""
    path=_path(path)
    try:
        item=path.lstat()
    except OSError as exc:
        raise IsolationError("required R6 asset missing or inaccessible: " + str(path)) from exc
    if (stat.S_ISDIR(item.st_mode) if directory else stat.S_ISREG(item.st_mode)) is False:
        raise IsolationError("R6 asset is not the expected ordinary file/directory: " + str(path))
    return item


def verify_layout(*, monitor_uid, agent_uid, monitor_gid, display_gid,
                  agent_groups, private_dir, journal, display_dir, display_file):
    """Pure POSIX metadata policy for mock testing and host layout inspection."""
    if (not all(type(x) is int and x >= 0 for x in
                (monitor_uid, agent_uid, monitor_gid, display_gid)) or
            monitor_uid == agent_uid or
            type(agent_groups) not in (tuple,list,set,frozenset)):
        raise IsolationError("invalid separation identity metadata")
    groups=set(agent_groups)
    if not all(type(x) is int and x >= 0 for x in groups):
        raise IsolationError("invalid agent group membership")
    if display_gid not in groups or monitor_gid in groups:
        raise IsolationError("UI must join display-only group, NOT private monitor group")
    spec=(
        (private_dir,monitor_uid,monitor_gid,0o700,"private journal directory"),
        (journal,monitor_uid,monitor_gid,0o600,"private journal file"),
        (display_dir,monitor_uid,display_gid,0o750,"public display directory"),
        (display_file,monitor_uid,display_gid,0o640,"public display snapshot"),
    )
    for data,uid,gid,mode,label in spec:
        if (data.st_uid!=uid or data.st_gid!=gid or
                stat.S_IMODE(data.st_mode)!=mode):
            raise IsolationError(label+" has unexpected owner/group or permission bits")
    if display_file.st_size > 65536:
        raise IsolationError("public display snapshot exceeds 64 KiB")
    return {
        "kind":"SSE_R6_UBUNTU_LAYOUT_ACCEPTANCE",
        "privateJournalShared":False,
        "displayGroupReadOnly":True,
        "linuxUserSeparationVerified":True,
        "uiKernelAccessProbed":False,
        "unitsInstalledByCheck":False,
        "ethereumTransactionsSent":False,
        "sensitiveFileContentsRead":False,
    }


def check_layout(journal_path=JOURNAL,display_path=DISPLAY,
                 monitor_user="ssemonitor",agent_user="sseagent",
                 monitor_group="ssemonitor",display_group="ssemonitor-display"):
    _linux()
    import pwd
    import grp
    try:
        mon=pwd.getpwnam(monitor_user)
        agent=pwd.getpwnam(agent_user)
        mon_gid=grp.getgrnam(monitor_group).gr_gid
        display_gid=grp.getgrnam(display_group).gr_gid
    except KeyError as exc:
        raise IsolationError("expected Ubuntu user/group is not provisioned") from exc
    journal=_path(journal_path)
    display=_path(display_path)
    if (str(journal.parent)!="/var/lib/sse-monitor" or
            str(display.parent)!="/run/sse-monitor-display"):
        raise IsolationError("acceptance requires approved private and public service directories")
    groups=os.getgrouplist(agent.pw_name,agent.pw_gid)
    checked=verify_layout(
        monitor_uid=mon.pw_uid,agent_uid=agent.pw_uid,
        monitor_gid=mon_gid,display_gid=display_gid,
        agent_groups=groups,
        private_dir=_entry(journal.parent,directory=True),
        journal=_entry(journal,directory=False),
        display_dir=_entry(display.parent,directory=True),
        display_file=_entry(display,directory=False))
    return {**checked,"monitorUser":monitor_user,"uiUser":agent_user,
            "publicSnapshotPath":str(display),"privateJournalPath":str(journal)}


def _open_readonly_no_follow(path):
    flags=os.O_RDONLY
    for extra in ("O_NOFOLLOW","O_CLOEXEC","O_NONBLOCK"):
        flags |= getattr(os,extra,0)
    fd=os.open(path,flags)
    os.close(fd)


def verify_actual_ui_access(*, actual_uid, expected_uid, display_groups,
                            expected_display_gid, public_path, private_path,
                            private_dir):
    """Must be invoked under actual unprivileged UI identity, never root."""
    if (type(actual_uid) is not int or actual_uid == 0 or
            actual_uid != expected_uid or expected_display_gid not in display_groups):
        raise IsolationError("test must run as unprivileged UI user with display group")
    # The positive test must first succeed, or a broken setup may falsely pass.
    try:
        _open_readonly_no_follow(public_path)
    except OSError as exc:
        raise IsolationError("UI cannot read the expected nonsecret display") from exc
    for protected in (private_dir,private_path):
        try:
            _open_readonly_no_follow(protected)
        except OSError as exc:
            if exc.errno in (errno.EACCES,errno.EPERM):
                continue
            # Missing paths or bad symlinks are *not* proof of isolation.
            raise IsolationError("private monitor asset inaccessible for an unproven reason") from exc
        raise IsolationError("SECURITY FAILURE: UI can open private monitor asset")
    return {
        "kind":"SSE_R6_UBUNTU_UI_ACCESS_ACCEPTANCE",
        "uiPublicSnapshotReadable":True,
        "uiPrivateJournalOpenDenied":True,
        "uiPrivateDirectoryOpenDenied":True,
        "sensitiveFileContentsRead":False,
        "filesWritten":False,"ethereumTransactionsSent":False,
    }


def check_ui_access(journal_path=JOURNAL,display_path=DISPLAY,
                    agent_user="sseagent",display_group="ssemonitor-display"):
    _linux()
    import pwd
    import grp
    try:
        agent=pwd.getpwnam(agent_user)
        display_gid=grp.getgrnam(display_group).gr_gid
    except KeyError as exc:
        raise IsolationError("expected UI account/display group not provisioned") from exc
    journal=_path(journal_path)
    display=_path(display_path)
    if (str(journal.parent)!="/var/lib/sse-monitor" or
            str(display.parent)!="/run/sse-monitor-display"):
        raise IsolationError("nonstandard monitor acceptance directory")
    result=verify_actual_ui_access(
        actual_uid=os.geteuid(),expected_uid=agent.pw_uid,
        display_groups=os.getgroups(),expected_display_gid=display_gid,
        public_path=display,private_path=journal,private_dir=journal.parent)
    return {**result,"uiUser":agent_user}


def main(argv=None):
    parser=argparse.ArgumentParser(description="R6 read-only Ubuntu isolation acceptance")
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--layout",action="store_true",
                       help="verify provisioned service UID/GID and exact file modes")
    group.add_argument("--as-ui",action="store_true",
                       help="under sseagent identity, prove snapshot readable and journal denied")
    args=parser.parse_args(argv)
    try:
        if args.layout:
            result=check_layout()
        elif args.as_ui:
            result=check_ui_access()
        else:
            result={
                "kind":"SSE_R6_UBUNTU_ISOLATION_PLAN",
                "linuxHostVerified":False,
                "checks":["--layout after Ubuntu provisioning",
                          "--as-ui under the actual sseagent account"],
                "privateJournalPath":JOURNAL,
                "publicSnapshotPath":DISPLAY,
                "systemChangesMade":False,
                "ethereumTransactionsSent":False}
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (IsolationError,OSError,TypeError) as exc:
        print("SSE_R6_ISOLATION_CHECK_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
