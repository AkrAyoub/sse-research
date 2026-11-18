#!/usr/bin/env python3
"""Safely bring an already-generated SSE PoS genesis YAML to reviewed launch spec.

This is a one-time, explicit patch of a LOCAL GENERATED SECRET, not a source
edit or a validator authorization. Never print, upload, overwrite or regenerate
the bootstrap BIP39 mnemonic. The original generator's immutable manifest
continues to identify its pre-patch SHA; a separate launch-ready manifest
records BOTH hashes and enables recovery from interruption.

Pinned upstream ethereum-package d3014d6 checks Fulu=0 requires supernode
or 128+ validators on one participant, or a full PeerDAS 16-node setup.
For our 2x32 SMOKE, defer Fulu (18446744073709551615). This DOES NOT claim
a secure public P2P network or later fork compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASELINE_SHA=re.compile(r"[0-9a-f]{40}\Z")
TARGET_LINE=b"  fulu_fork_epoch: 18446744073709551615\n"
ANCHOR=b"  genesis_gaslimit: 30000000\n"
MAX_SIZE=65536
MAX_FAR_FUTURE=18446744073709551615


class LaunchPrepError(ValueError):
    pass


def digest(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def checked_files(folder:Path):
    if (not folder.is_absolute() or not folder.is_dir() or folder.is_symlink()
            or os.name!="posix" or os.geteuid()==0
            or folder.stat().st_uid!=os.geteuid()
            or stat.S_IMODE(folder.stat().st_mode)!=0o700):
        raise LaunchPrepError("requires unprivileged POSIX owner and 0700 secret folder")
    p=folder/"network_params.yaml"
    m=folder/"manifest.json"
    for path in (p,m):
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_uid!=os.geteuid()
                or stat.S_IMODE(path.stat().st_mode)!=0o600
                or not 1<=path.stat().st_size<=MAX_SIZE):
            raise LaunchPrepError("existing secret config and original manifest must be owner-only 0600")
    return p,m


def validated_patch(raw:bytes,manifest:dict)->tuple[bytes,str,str]:
    if type(manifest) is not dict or any(
        manifest.get(k)!=v for k,v in (
            ("schema","SSE_OWN_ETHEREUM_POS_DEVNET_PLAN_V1"),
            ("chainId",31339),("networkConfigCreated",True),
            ("initialBootstrapValidators",64),
            ("publicP2PRequested",False),
        )
    ):
        raise LaunchPrepError("original record not the expected private 2x32 PoS smoke")
    oldhash=manifest.get("secretConfigSha256")
    if type(oldhash) is not str or not re.fullmatch(r"[0-9a-f]{64}\Z",oldhash):
        raise LaunchPrepError("missing original generated config digest")
    if (raw.count(b'  network_id: "31339"\n')!=1
            or raw.count(b'    validator_count: 32\n')!=1
            or raw.count(b'    count: 2\n')!=1
            or raw.count(b'  preregistered_validator_count: 0\n')!=1
            or raw.count(b'  prefunded_accounts: ')!=1
            or raw.count(b'  preregistered_validator_keys_mnemonic: "')!=1
            or raw.count(ANCHOR)!=1
            or b'    enabled: true\n' in raw
            or b"\x00" in raw):
        raise LaunchPrepError("config differs from expected restricted two-node genesis template")
    if raw.count(b"  fulu_fork_epoch:")>1:
        raise LaunchPrepError("ambiguous Fulu fork settings")
    if b"  fulu_fork_epoch:" in raw:
        if raw.count(TARGET_LINE)!=1:
            raise LaunchPrepError("unexpected Fulu settings; manual review required")
        original=raw.replace(TARGET_LINE,b"",1)
        result=raw
    else:
        original=raw
        result=raw.replace(ANCHOR,ANCHOR+TARGET_LINE,1)
    if digest(original)!=oldhash:
        raise LaunchPrepError("config diverged from original SHA; refusing to touch mnemonic")
    return result,oldhash,digest(result)


def _read(folder:Path):
    target,manifest=checked_files(folder)
    before=target.read_bytes()
    try:
        record=json.loads(manifest.read_text("utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise LaunchPrepError("original signed-off manifest unreadable") from exc
    after,oldhash,newhash=validated_patch(before,record)
    return target,before,after,oldhash,newhash


def verify(folder:Path)->dict:
    target,before,after,oldhash,newhash=_read(folder)
    marker=folder/"launch_ready.json"
    if (before!=after or not marker.is_file() or marker.is_symlink()
            or marker.stat().st_uid!=os.geteuid()
            or stat.S_IMODE(marker.stat().st_mode)!=0o600):
        raise LaunchPrepError("launch config not upgraded and verified")
    try:
        record=json.loads(marker.read_text("utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise LaunchPrepError("launch provenance unreadable") from exc
    if any(record.get(k)!=v for k,v in (
        ("schema","SSE_POS_FULU_DEFERRED_LAUNCH_V1"),
        ("oldGeneratedConfigSha256",oldhash),
        ("upgradedLaunchConfigSha256",newhash),
        ("chainId",31339),("fuluForkEpoch",MAX_FAR_FUTURE),
        ("publicP2PVerified",False),
        ("networkStarted",False),
    )):
        raise LaunchPrepError("launch provenance does not match owner-only genesis")
    return {
        "schema":"SSE_POS_LAUNCH_CONFIG_VERIFIED_V1",
        "chainId":31339,"originalSha256":oldhash,"launchSha256":newhash,
        "FuluDeferredForTwoParticipantSmoke":True,
        "mnemonicReadLocallyButNotPrinted":True,"publicP2PVerified":False,
        "networkStartedByThisTool":False,
    }


def prepare(folder:Path,*,expected_source_sha:str)->dict:
    if (type(expected_source_sha) is not str
            or not BASELINE_SHA.fullmatch(expected_source_sha)):
        raise LaunchPrepError("expected exact approved GitHub SHA")
    current=subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=ROOT,text=True,timeout=5).strip()
    dirty=subprocess.check_output(
        ["git","status","--porcelain","--untracked-files=no"],
        cwd=ROOT,text=True,timeout=5).strip()
    if current!=expected_source_sha or dirty:
        raise LaunchPrepError("not clean approved source checkout")
    target,before,after,oldhash,newhash=_read(folder)
    marker=folder/"launch_ready.json"
    if marker.exists() or marker.is_symlink():
        raise LaunchPrepError("never overwrite existing launch-ready marker")
    if before!=after:
        temp=folder/(".network_params."+secrets.token_hex(10)+".tmp")
        flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
        if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
        fd=os.open(temp,flags,0o600)
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(after)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp,target)
        finally:
            if temp.exists():
                temp.unlink()
    record={
        "schema":"SSE_POS_FULU_DEFERRED_LAUNCH_V1",
        "sourceGitSha":expected_source_sha,
        "chainId":31339,
        "oldGeneratedConfigSha256":oldhash,
        "upgradedLaunchConfigSha256":newhash,
        "fuluForkEpoch":MAX_FAR_FUTURE,
        "fullNodeSupernodeRequiredForDeferredFulu":False,
        "publicP2PVerified":False,
        "networkStarted":False,
        "bootstrapMnemonicCopiedToGitHub":False,
    }
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
    fd=os.open(marker,flags,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(record,out,sort_keys=True,indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return verify(folder)


def main(argv=None):
    p=argparse.ArgumentParser(
        description="Patch only generated, hashed, protected SSE PoS genesis; preserve mnemonic")
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--expected-commit")
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--verify-only",action="store_true")
    a=p.parse_args(argv)
    try:
        if a.apply:
            if not a.expected_commit:
                raise LaunchPrepError("--expected-commit is required for --apply")
            record=prepare(a.output_dir,expected_source_sha=a.expected_commit)
        else:
            record=verify(a.output_dir)
        print(json.dumps(record,sort_keys=True,indent=2))
        return 0
    except (LaunchPrepError,PermissionError,OSError,ValueError,
            subprocess.SubprocessError) as exc:
        print("SSE_POS_LAUNCH_PREP_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
