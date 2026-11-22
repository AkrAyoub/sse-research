#!/usr/bin/env python3
"""R163: one-time publication of the EXACT verified public chain31340 genesis.

This maintainer-only operation uses the operator's already authenticated
GitHub CLI credentials; never solicits, logs, stores or copies a token.
A failed/missing gh authorization produces a clear refusal. Its public
release asset is verified AGAIN via anonymous HTTPS and exact original
archive SHA256 + internal public-only member hashes. It does NOT touch
VM clients, generate a chain, manage validators or mutate existing tags.

A future new VM does NOT run this. It uses the verified public release
automatically through R149. Github release is source distribution, not
a permissionless node-admission authority or permanent peer seed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import sse_pos_r150_verified_genesis_release as original
import sse_public_genesis as public_release

REPO="AkrAyoub/sse-research"
TAG="chain31340-genesis-v1"
ASSET="chain31340-public-native-observer-v1.tar.gz"
PUBLIC_URL=f"https://github.com/{REPO}/releases/download/{TAG}/{ASSET}"
SHA40=re.compile(r"[0-9a-f]{40}\Z")
PROOF_SCHEMA="SSE_R150_VERIFIED_PUBLIC_GENESIS_ASSET_V1"

class Refused(ValueError):
    pass

def candidate(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise Refused("original verified release candidate missing or symlinked")
    data=original.safe_input(path)
    result=original.verify(data)
    proof=path.parent/"verified-public-genesis.json"
    if proof.is_symlink() or not proof.is_file() or proof.stat().st_size>8192:
        raise Refused("R150 public-only original release proof missing")
    try:
        marker=json.loads(proof.read_text("utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise Refused("malformed original-genesis release proof") from exc
    if (type(marker) is not dict or marker.get("schema")!=PROOF_SCHEMA
            or marker.get("sha256")!=original.ARCHIVE_SHA
            or marker.get("assetFilename")!=ASSET
            or marker.get("includesOnlyPublicGenesisMembers") is not True
            or marker.get("newGenesisGenerated") is not False
            or marker.get("validatorSecretInspectedOrCopied") is not False
            or marker.get("publiclyPublished") is not False):
        raise Refused("the public-only verified R150 provenance is not valid")
    return result

def run(command,*,timeout=180):
    try:
        result=subprocess.run(command,check=False,capture_output=True,text=True,
                              timeout=timeout,env={
                                  **os.environ,"GH_PROMPT_DISABLED":"1",
                                  "GIT_TERMINAL_PROMPT":"0"})
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("required trusted authenticated GitHub CLI unavailable") from exc
    if result.returncode:
        # Do not leak any GitHub authentication or private shell details.
        raise Refused("authorized GitHub release command failed; check gh auth status privately")
    return result.stdout.strip()

def upload(path,commit,*,runner=run,downloader=public_release.download):
    if type(commit) is not str or not SHA40.fullmatch(commit):
        raise Refused("pin exactly the reviewed 40-character Git source SHA")
    proof=candidate(path)
    if not shutil.which("gh"):
        raise Refused("GitHub CLI not installed: cannot publish release asset")
    runner(["gh","auth","status"],timeout=30)
    # A release/tag already existing must not be clobbered. A previous
    # partial execution must be inspected rather than silently overwritten.
    try:
        existed=subprocess.run(
            ["gh","release","view",TAG,"--repo",REPO,"--json","tagName"],
            capture_output=True,text=True,timeout=30,
            env={**os.environ,"GH_PROMPT_DISABLED":"1"})
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("unable to inspect existing immutable release state") from exc
    if existed.returncode==0:
        raise Refused("release already exists; never overwrite or mutate public genesis")
    if existed.returncode not in (1,):
        raise Refused("ambiguous release existence; refuse upload")
    # Repo write authorization is required ONLY ONCE by network maintainer;
    # future permissionless VM joiners download anonymously.
    # GitHub creates a draft while uploading and publishes after asset
    # completion. Do not use --clobber or mutate a pre-existing tag.
    runner([
        "gh","release","create",TAG,str(Path(path).resolve()),
        "--repo",REPO,"--target",commit,
        "--title","Immutable chain31340 original public genesis v1",
        "--notes",("Original existing chain31340, not a new genesis. "
                   "Exactly the verified R59 public-only release archive. "
                   "SHA256: "+original.ARCHIVE_SHA+". "
                   "No validator keys or mnemonic files."),
    ],timeout=300)
    remote=downloader(PUBLIC_URL)
    original.verify(remote)
    if remote!=Path(path).read_bytes():
        raise Refused("published bytes differ from the original candidate")
    return {
        "schema":"SSE_R163_ORIGINAL_PUBLIC_GENESIS_PUBLISHED_V1",
        "publicDownloadUrl":PUBLIC_URL,
        "originalArchiveSha256":original.ARCHIVE_SHA,
        "publishedPublicBytesIndependentlyVerified":True,
        "publicArchiveMembersVerified":proof["memberDigestsVerified"],
        "newChainGenesisGenerated":False,
        "validatorSecretsUploaded":False,
        "onChainServicesOrValidatorsChanged":False,
        "releaseTargetGitSha":commit,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset",type=Path,required=True)
    p.add_argument("--commit",required=True)
    p.add_argument("--publish",action="store_true",
                   help="perform one-time authorized PUBLIC GitHub release")
    args=p.parse_args(argv)
    try:
        summary=candidate(args.asset)
        if type(args.commit) is not str or not SHA40.fullmatch(args.commit):
            raise Refused("requires full pinned Git source SHA")
        if args.publish:
            result=upload(args.asset,args.commit)
        else:
            result={
                "schema":"SSE_R163_PUBLISH_PLAN_ONLY_V1",
                "archiveSha256":summary["sha256"],
                "publicAssetUrlOnlyAfterSuccessfulPublication":PUBLIC_URL,
                "publishingRequested":False,
                "authOrNetworkMutated":False,
                "originalGenesisRecreated":False,
            }
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,original.Refused,public_release.Refused,
            OSError,TypeError,ValueError) as exc:
        print("R163_ORIGINAL_PUBLIC_GENESIS_RELEASE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
