#!/usr/bin/env python3
"""R179 owner-only read-only Beacon finalized-checkpoint source probe.

Run on VM4707 localhost against its EXISTING non-signing Beacon REST.
Never sends a state snapshot, exposes the Beacon API, reads signer keys
or makes changes to a container, Docker or chain files.
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error

BASE="http://127.0.0.1:25052"
PATHS={
    "genesis":"/eth/v1/beacon/genesis",
    "finality":"/eth/v1/beacon/states/head/finality_checkpoints",
    "header":"/eth/v1/beacon/headers/finalized",
}
EXPECTED_GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"

class Refused(ValueError):
    pass

def fetch_json(path, *,opener=None):
    if path not in PATHS.values():
        raise Refused("unapproved Beacon endpoint")
    if opener is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request(BASE+path,
                                  headers={"Accept":"application/json"})
    try:
        with opener.open(request,timeout=8) as response:
            if response.status!=200:
                raise Refused("local Beacon endpoint HTTP non-200")
            data=response.read(16385)
    except (OSError,ValueError) as exc:
        raise Refused("existing owner Beacon API inaccessible") from exc
    if len(data)>16384:
        raise Refused("unbounded owner Beacon response")
    try:
        obj=json.loads(data)
    except ValueError as exc:
        raise Refused("owner Beacon returned invalid JSON") from exc
    if type(obj) is not dict or type(obj.get("data")) is not dict:
        raise Refused("owner Beacon returned invalid payload")
    return obj

def probe(*,fetch=fetch_json):
    genesis=fetch(PATHS["genesis"])["data"]
    root=genesis.get("genesis_validators_root")
    if root!=EXPECTED_GENESIS:
        raise Refused("owner Beacon genesis root mismatch")
    finality=fetch(PATHS["finality"])["data"].get("finalized")
    if type(finality) is not dict:
        raise Refused("no finalized checkpoint in owner Beacon")
    epoch=finality.get("epoch")
    checkpoint_root=finality.get("root")
    if (type(epoch) is not str or not epoch.isdecimal() or
            int(epoch)<1 or type(checkpoint_root) is not str or
            len(checkpoint_root)!=66):
        raise Refused("no non-genesis valid finalized checkpoint")
    header=fetch(PATHS["header"])
    actual=header["data"]
    if actual.get("root")!=checkpoint_root:
        raise Refused("finalized header root disagrees with checkpoint root")
    slot=((actual.get("header") or {}).get("message") or {}).get("slot")
    if type(slot) is not str or not slot.isdecimal() or int(slot)<int(epoch)*32:
        raise Refused("finalized header slot invalid")
    return {"schema":"SSE_R179_OWNER_FINALIZED_CHECKPOINT_READONLY_V1",
            "genesisValidatorsRoot":root,
            "finalizedEpoch":int(epoch),
            "finalizedBlockRoot":checkpoint_root,
            "finalizedSlot":int(slot),
            "ownerBeaconApiOnlyLocal":True,
            "remoteCheckpointBytesAvailableOrReachable":False,
            "mutatedAnyHostOrChainState":False}

def main():
    try:
        print(json.dumps(probe(),sort_keys=True,indent=2))
        return 0
    except (Refused,KeyError,TypeError,ValueError) as exc:
        print("R179_OWNER_CHECKPOINT_PROBE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
