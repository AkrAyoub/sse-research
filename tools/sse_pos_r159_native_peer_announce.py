#!/usr/bin/env python3
"""R159: periodically announce the actual local R156 P2P record to public mirrors.

No GitHub token, wallet, validator signer, admin RPC, private P2P key,
hardcoded peer, fixed IP or user prompt. POST public-only short-lived
native identity to HTTPS peer-directory mirrors declared in the exact
chain31340 release. Two source acknowledgements are needed to report
redundant publication; fewer are recorded as partial, never a live peer
handshake or permission to join. Does not create public mirrors itself.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import urllib.request

import sse_pos_r142_public_peer_discovery as r142
import sse_pos_r157_public_peer_directory as r157
import sse_public_genesis as genesis

MAX_BODY=8192

class Refused(ValueError):
    pass

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def send_https(url, payload):
    r142.check_source(url)
    if not url.endswith("/peers.json"):
        raise Refused("reviewed directory submission endpoint must be /peers.json")
    wire=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    if not 0<len(wire)<=MAX_BODY:
        raise Refused("oversized public-only announcement")
    request=urllib.request.Request(url,data=wire,method="POST",headers={
        "Accept":"application/json","Content-Type":"application/json"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPSHandler(),
                                       _NoRedirect())
    try:
        with opener.open(request,timeout=8) as response:
            if response.status!=202 or response.url!=url:
                raise Refused("directory did not accept public announcement")
            raw=response.read(4097)
    except (OSError,ValueError) as exc:
        raise Refused("public native peer directory endpoint unreachable") from exc
    if len(raw)>4096:
        raise Refused("oversized directory acknowledgement")
    try:
        result=json.loads(raw,object_pairs_hook=r142._unique_keys)
    except (UnicodeError,ValueError) as exc:
        raise Refused("invalid directory acknowledgement JSON") from exc
    if (type(result) is not dict or result.get("accepted") is not True
            or result.get("nodeId")!=payload["publicPeerRecord"]["nodeId"]
            or result.get("expiresAt")!=payload["expiresAt"]
            or result.get("membershipOrRoleGranted") is not False):
        raise Refused("remote directory returned inconsistent publication status")
    return result

def announce(record, release, *, now=None, sender=send_https):
    data=genesis.manifest(release)
    now=int(datetime.now(timezone.utc).timestamp()) if now is None else now
    try:
        peer,expiry=r157.parse_record(record,now=now)
    except r157.Refused as exc:
        raise Refused("local public peer record stale or invalid") from exc
    sources=data["replaceablePeerDirectorySources"]
    # This is not permissioned chain admission. Do not guess endpoints
    # when the release has no actual published independent sources yet.
    if not sources:
        return {
            "schema":"SSE_R159_PUBLIC_ANNOUNCEMENT_V1",
            "nodeId":peer["nodeId"],
            "attemptedSources":0,"acknowledgedSources":0,
            "redundantlyPublishedByIndependentSourcesProven":False,
            "state":"AWAITING_REAL_PUBLIC_DIRECTORY_SOURCES",
            "nativePeerHandshakeVerified":False,
        }
    successful=[]
    for url in sources:
        try:
            result=sender(url,record)
            if (type(result) is dict and result.get("accepted") is True
                    and result.get("nodeId")==peer["nodeId"]
                    and result.get("expiresAt")==expiry
                    and result.get("membershipOrRoleGranted") is False):
                successful.append(url)
        except (Refused,OSError,ValueError,TypeError):
            continue
    return {
        "schema":"SSE_R159_PUBLIC_ANNOUNCEMENT_V1",
        "nodeId":peer["nodeId"],
        "attemptedSources":len(sources),"acknowledgedSources":len(successful),
        "redundantlyPublishedByIndependentSourcesProven":False,
        "state":("TWO_OR_MORE_DISTINCT_URLS_ACKNOWLEDGED_INDEPENDENCE_UNPROVEN"
                 if len(successful)>=2 else "PARTIAL_OR_UNAVAILABLE_PUBLIC_MIRRORS"),
        "nativePeerHandshakeVerified":False,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record",type=Path,required=True)
    p.add_argument("--release",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        record=r157.load_public_record(args.record)
        data=genesis.read_manifest(args.release)
        print(json.dumps(announce(record,data),sort_keys=True,indent=2))
        return 0
    except (Refused,r157.Refused,genesis.Refused,OSError,ValueError,TypeError) as exc:
        print("R159_PUBLIC_ANNOUNCEMENT_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
