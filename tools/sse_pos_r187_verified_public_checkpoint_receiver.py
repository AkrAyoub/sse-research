#!/usr/bin/env python3
"""R187: anonymous, immutable, SHA256-pinned chain31340 checkpoint download.

Use only PUBLIC release assets. The pinned hashes were actually printed by
the original VM4707 operator after an observed finalized epoch565 export.
No paid/API authentication, VM credentials, Docker or chain data mutations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

TAG="chain31340-checkpoint-e565-86fdc98df47d641a"
BASE="https://github.com/AkrAyoub/sse-research/releases/download/"+TAG+"/"
GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
ROOT="0x86fdc98df47d641a27fbc95eb3229dfc0e24553d1dc57bfbe2599e161b60a259"
FILES={
 "checkpoint-state.ssz":(2859760,"8c03cdec390bb9442d7ac8d98a01a1d6dc03861602bf085d95553554ea5a1d41"),
 "checkpoint-block.ssz":(1417,"9e2859ca4e57bf1228d010bd7958483ee111b4ec10d39c5d5aa82f691c702373"),
}
MAX_MANIFEST=4096
class Refused(ValueError): pass

def download(url, *,max_bytes):
    if url not in [BASE+k for k in (*FILES,"checkpoint-manifest.json")]:
        raise Refused("unapproved checkpoint asset")
    req=urllib.request.Request(url,headers={"User-Agent":"SSE-chain31340-r187"})
    try:
        with urllib.request.urlopen(req,timeout=40) as response:
            if response.status!=200:
                raise Refused("public checkpoint response non-200")
            body=response.read(max_bytes+1)
    except urllib.error.HTTPError as exc:
        raise Refused("public checkpoint HTTP_"+str(exc.code)) from exc
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise Refused("public checkpoint HTTPS unavailable") from exc
    if not 0<len(body)<=max_bytes:
        raise Refused("public checkpoint asset size outside bounds")
    return body

def verify_manifest(data):
    try:
        m=json.loads(data)
    except (UnicodeError,ValueError) as exc:
        raise Refused("invalid checkpoint manifest JSON") from exc
    if (type(m) is not dict or
        m.get("schema")!="SSE_R186_ORIGINAL_CHAIN31340_PUBLIC_SSZ_CHECKPOINT_V1" or
        m.get("chainId")!=31340 or
        m.get("genesisValidatorsRoot")!=GENESIS or
        m.get("finalizedEpoch")!=565 or m.get("finalizedSlot")!=18080 or
        m.get("finalizedBlockRoot")!=ROOT or
        m.get("finalizedRootStableAcrossReads") is not True or
        m.get("containsWalletOrEngineJwt") is not False):
        raise Refused("unexpected original-chain checkpoint identity")
    for key,field in (("checkpoint-state.ssz","checkpointState"),
                      ("checkpoint-block.ssz","checkpointBlock")):
        item=m.get(field)
        if (type(item) is not dict or item.get("filename")!=key or
            item.get("bytes")!=FILES[key][0] or item.get("sha256")!=FILES[key][1]):
            raise Refused("manifest checkpoint SHA/size not pinned")
    return m

def stage(out,*,getter=download):
    out=Path(out)
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise Refused("checkpoint destination exists or parent unavailable")
    manifest=getter(BASE+"checkpoint-manifest.json",max_bytes=MAX_MANIFEST)
    parsed=verify_manifest(manifest)
    blobs={}
    for filename,(size,digest) in FILES.items():
        blob=getter(BASE+filename,max_bytes=size)
        if len(blob)!=size or hashlib.sha256(blob).hexdigest()!=digest:
            raise Refused("downloaded checkpoint SHA256/size mismatch: "+filename)
        blobs[filename]=blob
    # Download and verify everything before making any local changes.
    # These exact SSZ and manifest assets are PUBLIC chain data. The
    # future hardened Lighthouse container intentionally drops all
    # capabilities, so its bind-mounted checkpoint must be traversable
    # and readable even when owned by the non-root joining account.
    # Do not apply these modes to ANY wallet/JWT/Beacon DB or parent dir.
    out.mkdir(mode=0o755)
    # Caller umask may be 077: set exact public mode on this new dir.
    out.chmod(0o755)
    for name,blob in [("checkpoint-manifest.json",manifest),*blobs.items()]:
        fd=os.open(out/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),0o644)
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
    return {"schema":"SSE_R187_CHECKPOINT_RECEIVER_VERIFIED_V1",
            "sourceRelease":TAG,
            "localDestination":str(out),
            "finalizedEpoch":565,
            "originalGenesisRoot":GENESIS,
            "checkpointRoot":ROOT,
            "stateAndBlockSha256Verified":True,
            "consensusHashTreeRootVerifiedByThisDownloader":False,
            "nativePeersAndFinalityVerified":False,
            "existingDockerOrBeaconDatabaseModified":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    try:
        print(json.dumps(stage(a.out),sort_keys=True,indent=2))
        return 0
    except (Refused,OSError,ValueError,KeyError,TypeError) as exc:
        print("R187_CHECKPOINT_RECEIVER_REFUSED: "+str(exc),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
