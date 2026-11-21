#!/usr/bin/env python3
"""R153: unattended real local Besu/Lighthouse evidence after native install.

Uses actual R141 execution/beacon read-only APIs. A node is NOT 'joined'
until both clients independently pass chain31340, live sync, native peers
and original finality checks. Failure is recorded as PENDING, never fake
success. Optional local systemd timer stores nonsecret observations.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import sse_pos_r141_independent_fleet_audit as r141
import sse_public_genesis as original_chain

SCHEMA = "SSE_R153_UNATTENDED_CHAIN31340_OBSERVATION_V1"
SERVICE = "sse31340-local-evidence"
ROOT = Path("/var/lib/sse/evidence")
NODE = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")

class Refused(ValueError):
    pass

def observe(node, el="http://127.0.0.1:28545",
            bn="http://127.0.0.1:25052", collector=r141.capture):
    if type(node) is not str or not NODE.fullmatch(node):
        raise Refused("invalid actual local node identifier")
    try:
        report=collector(node,el,bn)
        r141.validate_report(report)
        # R141 validates report structure and on-chain chainId, not exact
        # original genesis identity or native peer counts. An unrelated
        # chain with chainId=31340 must never become "verified" here.
        if (report["executionGenesisHash"].lower()!=original_chain.EL_GENESIS
                or report["beaconGenesisValidatorsRoot"].lower()!=original_chain.CL_GENESIS):
            raise r141.Refused("local node follows a different genesis")
        if (report["executionNativePeers"]<1 or report["beaconNativePeers"]<1):
            raise r141.Refused("live native EL/CL peering not established")
        return {
            "schema":SCHEMA,"nodeId":node,
            "observedAtUtc":datetime.now(timezone.utc).isoformat(),
            "state":"ACTUAL_LOCAL_CHAIN_FINALITY_VERIFIED",
            "evidence":report,
            "externalOperatorIndependenceVerified":False,
            "permissionlessExternalP2pReachabilityVerified":False,
            "validatorKeyOrMarketLeaseVerified":False,
        }
    except (r141.Refused,OSError,ValueError,TypeError,KeyError) as exc:
        # A live syncing node is PENDING, not a failed/finalized network.
        return {
            "schema":SCHEMA,"nodeId":node,
            "observedAtUtc":datetime.now(timezone.utc).isoformat(),
            "state":"WAITING_FOR_ACTUAL_EL_CL_FINALITY",
            "reason":type(exc).__name__,
            "evidence":None,
            "externalOperatorIndependenceVerified":False,
            "permissionlessExternalP2pReachabilityVerified":False,
            "validatorKeyOrMarketLeaseVerified":False,
        }

def write_atomic(path, payload):
    target=Path(path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise Refused("refusing nonregular evidence target")
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode="w",dir=target.parent,prefix=".r153-",suffix=".json",
            encoding="utf-8",delete=False) as handle:
        staged=Path(handle.name)
        os.fchmod(handle.fileno(),0o600)
        json.dump(payload,handle,sort_keys=True,indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged,target)
    return payload

def unit_contents(release, node_id):
    if not GIT_SHA.fullmatch(release.name) or not NODE.fullmatch(node_id):
        raise Refused("service requires pinned release and node ID")
    if release.parent != Path("/opt/sse/releases"):
        raise Refused("release service cannot execute arbitrary source path")
    script=release/"tools"/"sse_pos_r153_local_node_evidence.py"
    service=(
        "[Unit]\nDescription=SSE chain31340 read-only local EL/CL evidence\n"
        "After=network-online.target docker.service\n\n"
        "[Service]\nType=oneshot\nUser=root\n"
        "NoNewPrivileges=true\nPrivateTmp=true\n"
        "ProtectSystem=strict\n"
        "ReadWritePaths=/var/lib/sse/evidence\n"
        f"ExecStart=/usr/bin/python3 -B {script} --node-id {node_id} "
        "--out /var/lib/sse/evidence/latest.json\n"
        f"ExecStartPost=-/usr/bin/python3 -B {release / 'tools/sse_pos_r156_local_native_peer_identity.py'} "
        f"--node-id {node_id} --out /var/lib/sse/evidence/public-peer.json\n"
    )
    timer=(
        "[Unit]\nDescription=Periodic chain31340 local client evidence\n\n"
        "[Timer]\nOnBootSec=3min\nOnUnitActiveSec=2min\n"
        "RandomizedDelaySec=30\nPersistent=true\n"
        f"Unit={SERVICE}.service\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    return service,timer

def install_timer(release,node_id,*,unit_root=Path("/etc/systemd/system"),
                  run=subprocess.run):
    if os.geteuid()!=0:
        raise Refused("host timer requires root authorization")
    service,timer=unit_contents(Path(release),node_id)
    src=Path(release)/"tools/sse_pos_r153_local_node_evidence.py"
    if src.is_symlink() or not src.is_file():
        raise Refused("pinned evidence tool missing")
    locations=[(unit_root/f"{SERVICE}.service",service),
               (unit_root/f"{SERVICE}.timer",timer)]
    if any(p.exists() or p.is_symlink() for p,_ in locations):
        raise Refused("evidence timer/unit already exists; never overwrite")
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    for p,source in locations:
        fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,"w") as out:
            out.write(source)
    for cmd in (["systemctl","daemon-reload"],
                ["systemctl","enable","--now",SERVICE+".timer"]):
        r=run(cmd,capture_output=True,timeout=30,check=False)
        if r.returncode!=0:
            raise Refused("local evidence timer activation failed; preserve state")
    return {"service":SERVICE+".service","timer":SERVICE+".timer",
            "actualFinalityObservedByInstaller":False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id",required=True)
    p.add_argument("--out",type=Path,default=ROOT/"latest.json")
    args=p.parse_args(argv)
    try:
        result=observe(args.node_id)
        write_atomic(args.out,result)
        print(json.dumps({"nodeId":result["nodeId"],"state":result["state"],
                          "originalChainIdentityVerified":result["evidence"] is not None},
                         sort_keys=True))
        return 0
    except (Refused,OSError,ValueError) as exc:
        print("R153_EVIDENCE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
