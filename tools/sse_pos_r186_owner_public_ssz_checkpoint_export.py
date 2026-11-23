#!/usr/bin/env python3
"""R186: export owner chain31340 finalized SSZ pair via localhost Beacon API.

The same finalized block root MUST be observed before and after downloading
both binary artifacts. Source-only public Beacon state/block; no secrets.
Creates exactly one new output directory, never edits existing chain data.
The downloaded SSZ is not itself proof of native network synchronization.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime,timezone

BASE="http://127.0.0.1:25052"
GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
HEX32=re.compile(r"0x[0-9a-f]{64}\Z")
MAX_STATE=16_000_000
MAX_BLOCK=2_000_000
TIMEOUT=20
class Refused(ValueError): pass

def fetch(path, *,binary=False, max_size=32768):
    if not path.startswith("/eth/v1/beacon/") and not path.startswith("/eth/v2/"):
        raise Refused("unapproved owner Beacon path")
    req=urllib.request.Request(BASE+path,headers={
        "Accept":"application/octet-stream" if binary else "application/json"})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                req,timeout=TIMEOUT) as response:
            if response.status!=200:
                raise Refused("R186_OWNER_HTTP_NON_200")
            if binary and "application/octet-stream" not in response.headers.get(
                    "Content-Type","").lower():
                raise Refused("R186_OWNER_NOT_SSZ")
            body=response.read(max_size+1)
    except urllib.error.HTTPError as exc:
        raise Refused("R186_OWNER_HTTP_"+str(exc.code)) from exc
    except (OSError,urllib.error.URLError,TimeoutError) as exc:
        raise Refused("R186_OWNER_TRANSPORT_UNAVAILABLE") from exc
    if not body or len(body)>max_size:
        raise Refused("R186_OWNER_RESPONSE_EMPTY_OR_OVERSIZED")
    if binary:
        return body
    try:
        obj=json.loads(body)
    except (ValueError,UnicodeError) as exc:
        raise Refused("R186_INVALID_OWNER_BEACON_JSON") from exc
    if type(obj) is not dict or type(obj.get("data")) is not dict:
        raise Refused("R186_INVALID_OWNER_BEACON_SHAPE")
    return obj["data"]

def checkpoint(get=fetch):
    gen=get("/eth/v1/beacon/genesis")
    if gen.get("genesis_validators_root")!=GENESIS:
        raise Refused("R186_WRONG_ORIGINAL_BEACON_GENESIS")
    chk=get("/eth/v1/beacon/states/head/finality_checkpoints")
    final=chk.get("finalized")
    if type(final) is not dict:
        raise Refused("R186_NO_FINALIZED_CHECKPOINT")
    root=final.get("root")
    epoch=final.get("epoch")
    if not isinstance(root,str) or not HEX32.fullmatch(root) or (
            type(epoch) is not str or not epoch.isdecimal() or int(epoch)<1):
        raise Refused("R186_INVALID_FINALIZED_CHECKPOINT")
    return int(epoch),root

def collect(get=fetch):
    epoch,root=checkpoint(get)
    state=get("/eth/v2/debug/beacon/states/finalized",
              binary=True,max_size=MAX_STATE)
    if type(state) is not bytes or not 1024<=len(state)<=MAX_STATE:
        raise Refused("R186_INVALID_FINALIZED_STATE_BYTES")
    epoch_mid,root_mid=checkpoint(get)
    if (epoch_mid,root_mid)!=(epoch,root):
        raise Refused("R186_FINALIZED_ROOT_MOVED_DURING_STATE_EXPORT")
    block=get("/eth/v2/beacon/blocks/finalized",
              binary=True,max_size=MAX_BLOCK)
    if type(block) is not bytes or not 128<=len(block)<=MAX_BLOCK:
        raise Refused("R186_INVALID_FINALIZED_BLOCK_BYTES")
    epoch_after,root_after=checkpoint(get)
    if (epoch_after,root_after)!=(epoch,root):
        raise Refused("R186_FINALIZED_ROOT_MOVED_DURING_BLOCK_EXPORT")
    header=get("/eth/v1/beacon/headers/finalized")
    if header.get("root")!=root:
        raise Refused("R186_FINALIZED_HEADER_ROOT_CHANGED")
    slot=((header.get("header") or {}).get("message") or {}).get("slot")
    if type(slot) is not str or not slot.isdecimal() or int(slot)<epoch*32:
        raise Refused("R186_INVALID_FINALIZED_HEADER_SLOT")
    manifest={
        "schema":"SSE_R186_ORIGINAL_CHAIN31340_PUBLIC_SSZ_CHECKPOINT_V1",
        "chainId":31340,"genesisValidatorsRoot":GENESIS,
        "finalizedEpoch":epoch,"finalizedBlockRoot":root,
        "finalizedSlot":int(slot),
        "checkpointState":{"filename":"checkpoint-state.ssz","bytes":len(state),
            "sha256":hashlib.sha256(state).hexdigest()},
        "checkpointBlock":{"filename":"checkpoint-block.ssz","bytes":len(block),
            "sha256":hashlib.sha256(block).hexdigest()},
        "capturedAtUtc":datetime.now(timezone.utc).isoformat(),
        "ownerBeaconOnlyLocalhost":True,
        "finalizedRootStableAcrossReads":True,
        "cryptographicStateRootVerifiedByThisExporter":False,
        "clientCheckpointValidationStillRequired":True,
        "containsWalletOrEngineJwt":False}
    return manifest,state,block

def persist(out,manifest,state,block):
    out=Path(out).expanduser()
    if out.is_symlink() or out.exists() or not out.parent.is_dir():
        raise Refused("R186_CHECKPOINT_OUTPUT_ALREADY_EXISTS_OR_INVALID")
    out.mkdir(mode=0o700)
    for filename,content in (
        ("checkpoint-state.ssz",state),("checkpoint-block.ssz",block),
        ("checkpoint-manifest.json",
         (json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode())):
        f=out/filename
        fd=os.open(f,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True,
                   help="new (non-existing) dir for PUBLIC checkpoint pair")
    a=p.parse_args()
    try:
        manifest,state,block=collect()
        out=persist(a.out,manifest,state,block)
        print(json.dumps({"state":"EXPORTED_FINALIZED_PUBLIC_SSZ_PAIR",
          "outputDirectory":str(out),"manifest":manifest},
          indent=2,sort_keys=True))
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError) as exc:
        print("R186_CHECKPOINT_EXPORT_REFUSED: "+str(exc),file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
