#!/usr/bin/env python3
"""R178 read-only existing VM4709 Besu/Lighthouse startup diagnosis.

No Docker mutations, host package operations, chain writes, network fetches,
wallet inspection, or changes to a pinned original release.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys

NODE="node-8be265272c35f3d8c3a0"
PREFIX="sse31340-r137-"+NODE
EXPECTED={"el":PREFIX+"-el","bn":PREFIX+"-bn"}
FIELDS=("Name","Image","State","Config","HostConfig","Mounts")

class Refused(ValueError):
    pass

def command(args, *, runner=subprocess.run):
    try:
        result=runner(args,capture_output=True,text=True,timeout=15,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("read-only Docker inspection command unavailable") from exc
    if result.returncode:
        raise Refused("read-only Docker inspection failed")
    return result.stdout

def check(*, fetch=command):
    reports={}
    for role,name in EXPECTED.items():
        obj=json.loads(fetch(["docker","inspect",name]))
        if not isinstance(obj,list) or len(obj)!=1 or type(obj[0]) is not dict:
            raise Refused("ambiguous Docker inspect result")
        d=obj[0]
        if d.get("Name")!="/"+name:
            raise Refused("unexpected Docker container identity")
        cfg=d.get("Config") or {}
        host=d.get("HostConfig") or {}
        state=d.get("State") or {}
        mounts=d.get("Mounts") or []
        # NEVER output environment variables, JWT mounts' host SOURCE,
        # private keys or Docker IPs.
        report={
            "container":name,
            "running":bool(state.get("Running")),
            "restarting":bool(state.get("Restarting")),
            "exitCode":state.get("ExitCode"),
            "restartCount":d.get("RestartCount"),
            "imageId":d.get("Image"),
            "entrypoint":cfg.get("Entrypoint"),
            "user":cfg.get("User"),
            "readOnlyRootFs":host.get("ReadonlyRootfs"),
            "capDrop":host.get("CapDrop"),
            "securityOpt":host.get("SecurityOpt"),
            "mountTargetReadonly":sorted(
                [{"target":m.get("Destination"),"readonly":not m.get("RW",True)}
                  for m in mounts if type(m) is dict],
                key=lambda m:str(m["target"])),
        }
        if role=="bn":
            cmd=cfg.get("Cmd") or []
            # Show only safety-relevant opt-in flags; no dynamic peer addresses.
            report["usesIgnoreWeakSubjectivityCheck"] = "--ignore-ws-check" in cmd
            report["usesCheckpointSync"]=any(str(x).startswith("--checkpoint-sync-url")
                                             for x in cmd)
            report["usesKnownGenesisOnly"]="--allow-insecure-genesis-sync" in cmd
        reports[role]=report
    return {"schema":"SSE_R178_REAL_CLIENT_STARTUP_READONLY_DIAG_V1",
            "chainId":31340,
            "nodeId":NODE,
            "mutatedDockerOrHost":False,
            "walletOrJwtRead":False,
            "state":reports}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.parse_args(argv)
    try:
        print(json.dumps(check(),sort_keys=True,indent=2))
        return 0
    except (Refused,ValueError,TypeError,KeyError) as exc:
        print("R178_READONLY_DIAG_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
