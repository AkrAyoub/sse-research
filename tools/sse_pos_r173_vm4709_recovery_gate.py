#!/usr/bin/env python3
"""R173 strictly read-only first-runtime recovery diagnosis on VM4709.

Never installs, updates packages, reads wallet/signer material, deletes,
starts/stops a service, configures overlay, or creates new chain data.
Existing R147 selection and pinned R170 archive remain owned by root.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

EXPECTED_SOURCE="df3df85190789cc14fe6920a248f6a7545a44197"
EXPECTED_GENESIS="1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
ROOT=Path("/opt/sse/releases")
STATE=Path("/var/lib/sse/selection.json")

class Refused(ValueError):
    pass

def read_selection(path):
    if (path.is_symlink() or not path.is_file() or
            not 0<path.stat().st_size<=8192 or
            path.stat().st_mode & 0o077):
        raise Refused("private root-owned selection unavailable")
    data=json.loads(path.read_text("utf-8"))
    if (type(data) is not dict or data.get("sourceCommit")!=EXPECTED_SOURCE
            or data.get("selectedRoles")!=["observer"]
            or data.get("network")!="chain31340"
            or data.get("chainGenesisRecreated") is not False
            or data.get("publicSourceDownloaded") is not True
            or data.get("roleSelectionRecorded") is not True
            or type(data.get("nodeId")) is not str
            or not re.fullmatch(r"[a-z][a-z0-9-]{2,62}",data["nodeId"])):
        raise Refused("unexpected saved R170 observer selection; manual review")
    return data

def command(command):
    try:
        result=subprocess.run(command,check=False,capture_output=True,
                              text=True,timeout=10)
    except (OSError,subprocess.TimeoutExpired):
        return None
    return result.returncode,result.stdout.strip()

def diagnose(*,root=ROOT,state=STATE,runner=command):
    selected=read_selection(state)
    release=root/EXPECTED_SOURCE
    if release.is_symlink() or not release.is_dir():
        raise Refused("pinned original release checkout is unavailable")
    archive=release/"original-chain31340.tar.gz"
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size>6_000_000:
        raise Refused("pinned verified original genesis archive missing")
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest!=EXPECTED_GENESIS:
        raise Refused("existing original genesis archive does not match immutable checksum")
    containers=runner(["docker","ps","-a","--format","{{.Names}}"])
    if containers is None or containers[0]!=0:
        # sudo root is used here ONLY for read-only Docker process list.
        raise Refused("read-only Docker listing unavailable")
    names=containers[1].splitlines()
    expected="sse31340-r137-"+selected["nodeId"]
    conflicting=[n for n in names if n.startswith("sse31340-")]
    if conflicting:
        raise Refused("existing SSE Docker resources detected; do not retry")
    result={
        "schema":"SSE_R173_VM4709_READONLY_RECOVERY_GATE_V1",
        "savedSelectedRoles":["observer"],
        "pinnedSourceCommitVerified":True,
        "publicOriginalArchiveSha256Verified":True,
        "existingSseContainersDetected":False,
        "dockerAvailableForReadOnlyInspection":True,
        "originalChainOrSignerInspectedOrModified":False,
        "hostOrDockerStateMutated":False,
        "safeToRerunR147Installer":False,
        "existingReleaseMustBePreserved":True,
        "expectedNewResourcesPrefix":expected,
    }
    for service in ("docker","zerotier-one"):
        status=runner(["systemctl","is-active",service])
        result[service.replace("-","_")+"Active"]=(
            status is not None and status[0]==0 and status[1]=="active")
    zt=runner(["zerotier-cli","status"])
    result["zerotierCliAvailable"]=zt is not None and zt[0]==0
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        print(json.dumps(diagnose(),sort_keys=True,indent=2))
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R173_READONLY_RECOVERY_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
