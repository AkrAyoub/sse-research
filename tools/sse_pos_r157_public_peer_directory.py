#!/usr/bin/env python3
"""R157: compile fresh real-native node records into public R142 hint JSON.

Input is already-produced R156 local Besu/Lighthouse *public* metadata.
Output is a bounded, short-lived public discovery HINT for *independent*
HTTPS publishers to mirror. It is not a wallet credential, an admission
list, a signer, a service deployment, proof of peer reachability or a
publicly hosted URL. Two mirrors MAY carry one first-online peer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import sys

import sse_pos_r142_public_peer_discovery as r142
import sse_public_genesis as genesis

SCHEMA = "SSE_R156_LOCAL_NODE_NATIVE_IDENTITY_V1"
FIELDS = frozenset((
    "schema","capturedAtUtc","expiresAt","chainId",
    "executionGenesisHash","beaconGenesisValidatorsRoot",
    "overlayInterface","actualOverlayIpv6","publicPeerRecord",
    "publishedToAnyExternalDiscoveryService",
    "nativeRemoteHandshakeProven","localSigningKeyRead",
    "independentOperatorProven",
))
MAX_RECORDS = 64
MAX_FILE = 8192

class Refused(ValueError):
    pass

def parse_record(value, *, now):
    if type(value) is not dict or set(value)!=FIELDS:
        raise Refused("not an R156 bounded public-only local record")
    if (value["schema"]!=SCHEMA or type(value["chainId"]) is not int
            or value["chainId"]!=31340
            or value["executionGenesisHash"]!=genesis.EL_GENESIS
            or value["beaconGenesisValidatorsRoot"]!=genesis.CL_GENESIS
            or value["localSigningKeyRead"] is not False
            or value["publishedToAnyExternalDiscoveryService"] is not False
            or value["nativeRemoteHandshakeProven"] is not False
            or value["independentOperatorProven"] is not False):
        raise Refused("untrusted chain provenance or false live/public claim")
    expiry=value["expiresAt"]
    if type(expiry) is not int or not now<expiry<=now+600:
        raise Refused("expired or overlong public peer record")
    observed=value["capturedAtUtc"]
    if type(observed) is not str:
        raise Refused("missing actual observation UTC time")
    try:
        capture=datetime.fromisoformat(observed)
    except ValueError as exc:
        raise Refused("invalid actual capture timestamp") from exc
    if (capture.tzinfo is None or capture.utcoffset().total_seconds()!=0
            or not now-600<=capture.timestamp()<=now+60):
        raise Refused("stale/future native peer observation")
    peer=value["publicPeerRecord"]
    if type(peer) is not dict or set(peer)!=r142.PEER_FIELDS:
        raise Refused("incorrect public-only peer record fields")
    try:
        parsed=r142.parse(json.dumps({
            "schema":r142.SCHEMA,"chainId":31340,
            "executionGenesisHash":genesis.EL_GENESIS,
            "beaconGenesisValidatorsRoot":genesis.CL_GENESIS,
            "networkId":r142.NETWORK,"expiresAt":expiry,
            "peers":[peer],
        }).encode(),now=int(now))
    except r142.Refused as exc:
        raise Refused("not a legitimate native R142 hint syntax") from exc
    if len(parsed)!=1:
        raise Refused("no valid native peer record")
    return peer,expiry

def build(records, *, now):
    if type(records) is not list or not 1<=len(records)<=MAX_RECORDS:
        raise Refused("publisher requires 1–64 genuine node records")
    if type(now) is not int or now<1:
        raise Refused("invalid publication time")
    peers={}
    expiry=None
    for record in records:
        peer,until=parse_record(record,now=now)
        node=peer["nodeId"]
        if node in peers:
            if peers[node]!=peer:
                raise Refused("equivocating node identities in publication")
            raise Refused("duplicate public node hint")
        peers[node]=peer
        expiry=until if expiry is None else min(expiry,until)
    result={
        "schema":r142.SCHEMA,"chainId":31340,
        "executionGenesisHash":genesis.EL_GENESIS,
        "beaconGenesisValidatorsRoot":genesis.CL_GENESIS,
        "networkId":r142.NETWORK,"expiresAt":expiry,
        "peers":[peers[name] for name in sorted(peers)],
    }
    r142.parse(json.dumps(result,sort_keys=True).encode(),now=now)
    return result

def load_public_record(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_FILE:
        raise Refused("missing or oversized source record")
    try:
        return json.loads(path.read_text("utf-8"),
                          object_pairs_hook=r142._unique_keys)
    except (UnicodeError,ValueError) as exc:
        raise Refused("untrusted public node record JSON") from exc

def write_rotating(path,content):
    """Safe atomic replacement for expiring native P2P hint directories."""
    target=Path(path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise Refused("public directory target is not a regular file")
    target.parent.mkdir(parents=True,exist_ok=True)
    wire=(json.dumps(content,sort_keys=True,indent=2)+"\n").encode()
    if len(wire)>r142.MAX_BYTES:
        raise Refused("public peer directory exceeds bounded size")
    with tempfile.NamedTemporaryFile(
            dir=target.parent,mode="wb",prefix=".r157-",delete=False) as out:
        staged=Path(out.name)
        os.fchmod(out.fileno(),0o644)
        out.write(wire)
        out.flush()
        os.fsync(out.fileno())
    os.replace(staged,target)
    return target

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record",type=Path,required=True,action="append")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        now=int(datetime.now(timezone.utc).timestamp())
        report=build([load_public_record(x) for x in args.record],now=now)
        write_rotating(args.out,report)
        print(json.dumps({
            "schema":"SSE_R157_PUBLIC_DIRECTORY_CANDIDATE_V1",
            "candidateNodeCount":len(report["peers"]),
            "expiresAt":report["expiresAt"],
            "publishedToAnyHttpMirror":False,
            "peerIdentityOrReachabilityCryptographicallyVerified":False,
            "canBootstrapSecondPeerWithOneExistingFirstPeer":len(report["peers"])>=1,
        },sort_keys=True))
        return 0
    except (Refused,OSError,ValueError,TypeError,KeyError,r142.Refused) as exc:
        print("R157_PUBLIC_DIRECTORY_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
