#!/usr/bin/env python3
"""R272: existing VM4709 real provider host NONMUTATING capability preflight.

Native real host resource measurements, local Docker socket access via fixed
unix:///var/run/docker.sock and local Python dependencies. No sudo,
privileged Docker management, container start/stop, package installs,
wallet creation, secrets, network mutation, or transactions. A host
capability report is NOT a verified onchain provider or real SLA.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import stat
import subprocess
import sys

EXPECTED_OWNER="ayoubakrvm4709"
DOCKER_SOCKET=Path("/var/run/docker.sock")
MIN_LOGICAL_CPUS=2
MIN_AVAILABLE_MEMORY_BYTES=2 * 1024**3
MIN_DISK_FREE_BYTES=8 * 1024**3


class Refused(ValueError):
    pass


def available_memory(meminfo):
    if type(meminfo) is not str:
        raise Refused("invalid /proc/meminfo")
    for line in meminfo.splitlines():
        words=line.split()
        if len(words)==3 and words[0]=="MemAvailable:" and words[2]=="kB":
            if not words[1].isdecimal():
                break
            value=int(words[1])*1024
            if 0<value<2**63:
                return value
    raise Refused("no bounded Linux MemAvailable field")


def classify_docker_socket(path=DOCKER_SOCKET):
    if path.is_symlink():
        return {"state":"SYMLINK_REFUSED","ownerWritable":False}
    try:
        st=path.stat()
    except FileNotFoundError:
        return {"state":"ABSENT","ownerWritable":False}
    except OSError:
        return {"state":"INACCESSIBLE","ownerWritable":False}
    if not stat.S_ISSOCK(st.st_mode):
        return {"state":"NOT_UNIX_SOCKET","ownerWritable":False}
    can_write=os.access(path,os.W_OK)
    can_read=os.access(path,os.R_OK)
    return {
        "state":"ACCESSIBLE" if can_write and can_read else "PERMISSION_DENIED",
        "ownerWritable":bool(can_write and can_read),
        "socketUid":st.st_uid,
        "socketGid":st.st_gid,
        "socketMode":oct(stat.S_IMODE(st.st_mode)),
    }


def docker_container_listing(*,run=subprocess.run):
    # Fixed localhost Unix socket, never DOCKER_HOST/default context/remote.
    cmd=["docker","--host","unix:///var/run/docker.sock",
         "ps","--format","{{.Names}} {{.Status}}"]
    try:
        result=run(cmd,capture_output=True,text=True,timeout=8,
                   check=False,shell=False)
    except (OSError,subprocess.TimeoutExpired):
        return {"dockerListingStatus":"CLI_UNAVAILABLE_OR_TIMEOUT",
                "dockerContainerNames":[],
                "dockerContainersInspected":False}
    if result.returncode!=0:
        return {"dockerListingStatus":"ACCESS_DENIED_OR_DAEMON_UNAVAILABLE",
                "dockerContainerNames":[],
                "dockerContainersInspected":False}
    raw=result.stdout
    if not isinstance(raw,str) or len(raw)>8192:
        raise Refused("Docker container inventory oversized")
    names=[]
    for line in raw.splitlines():
        name=line.partition(" ")[0]
        if not name or len(name)>128 or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in name
        ):
            raise Refused("Docker reported malformed container identity")
        names.append(name)
    return {"dockerListingStatus":"ACTUAL_CONTAINERS_READONLY_LISTED",
            "dockerContainerNames":names,
            "dockerContainersInspected":False}


def collect(*,meminfo=None,docker_query=docker_container_listing):
    if os.name!="posix" or not sys.platform.startswith("linux"):
        raise Refused("real VM4709 Linux required")
    uid=os.geteuid()
    if uid==0 or pwd.getpwuid(uid).pw_name!=EXPECTED_OWNER:
        raise Refused("run only as original non-root VM4709 owner")
    count=os.cpu_count()
    if type(count) is not int or not 1<=count<=4096:
        raise Refused("CPU inventory unavailable")
    home=Path.home()
    space=shutil.disk_usage(home)
    if meminfo is None:
        meminfo=Path("/proc/meminfo").read_text("ascii")
    mem=available_memory(meminfo)
    docker=classify_docker_socket()
    report={
        "schema":"SSE_R272_VM4709_REAL_PROVIDER_HOST_READONLY_PREFLIGHT_V1",
        "hostRoleProposed":"compute-provider",
        "sourceRoleActualNativePoSNodePreviouslyObserved":True,
        "actualProviderOrWorkerRunningProven":False,
        "logicalCpus":count,
        "availableMemoryBytes":mem,
        "freeDiskBytes":space.free,
        "resourceMinimumsMetForProposedIsolatedWorker":(
            count>=MIN_LOGICAL_CPUS and
            mem>=MIN_AVAILABLE_MEMORY_BYTES and
            space.free>=MIN_DISK_FREE_BYTES
        ),
        "dockerCliInstalled":shutil.which("docker") is not None,
        "localDockerSocket":docker,
        "ethAccountInstalledInThisPython":importlib.util.find_spec("eth_account") is not None,
        "venvModuleInstalled":importlib.util.find_spec("venv") is not None,
        "pythonExecutable":sys.executable,
        "newProviderWalletCreated":False,
        "providerTestEthFunded":False,
        "providerHttpsReachabilityVerified":False,
        "realProviderWorkloadOrPhysicalSlaVerified":False,
        "walletOrValidatorKeyRead":False,
        "dockerOrNodeMutated":False,
        "nativeTransactionSent":False,
    }
    if report["dockerCliInstalled"]:
        report.update(docker_query())
    else:
        report.update({"dockerListingStatus":"CLI_NOT_INSTALLED",
                       "dockerContainerNames":[],
                       "dockerContainersInspected":False})
    report["operatorActionNeeded"]=(
        "REVIEW_READONLY_PRIVILEGED_DOCKER_INSPECTION_WITH_OWNER"
        if report["dockerListingStatus"]=="ACCESS_DENIED_OR_DAEMON_UNAVAILABLE"
        else "NONE" if report["dockerListingStatus"]=="ACTUAL_CONTAINERS_READONLY_LISTED"
        else "REVIEW_DOCKER_SERVICE_AND_OWNER_ACCESS"
    )
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory-only",action="store_true",
                   help="no effects; verifies current VM4709 host evidence")
    args=p.parse_args(argv)
    try:
        if not args.inventory_only:
            raise Refused("explicit --inventory-only required")
        report=collect()
        print(json.dumps(report,indent=2,sort_keys=True))
        print("R272_VM4709_PROVIDER_HOST_INVENTORY_ONLY_NO_CHANGES=true")
        return 0
    except (Refused,ValueError,OSError,TypeError) as exc:
        print("R272_VM4709_HOST_PREFLIGHT_REFUSED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
