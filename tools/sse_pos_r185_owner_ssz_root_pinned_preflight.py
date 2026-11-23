#!/usr/bin/env python3
"""R185: read-only PRE-FLIGHT for owner finalized SSZ export, no files or release.

Only trusted loopback Beacon API. Pins immutable finalized block ROOT once;
fetches both state and block BY THAT ROOT, no moving finalized aliases.
Never accesses Engine API, wallet, keys, Docker or SSH. No SSZ persistence.
"""
from __future__ import annotations
import json
import re
import sys
import urllib.error
import urllib.request

BASE="http://127.0.0.1:25052"
EXPECTED_GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
HEX32=re.compile(r"0x[0-9a-f]{64}\Z")
MAX_JSON=32768
MAX_STATE=16_000_000
MAX_BLOCK=2_000_000

class Refused(ValueError): pass

def get(path, *,binary=False,opener=None,maxbytes=None):
    if opener is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if not path.startswith("/eth/v1/beacon/") and not path.startswith("/eth/v2/"):
        raise Refused("unapproved Beacon endpoint")
    if maxbytes is None:
        maxbytes=MAX_STATE if binary else MAX_JSON
    req=urllib.request.Request(BASE+path,headers={
        "Accept":"application/octet-stream" if binary else "application/json"})
    try:
        with opener.open(req,timeout=15) as response:
            if response.status!=200:
                raise Refused("owner Beacon endpoint not available")
            ct=response.headers.get("Content-Type","")
            if binary and "application/octet-stream" not in ct.lower():
                raise Refused("owner Beacon did not return SSZ")
            raw=response.read(maxbytes+1)
    except urllib.error.HTTPError as exc:
        # Distinguish unsupported root-pinned state/block lookup without
        # logging server body, local host details, or authentication.
        raise Refused(f"R185_OWNER_BEACON_HTTP_{exc.code}_"
                      +("SSZ" if binary else "JSON")) from exc
    except (OSError,TimeoutError,urllib.error.URLError) as exc:
        raise Refused("R185_OWNER_BEACON_TRANSPORT_UNAVAILABLE") from exc
    if len(raw)>maxbytes or not raw:
        raise Refused("owner Beacon response empty or oversized")
    if binary:
        return len(raw)
    try:
        obj=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise Refused("invalid owner Beacon JSON") from exc
    if type(obj) is not dict or type(obj.get("data")) is not dict:
        raise Refused("invalid owner Beacon JSON shape")
    return obj["data"]

def probe(*,fetch=get):
    gen=fetch("/eth/v1/beacon/genesis")
    if gen.get("genesis_validators_root")!=EXPECTED_GENESIS:
        raise Refused("owner genesis is not original chain31340")
    checkpoint=fetch("/eth/v1/beacon/states/head/finality_checkpoints")
    finalized=checkpoint.get("finalized")
    if type(finalized) is not dict:
        raise Refused("missing owner finalized checkpoint")
    epoch=finalized.get("epoch")
    root=finalized.get("root")
    if (type(epoch) is not str or not epoch.isdecimal() or int(epoch)<1
            or type(root) is not str or not HEX32.fullmatch(root)):
        raise Refused("invalid owner finalized checkpoint")
    # Probe the root-pinned URLs, NOT /finalized aliases that could
    # advance independently between two separate HTTP GETs.
    state_path="/eth/v2/debug/beacon/states/"+root
    block_path="/eth/v2/beacon/blocks/"+root
    state_bytes=fetch(state_path,binary=True,maxbytes=MAX_STATE)
    block_bytes=fetch(block_path,binary=True,maxbytes=MAX_BLOCK)
    if (type(state_bytes) is not int or type(block_bytes) is not int
            or state_bytes<1024 or block_bytes<128):
        raise Refused("unexpected bounded real SSZ byte lengths")
    return {"schema":"SSE_R185_IMMUTABLE_ROOT_SSZ_READONLY_PREFLIGHT_V1",
            "chainId":31340,"genesisValidatorsRoot":EXPECTED_GENESIS,
            "checkpointEpoch":int(epoch),"finalizedBlockRoot":root,
            "checkpointStateBytes":state_bytes,
            "checkpointBlockBytes":block_bytes,
            "sameImmutableBlockRootRequestedForBoth":True,
            "localOwnerBeaconApiOnly":True,
            "sszFilesPersisted":False,
            "githubReleaseCreated":False,
            "anyHostOrChainMutation":False}

if __name__=="__main__":
    try:
        print(json.dumps(probe(),sort_keys=True,indent=2))
    except (Refused,ValueError,KeyError,TypeError) as exc:
        print("R185_CHECKPOINT_PREFLIGHT_REFUSED: "+str(exc),file=sys.stderr)
        sys.exit(2)
