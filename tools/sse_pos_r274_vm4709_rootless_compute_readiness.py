#!/usr/bin/env python3
"""R274: VM4709 rootless isolated compute worker PRE-FLIGHT ONLY.

Owner-local, read-only check for isolated Docker rootless prerequisites.
This is NOT a rootless-Docker installer, a request to modify the existing
rootful Besu/Lighthouse daemon, a privilege grant or proof that a worker runs.
No sudo, no Docker API calls, no transactions, no key or keystore reads.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import sys

OWNER="ayoubakrvm4709"
RANGE_LIMIT=2**32
UID_MAP_MIN=65536

class Refused(ValueError):
    pass


def ranges(text,username):
    """Return public user subuid/subgid mapping summary, never modify it."""
    if type(text) is not str:
        raise Refused("invalid subordinate ID text")
    matching=[]
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts=line.split(":")
        if len(parts)!=3:
            continue
        name,start,count=parts
        if name!=username:
            continue
        if (not start.isdecimal() or not count.isdecimal()
            or int(start)>=RANGE_LIMIT or int(count)>RANGE_LIMIT):
            raise Refused("invalid subordinate ID range for operator")
        a,b=int(start),int(count)
        if a+b>RANGE_LIMIT:
            raise Refused("subordinate ID range overflows")
        matching.append({"start":a,"count":b})
    return matching


def socket_state(path,uid):
    """Report exact owner rootless UNIX Docker socket, never connect to it."""
    if path.is_symlink():
        return {"state":"SYMLINK_REFUSED"}
    try:
        info=path.stat()
    except FileNotFoundError:
        return {"state":"NOT_CREATED"}
    except OSError:
        return {"state":"UNAVAILABLE"}
    if not stat.S_ISSOCK(info.st_mode):
        return {"state":"NOT_UNIX_SOCKET"}
    if info.st_uid!=uid:
        return {"state":"NOT_OWNED_BY_CALLER"}
    return {"state":"EXISTING_OWNER_SOCKET" if os.access(path,os.R_OK | os.W_OK)
            else "UNREADABLE"}


def collect(*,read_file=None,which=shutil.which):
    if os.name!="posix" or not sys.platform.startswith("linux"):
        raise Refused("VM4709 Linux only")
    uid=os.geteuid()
    if uid==0 or pwd.getpwuid(uid).pw_name!=OWNER:
        raise Refused("requires nonroot VM4709 owner")
    if read_file is None:
        read_file=lambda p:Path(p).read_text("ascii")
    binaries={name:bool(which(name)) for name in (
        "dockerd-rootless-setuptool.sh","dockerd-rootless.sh",
        "rootlesskit","slirp4netns","newuidmap","newgidmap","docker"
    )}
    maps={}
    for kind in ("subuid","subgid"):
        try:
            mapping=ranges(read_file("/etc/"+kind),OWNER)
        except (OSError,UnicodeError):
            mapping=[]
        maps[kind]={
            "ranges":mapping,
            "atLeast65536ContiguousIds":any(v["count"]>=UID_MAP_MIN for v in mapping),
        }
    runtime=os.environ.get("XDG_RUNTIME_DIR")
    expected="/run/user/"+str(uid)
    runtime_matches=runtime==expected
    directory=Path(expected)
    if directory.is_symlink():
        runtime_state="SYMLINK_REFUSED"
    elif not directory.is_dir():
        runtime_state="NOT_PRESENT"
    elif directory.stat().st_uid!=uid or stat.S_IMODE(directory.stat().st_mode)!=0o700:
        runtime_state="NOT_OWNER_PRIVATE_0700"
    else:
        runtime_state="OWNER_PRIVATE_0700"
    socket=socket_state(directory/"docker.sock",uid)
    prerequisites=(all(binaries[k] for k in (
        "dockerd-rootless-setuptool.sh","dockerd-rootless.sh",
        "rootlesskit","newuidmap","newgidmap","docker"
    )) and
        maps["subuid"]["atLeast65536ContiguousIds"] and
        maps["subgid"]["atLeast65536ContiguousIds"] and
        runtime_matches and runtime_state=="OWNER_PRIVATE_0700")
    return {
        "schema":"SSE_R274_VM4709_OWNER_ROOTLESS_COMPUTE_READINESS_ONLY_V1",
        "actualHostUser":OWNER,
        "uid":uid,
        "rootlessBinariesFound":binaries,
        "subordinateIdMappings":maps,
        "expectedUserRuntimeDirectory":expected,
        "xdgRuntimeDirExactlyOwnerPath":runtime_matches,
        "ownerRuntimeDirectoryState":runtime_state,
        "ownerRootlessDockerSocket":socket,
        "rootlessPrerequisitesPresent":bool(prerequisites),
        "rootlessDaemonActuallyRunningVerified":False,
        "computeWorkerActuallyRunningVerified":False,
        "nativePoSRootfulDaemonModified":False,
        "ownerAddedToPrivilegedDockerGroup":False,
        "privilegedCommandExecuted":False,
        "packageInstalled":False,
        "rootlessServiceInstalledOrStarted":False,
        "walletOrValidatorKeyRead":False,
        "transactionSignedOrSent":False,
        "suggestedNextAction":(
            "EXISTING_OWNER_ROOTLESS_SOCKET_REQUIRES_SEPARATE_REAL_DOCKER_INSPECTION"
            if socket["state"]=="EXISTING_OWNER_SOCKET"
            else "REVIEW_ROOTLESS_PREREQUISITES_AND_SEPARATE_OPERATOR_INSTALL_APPROVAL"
        )
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only",action="store_true")
    opts=parser.parse_args(argv)
    try:
        if not opts.inventory_only:
            raise Refused("--inventory-only is required; no install mode exists")
        print(json.dumps(collect(),indent=2,sort_keys=True))
        print("R274_VM4709_ROOTLESS_COMPUTE_PREFLIGHT_READONLY_NO_CHANGES=true")
        return 0
    except (Refused,OSError,UnicodeError,ValueError,TypeError,KeyError) as exc:
        print("R274_READONLY_ROOTLESS_PREFLIGHT_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
