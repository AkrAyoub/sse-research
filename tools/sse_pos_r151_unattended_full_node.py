#!/usr/bin/env python3
"""R151: unattended REAL nonsigning EL+CL launch using already-proven R59/R137.

This is the guarded runtime phase after one public-install role selection.
It reuses R137's actual Docker creation, pinned original R59 genesis and
Besu/Lighthouse images. No validator signer, fresh genesis or admin peer list.
Runtime prerequisites must already be installed and LIVE; no fake outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import sse_pos_r59_native_ipv6_observer as r59
import sse_pos_r136_independent_observer_preflight as r136
import sse_pos_r137_independent_observer_create_once as r137
import sse_pos_r142_public_peer_discovery as r142
import sse_public_genesis as public_genesis
import sse_pos_r152_unattended_host_dependencies as host_packages
import sse_pos_r153_local_node_evidence as local_evidence

class Refused(ValueError):
    pass

STATE = Path("/var/lib/sse/selection.json")
RELEASES = Path("/opt/sse/releases")
FULL = {"full_node","observer","validator"}

def safe_selection(obj, *, commit=None):
    if type(obj) is not dict or obj.get("schema") != "SSE_R147_PUBLIC_INSTALL_V1":
        raise Refused("missing locally created R147 role selection")
    roles=obj.get("selectedRoles")
    if (type(roles) is not list or not roles or
            any(type(r) is not str for r in roles) or
            not set(roles).intersection(FULL) or
            len(set(roles)) != len(roles)):
        raise Refused("no locally selected full-node or observer role")
    if (obj.get("network")!="chain31340" or
            obj.get("chainGenesisRecreated") is not False or
            obj.get("publicSourceDownloaded") is not True or
            obj.get("roleSelectionRecorded") is not True):
        raise Refused("selection not backed by actual verified public source phase")
    sha=obj.get("sourceCommit")
    if (type(sha) is not str or len(sha)!=40 or
            any(ch not in "0123456789abcdef" for ch in sha)
            or (commit is not None and sha!=commit)):
        raise Refused("invalid pinned local source revision")
    r136.validate_manifest({
        "schema":r136.SCHEMA,"chainId":31340,
        "nodeId":obj.get("nodeId"),"role":"observer",
        "networkId":r136.NETWORK_ID,"archiveSha256":r136.ARCHIVE_SHA})
    return obj

def load_selection(path=STATE):
    path=Path(path)
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= 8192
            or path.stat().st_mode & 0o077):
        raise Refused("private local selection file unavailable")
    try:
        obj=json.loads(path.read_text("utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise Refused("invalid local selected-role JSON") from exc
    return safe_selection(obj)

def ensure_fresh_host():
    if os.geteuid()!=0:
        raise Refused("root execution required by the existing privileged Docker setup")
    for home in Path("/home").glob("*"):
        for name in ("sse-r35-chain31340-g2-private",
                     "sse-r27-bls-operator-private",
                     "sse-r59-chain31340-observer"):
            p=home/".local/share"/name
            if p.exists() or p.is_symlink():
                raise Refused("original owner or established observer protected")
    r59.guard_owner()
    # Root privilege is only for local Docker/signed package operations;
    # do NOT use Docker HTTP socket, expose Engine or import validator keys.

def verify_release(selection):
    root=RELEASES/selection["sourceCommit"]
    if root.is_symlink() or not root.is_dir():
        raise Refused("pinned public checkout not present")
    identity=public_genesis.read_manifest(root/"release/chain31340-public-release.json")
    archive=root/"original-chain31340.tar.gz"
    if archive.is_symlink() or not archive.is_file():
        raise Refused("original verified public genesis archive not staged")
    from sse_pos_r150_verified_genesis_release import verify
    verify(archive.read_bytes())
    return root,identity,archive

def prepare_original_archive(source):
    # R137 still expects R59's original archive path: create it only once
    # on the independently installed NEW host. No source archive overwrite.
    target=r59.ARCHIVE
    if target.is_symlink():
        raise Refused("original archive target is symlinked")
    if target.exists():
        r136.verify_archive(target)
        if target.read_bytes()!=source.read_bytes():
            raise Refused("preexisting original archive differs")
        return target
    data=source.read_bytes()
    if hashlib.sha256(data).hexdigest()!=r59.ARCHIVE_SHA:
        raise Refused("not the real original chain31340 archive")
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    return target

def peer_hints(release, *, lookup=r142.discover):
    urls=release["replaceablePeerDirectorySources"]
    if not urls:
        # This is an isolated first-online peer (or a disconnected peer).
        # No admin permission or invented enodes; no syncing claims.
        return None,None,"ZERO_PUBLISHED_BOOTSTRAPS_WAIT_FOR_DISCOVERY"
    found=lookup(urls)
    els=found["executionBootnodes"]
    bns=found["beaconBootnodes"]
    if len(els)<2 or len(bns)<2:
        raise Refused("insufficient live independent bootnode hints")
    return ",".join(els),",".join(bns),"PUBLIC_MULTISOURCE_NATIVE_HINTS"

def plan(selection, release, archive, *, observe=None,
         lookup=r142.discover):
    safe_selection(selection)
    if not archive.is_file():
        raise Refused("original verified chain31340 archive missing")
    el,bn,mode=peer_hints(release,lookup=lookup)
    # Do not call preflight during a pure source-only unit test; it must
    # inspect LIVE Docker/ZeroTier/image state before claiming readiness.
    observed=None
    if observe is not None:
        with tempfile.TemporaryDirectory(prefix="sse-r151-") as tmp:
            path=Path(tmp)/"observer.json"
            data={
                "schema":r136.SCHEMA,"chainId":31340,
                "nodeId":selection["nodeId"],"role":"observer",
                "networkId":r136.NETWORK_ID,
                "archiveSha256":r136.ARCHIVE_SHA}
            path.write_text(json.dumps(data))
            observed=observe(path,archive,el,bn,allow_no_peers=(el is None))
    return {
        "schema":"SSE_R151_REAL_NON_SIGNING_RUNTIME_PREFLIGHT_V1",
        "nodeId":selection["nodeId"],"discoveryMode":mode,
        "originalArchiveVerified":True,
        "nativePeerHandshakeVerified":False,
        "finalizedCheckpointVerified":False,
        "newValidatorSignerStarted":False,
        "actualPreflight":observed,
        "peerExecutionHints":el,"peerConsensusHints":bn,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",action="store_true")
    p.add_argument("--execute",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.plan==args.execute:
            raise Refused("choose one of --plan or --execute")
        ensure_fresh_host()
        selection=load_selection()
        release,descriptor,archive=verify_release(selection)
        # Archive is verified before being staged in the previously tested
        # R59 path (only for execute, never for plan).
        if args.execute:
            # Actual fresh-host dependencies, not the user's manual task:
            # signed Ubuntu Docker, verified ZeroTier package installer,
            # controllerless public overlay and immutable OCI image digests.
            host_packages.setup(execute=True)
            archive=prepare_original_archive(archive)
        ready=plan(selection,descriptor,archive,
                   observe=r137.preflight if args.execute else None)
        if not args.execute:
            ready.pop("peerExecutionHints")
            ready.pop("peerConsensusHints")
            print(json.dumps(ready,sort_keys=True,indent=2,default=str))
            return 0
        with tempfile.TemporaryDirectory(prefix="sse-r151-") as tmp:
            manifest=Path(tmp)/"observer.json"
            manifest.write_text(json.dumps({
                "schema":r136.SCHEMA,"chainId":31340,
                "nodeId":selection["nodeId"],"role":"observer",
                "networkId":r136.NETWORK_ID,
                "archiveSha256":r136.ARCHIVE_SHA}))
            checked=r137.preflight(manifest,archive,
                ready["peerExecutionHints"],ready["peerConsensusHints"],
                allow_no_peers=ready["peerExecutionHints"] is None)
            result=r137.apply(checked,ready["peerExecutionHints"],
                              ready["peerConsensusHints"],unattended=True)
        ready.pop("peerExecutionHints")
        ready.pop("peerConsensusHints")
        ready.update(result)
        ready["liveNativeP2pHandshakeVerified"]=False
        ready["actualFinalityVerified"]=False
        ready["status"]="REAL_CLIENT_CONTAINERS_SUBMITTED_AWAITING_R141_EVIDENCE"
        # Background local evidence is READ-ONLY. Failure to install its
        # timer does not roll back a successfully created live EL/CL node.
        try:
            timer=local_evidence.install_timer(
                RELEASES/selection["sourceCommit"],selection["nodeId"])
            ready["automaticEvidenceTimerInstalled"]=True
            ready["evidenceTimer"]=timer["timer"]
        except (local_evidence.Refused,OSError):
            ready["automaticEvidenceTimerInstalled"]=False
            ready["evidenceTimer"]="LOCAL_TIMER_NEEDS_REVIEW"
        print(json.dumps(ready,sort_keys=True,indent=2,default=str))
        return 0
    except (Refused,r59.R59Refused,r136.Refused,r137.Refused,
            r142.Refused,public_genesis.Refused,host_packages.Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R151_UNATTENDED_NODE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
