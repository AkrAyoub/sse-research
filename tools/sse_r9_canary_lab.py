#!/usr/bin/env python3
"""One-command VM4704 *isolated* QBFT genesis canary, not a validator.

Operator approval flag --apply explicitly permits an exploratory Besu Docker
image pull and a P2P-disabled, throwaway Compose container. No wallet, no
SSH/Tailscale reauth, no real validator private key, no chain31337 change,
no public RPC, no block production and no GitHub Actions. It records actual
observed block0 hash, client version and immutable image digest; nonzero
progress requires genuine Docker RPC evidence, not a guessed genesis hash.

A reviewed production release should pin the observed image digest in
GitHub before anyone runs a final four-host fleet. No authority is granted
by successfully starting this canary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.request import Request,urlopen

from sse_qbft_lab_config import genesis
from sse_qbft_vm_preflight import parse_image,PreflightError

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=ROOT/"infra"/"qbft-multivm"/"genesis-canary.compose.yaml"
SHA=re.compile(r"[0-9a-f]{40}\Z")
TAG=re.compile(r"hyperledger/besu:([0-9]+)\.([0-9]+)\.([0-9]+)\Z")
RUN_ID=re.compile(r"[a-z][a-z0-9-]{3,25}\Z")
DOCKER_DIGEST=re.compile(r"hyperledger/besu@sha256:([0-9a-f]{64})\Z")
SYNTHETIC_ADDRS=["0x"+f"{i:02x}"*20 for i in range(1,5)]


class CanaryError(ValueError):
    pass


def check(version:str,revision:str,run_id:str)->dict:
    if (type(version) is not str or not TAG.fullmatch(version)
            or type(revision) is not str or not SHA.fullmatch(revision)
            or type(run_id) is not str or not RUN_ID.fullmatch(run_id)):
        raise CanaryError("requires numeric Besu version, exact Git SHA and safe run ID")
    m=TAG.fullmatch(version)
    if tuple(int(x) for x in m.groups())<(26,11,1):
        raise CanaryError("QBFT withdrawal mint vulnerability: require Besu >=26.11.1 for current research baseline")
    if not COMPOSE.is_file():
        raise CanaryError("reviewed canary Compose template not found")
    return {
        "kind":"SSE_R9_BESU_CANARY_PLAN_V1",
        "mode":"DRY_RUN",
        "sourceCommit":revision,
        "imageTag":version,
        "experimentalImageDigestNotYetVerified":True,
        "chainId":31338,
        "p2pEnabled":False,
        "discoveryEnabled":False,
        "rpcHost":"127.0.0.1",
        "rpcPort":18559,
        "syntheticGenesisValidators":4,
        "doesNotUseRealValidatorKeys":True,
        "besuContainersStarted":False,
        "historicalAnvilTouched":False,
    }


def invoke(argv,*,env=None,timeout=40,success=True):
    try:
        result=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,
                              text=True,timeout=timeout,check=False)
    except (OSError,subprocess.SubprocessError):
        raise CanaryError("local tool unavailable or timed out: "+argv[0]) from None
    if success and result.returncode!=0:
        raise CanaryError(
            "subprocess refused: "+argv[0]+" "+argv[1] if len(argv)>1
            else "subprocess refused: "+argv[0])
    return result.stdout.strip()


def _rpc(method,params):
    payload=json.dumps({"jsonrpc":"2.0","id":1,"method":method,
                        "params":params},separators=(",",":")).encode()
    req=Request("http://127.0.0.1:18559",data=payload,method="POST",
                headers={"Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=3) as res:
            if res.status!=200:
                raise CanaryError("canary RPC non-200")
            raw=res.read(65537)
    except (OSError,TimeoutError):
        raise CanaryError("canary RPC not ready") from None
    if len(raw)>65536:
        raise CanaryError("oversized canary RPC response")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeError):
        raise CanaryError("malformed canary JSONRPC") from None
    if (type(data) is not dict or data.get("id")!=1
            or data.get("jsonrpc")!="2.0" or "error" in data
            or data.get("result") is None):
        raise CanaryError("canary JSONRPC returned error or null")
    return data["result"]


def probe(*,read_rpc=_rpc,retries=20,sleep=time.sleep)->dict:
    last_error=""
    for attempt in range(retries):
        try:
            chain=read_rpc("eth_chainId",[])
            if chain!=hex(31338):
                raise CanaryError("canary unexpectedly using wrong chain ID")
            zero=read_rpc("eth_getBlockByNumber",["0x0",False])
            if type(zero) is not dict:
                raise CanaryError("missing block0")
            blockhash=zero.get("hash")
            if (type(blockhash) is not str or not re.fullmatch(
                    r"0x[0-9a-fA-F]{64}\Z",blockhash)
                    or int(blockhash,16)==0 or zero.get("number")!="0x0"):
                raise CanaryError("invalid observed genesis block")
            version=read_rpc("web3_clientVersion",[])
            if type(version) is not str or "besu" not in version.lower() or len(version)>300:
                raise CanaryError("canary client does not identify as Besu")
            return {
                "kind":"SSE_R9_OBSERVED_GENESIS_CANARY_V1",
                "chainId":31338,
                "observedBlock0Hash":blockhash.lower(),
                "observedBesuClientVersion":version,
                "genesisHashIsNotFileSha256":True,
                "p2pEnabled":False,
                "startedValidator":False,
                "readOnlyRpcOnly":True,
                "transactionsSent":False,
            }
        except CanaryError as exc:
            last_error=str(exc)
            if "wrong chain" in last_error or "does not identify" in last_error:
                raise
            if attempt+1<retries:
                sleep(1)
    raise CanaryError("canary never produced a valid genesis RPC: "+last_error)


def _busy(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.settimeout(.3)
        return sock.connect_ex(("127.0.0.1",port))==0


def _new_file(path:Path,text:str):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(text)


def execute(directory:Path,*,version:str,revision:str,run_id:str,
            command=invoke,read_rpc=_rpc,sleep=time.sleep)->dict:
    check(version,revision,run_id)
    try:
        os_release=Path("/etc/os-release").read_text("utf-8")
    except OSError:
        raise CanaryError("Ubuntu operating system manifest unavailable") from None
    if (os.name!="posix" or platform.system()!="Linux"
            or "microsoft" in platform.release().lower()
            or not any(x in ('ID=ubuntu','ID="ubuntu"') for x in os_release.splitlines())
            or os.geteuid()==0 or not directory.is_absolute()
            or directory.is_symlink() or not directory.is_dir()
            or directory.stat().st_uid!=os.geteuid()
            or directory.stat().st_mode&0o077):
        raise CanaryError("requires native nonroot Ubuntu and user-owned 0700 output dir")
    if _busy(8545) or _busy(18545) or _busy(18559):
        raise CanaryError("Anvil, validator or canary RPC detected; refuse collision")
    if (command(["git","rev-parse","HEAD"])!=revision
            or command(["git","status","--porcelain","--untracked-files=no"])):
        raise CanaryError("approved exact GitHub checkout not clean")
    needed=("genesis.json",".canary.env","result.json","docker.log")
    if any((directory/name).exists() or (directory/name).is_symlink()
           for name in needed):
        raise CanaryError("refusing to overwrite any existing canary evidence")
    g=genesis(SYNTHETIC_ADDRS,chain_id=31338,
              block_period=5,gas_limit=15000000,reward_wei=0)
    gbytes=json.dumps(g,sort_keys=True,indent=2)+"\n"
    _new_file(directory/"genesis.json",gbytes)
    source_sha=hashlib.sha256(gbytes.encode()).hexdigest()
    # Exploratory pilot may pull a version tag. Pin the returned immutable
    # registry digest for the *actual run*, and never silently use that tag
    # for a later production validator.
    command(["sudo","docker","pull",version],timeout=240)
    digests=command(["sudo","docker","image","inspect","--format",
                     "{{json .RepoDigests}}",version])
    try:
        listed=json.loads(digests)
    except (ValueError,UnicodeError):
        raise CanaryError("Docker did not provide verifiable RepoDigests") from None
    valid=[]
    if type(listed) is list:
        for candidate in listed:
            if type(candidate) is str and DOCKER_DIGEST.fullmatch(candidate):
                valid.append(DOCKER_DIGEST.fullmatch(candidate).group(1))
    if len(set(valid))!=1:
        raise CanaryError("ambiguous or missing immutable Besu image digest")
    pinned=version+"@sha256:"+valid[0]
    parse_image(pinned)
    env_content="\n".join((
        "BESU_IMAGE="+pinned,
        "BESU_UID="+str(os.geteuid()),
        "BESU_GID="+str(os.getegid()),
        "BESU_GENESIS="+str(directory/"genesis.json"),
        "",
    ))
    _new_file(directory/".canary.env",env_content)
    # Unique project per run ensures cleanup cannot affect validator Compose.
    project="sse-canary-"+run_id
    base=["sudo","docker","compose","-p",project,"-f",str(COMPOSE),
          "--env-file",str(directory/".canary.env")]
    started=False
    logs=""
    try:
        command(base+["config","--quiet"])
        started=True  # up may partially create resources, cleanup on error.
        command(base+["up","-d"],timeout=120)
        observed=probe(read_rpc=read_rpc,sleep=sleep)
    finally:
        if started:
            try:
                logs=command(base+["logs","--no-color","--tail","120"],
                             timeout=20,success=False)
            except CanaryError:
                logs="(container logs unavailable)"
            _new_file(directory/"docker.log",logs[:100000]+"\n")
            try:
                command(base+["down","--remove-orphans"],timeout=60)
            except CanaryError:
                # Stop failures must never be presented as safe cleanup.
                raise CanaryError("canary may still be running; operator cleanup required")
    evidence={
        **observed,
        "sourceCommit":revision,"imageTag":version,
        "immutableImage":pinned,
        "genesisFileSha256":source_sha,
        "actualValidatorKeyUsed":False,
        "genesisSyntheticNotFinalFleet":True,
        "experimentalImageTagPulledBeforeDigestPin":True,
        "reuseWithoutApprovalForbidden":True,
        "canaryStoppedAfterProbe":True,
        "dockerLogsSha256":hashlib.sha256((logs[:100000]+"\n").encode()).hexdigest(),
        "evidenceNotProofOfFourHostConsensus":True,
    }
    _new_file(directory/"result.json",
              json.dumps(evidence,sort_keys=True,indent=2)+"\n")
    return evidence


def main(argv=None):
    p=argparse.ArgumentParser(description="P2P-disabled disposable Besu QBFT genesis canary")
    p.add_argument("--source-commit",required=True)
    p.add_argument("--image-tag",default="hyperledger/besu:26.11.1")
    p.add_argument("--run-id",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    try:
        prepared=check(a.image_tag,a.source_commit,a.run_id)
        if a.apply:
            result=execute(a.output_dir,version=a.image_tag,
                           revision=a.source_commit,run_id=a.run_id)
        else:
            result=prepared
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (CanaryError,PreflightError,OSError,TypeError,ValueError) as exc:
        print("SSE_R9_CANARY_REFUSED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
