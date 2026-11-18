#!/usr/bin/env python3
"""R11: actual four-PUBLIC-key QBFT genesis canary, then authoritative block0.

Unlike the earlier synthetic canary, uses the actual four host-generated
PUBLIC validator records. No private node keys are read, imported, cloned,
or generated. Runs a P2P-DISABLED, disposable Besu instance on the first
approved Ubuntu node, pinned to the exact previously observed image digest.
This is still not four-host consensus. Starts Docker ONLY with --apply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from sse_qbft_network_assembly import load_public,validate_roster,AssemblyError
from sse_qbft_lab_config import qbft_extra_data
from sse_qbft_vm_preflight import parse_image,parse_genesis,PreflightError
from sse_r9_canary_lab import invoke,probe,_busy,stage,COMPOSE,CanaryError

SHA=re.compile(r"[0-9a-f]{40}\Z")
RUN=re.compile(r"[a-z][a-z0-9-]{3,23}\Z")
ROOT=Path(__file__).resolve().parents[1]


class RealGenesisError(ValueError):
    pass


def validate_input(public:list[dict],genesis_path:Path,genesis_sha256:str,
                   image:str,revision:str,run_id:str)->dict:
    if (type(revision) is not str or not SHA.fullmatch(revision)
            or type(run_id) is not str or not RUN.fullmatch(run_id)):
        raise RealGenesisError("exact revision and safe unique run ID required")
    image=parse_image(image)
    public=validate_roster(public)
    parsed=parse_genesis(genesis_path,genesis_sha256)
    genesis=json.loads(genesis_path.read_text("utf-8"))
    addrs=[entry["validatorAddress"] for entry in public]
    if genesis.get("extraData")!=qbft_extra_data(addrs):
        raise RealGenesisError("approved real four-validator genesis keys do not match public records")
    return {
        "kind":"SSE_QBFT_REAL_GENESIS_CANARY_PLAN_V1",
        "sourceGitSha":revision,
        "image":image,
        "nodeIds":[rec["nodeId"] for rec in public],
        "validatorAddresses":addrs,
        "genesisFileSha256":parsed["genesisSha256"],
        "chainId":31338,
        "rpcHost":"127.0.0.1","rpcPort":18559,
        "p2pDisabled":True,"hasRealPublicValidators":True,
        "validatorPrivateKeysAccessed":False,
        "startedValidator":False,"consensusQuorumObserved":False,
        "permissionlessMembershipClaimed":False,
        "ethereumTransactionsSent":False,
    }


def write_once(path:Path,value:str):
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(value)
        f.flush()
        os.fsync(f.fileno())


def apply(*,public:list[dict],genesis_path:Path,genesis_sha256:str,image:str,
          revision:str,run_id:str,output_dir:Path,cmd=invoke,
          read_rpc=None)->dict:
    plan=validate_input(public,genesis_path,genesis_sha256,image,revision,run_id)
    if (sys.platform!="linux" or os.geteuid()==0
            or not output_dir.is_absolute() or not output_dir.is_dir()
            or output_dir.is_symlink() or output_dir.stat().st_uid!=os.geteuid()
            or output_dir.stat().st_mode&0o077):
        raise RealGenesisError("apply requires unprivileged Linux and private owner-controlled output dir")
    if any((output_dir/f).exists() for f in (".env","docker.log","result.json")):
        raise RealGenesisError("will not overwrite existing real-genesis evidence")
    if _busy(8545) or _busy(18545) or _busy(18559):
        raise RealGenesisError("local Anvil/Besu RPC listener already running")
    if (cmd(["git","rev-parse","HEAD"])!=revision
            or cmd(["git","status","--porcelain","--untracked-files=no"])):
        raise RealGenesisError("unapproved or modified GitHub source checkout")
    try:
        cmd(["sudo","-n","docker","info","--format","{{.ServerVersion}}"],timeout=15)
    except CanaryError:
        raise RealGenesisError("Docker authorization missing: run sudo -v before a new attempt") from None
    # Never silently pull a new image. The R10 canary already recorded
    # a real repo digest; operator must explicitly pass that immutable ref.
    digests=cmd(["sudo","-n","docker","image","inspect","--format",
                 "{{json .RepoDigests}}",image])
    digest=image.split("@",1)[1]
    try:
        repos=json.loads(digests)
    except ValueError:
        raise RealGenesisError("Docker image inventory unavailable") from None
    if (type(repos) is not list or
            not any(isinstance(s,str) and s.endswith("@"+digest)
                    and s.startswith("hyperledger/besu@") for s in repos)):
        raise RealGenesisError("immutable Besu digest not found in local Docker cache")
    env="\n".join((
        "BESU_IMAGE="+image,
        "BESU_UID="+str(os.geteuid()),
        "BESU_GID="+str(os.getegid()),
        "BESU_GENESIS="+str(genesis_path),
        "",
    ))
    write_once(output_dir/".env",env)
    project="sse-realgen-"+run_id
    command=["sudo","-n","docker","compose","-p",project,
             "-f",str(COMPOSE),"--env-file",str(output_dir/".env")]
    started=False
    logs=""
    observed=None
    try:
        stage("REAL_GENESIS_COMPOSE_CONFIG")
        cmd(command+["config","--quiet"])
        started=True
        stage("REAL_GENESIS_P2P_DISABLED_BESU")
        cmd(command+["up","-d","--pull","never"],timeout=120)
        stage("REAL_GENESIS_OBSERVE_BLOCK0")
        observed=probe(read_rpc=read_rpc) if read_rpc else probe()
    finally:
        if started:
            try:
                logs=cmd(command+["logs","--no-color","--tail","160"],
                         timeout=25,success=False)
            except CanaryError:
                logs="(Docker logs unavailable)"
            write_once(output_dir/"docker.log",logs[:120000]+"\n")
            stage("REAL_GENESIS_STOP_DISPOSABLE_CANARY")
            try:
                cmd(command+["down","--remove-orphans"],timeout=60)
            except CanaryError:
                raise RealGenesisError("disposable canary may be running, inspect Docker state") from None
    if observed is None:
        raise RealGenesisError("no real Besu genesis RPC was observed")
    report={
        **plan,**observed,
        "kind":"SSE_QBFT_REAL_GENESIS_BLOCK0_OBSERVED_V1",
        "observedRealGenesisBlockHash":observed["observedBlock0Hash"],
        "observedBesuClientVersion":observed["observedBesuClientVersion"],
        "immutableImageDigest":digest,
        "dockerLogSha256":hashlib.sha256((logs[:120000]+"\n").encode()).hexdigest(),
        "canaryStoppedAfterProbe":True,
        "genesisHashStillNeedsPeerCatalogSignature":True,
        "actualConsensusReached":False,
    }
    write_once(output_dir/"result.json",json.dumps(report,sort_keys=True,indent=2)+"\n")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description="Real public-validator genesis block0 probe before signing peer catalog")
    p.add_argument("--public",action="append",required=True,type=Path)
    p.add_argument("--genesis",required=True,type=Path)
    p.add_argument("--genesis-sha256",required=True)
    p.add_argument("--image",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        roster=[load_public(path) for path in a.public]
        if a.apply:
            result=apply(public=roster,genesis_path=a.genesis,
                         genesis_sha256=a.genesis_sha256,image=a.image,
                         revision=a.source_commit,run_id=a.run_id,
                         output_dir=a.output_dir)
        else:
            result=validate_input(roster,a.genesis,a.genesis_sha256,
                                  a.image,a.source_commit,a.run_id)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (RealGenesisError,AssemblyError,PreflightError,
            CanaryError,OSError,ValueError,TypeError,KeyError) as exc:
        print("SSE_QBFT_REAL_GENESIS_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
