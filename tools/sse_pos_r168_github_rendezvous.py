#!/usr/bin/env python3
"""R168 EXPERIMENTAL GitHub Issue rendezvous for genuine chain31340 peers.

Anonymous readers retrieve SHORT-LIVED public R156 native identity records
from a PUBLIC GitHub Issue comments API; publisher uses its OWN existing
GitHub CLI authorization to refresh ONE existing comment in place. No VM
address, ENR, participant allowlist or signer is hardcoded. This is
centralized *discovery availability*, NOT infrastructure-independent
permissionless discovery, member admission, peer authentication, or finality.

The original EL/CL software independently validates native handshakes and
the exact immutable genesis. GitHub accounts are NOT required to join:
only an operator wishing to publish via this OPTIONAL mirror needs write
authority there. Prefer multiple independent native HTTPS rendezvous later.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

import sse_pos_r142_public_peer_discovery as native
import sse_pos_r157_public_peer_directory as directory
import sse_pos_r156_local_native_peer_identity as local_identity

REPO="AkrAyoub/sse-research"
ISSUE=42
API=f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100"
MARKER="SSE_CHAIN31340_R156_NATIVE_PEER_V1\n"
MAX_RESPONSE=512_000
MAX_COMMENT=8192
MAX_COMMENTS=100
SCHEMA="SSE_R168_GITHUB_RENDEZVOUS_EXPERIMENTAL_V1"

class Refused(ValueError):
    pass

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def fetch_public(url=API):
    if url!=API:
        raise Refused("only the pinned public research rendezvous issue is permitted")
    req=urllib.request.Request(url,headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"SSE-chain31340-native-peer-discovery"})
    opener=urllib.request.build_opener(
        urllib.request.ProxyHandler({}),_NoRedirect())
    try:
        with opener.open(req,timeout=8) as response:
            if response.status!=200 or response.url!=url:
                raise Refused("GitHub public issue API unavailable")
            raw=response.read(MAX_RESPONSE+1)
    except (OSError,ValueError) as exc:
        raise Refused("anonymous public rendezvous unavailable") from exc
    if len(raw)>MAX_RESPONSE:
        raise Refused("public issue response exceeds resource limit")
    try:
        obj=json.loads(raw,object_pairs_hook=native._unique_keys)
    except (ValueError,UnicodeError) as exc:
        raise Refused("invalid public issue response JSON") from exc
    if type(obj) is not list or len(obj)>MAX_COMMENTS:
        raise Refused("unbounded public issue comments page")
    return obj

def marker_record(body,*,now):
    if type(body) is not str or not body.startswith(MARKER):
        return None
    if len(body.encode("utf-8"))>MAX_COMMENT:
        raise Refused("oversized native peer announcement")
    try:
        record=json.loads(body[len(MARKER):],
                          object_pairs_hook=native._unique_keys)
    except (ValueError,UnicodeError) as exc:
        raise Refused("invalid marked R156 public node record") from exc
    try:
        peer,expiry=directory.parse_record(record,now=now)
    except directory.Refused as exc:
        raise Refused("invalid or stale native public node announcement") from exc
    return record

def compile_comments(comments,*,now):
    """Return a real R142 peer feed from only fresh R156 public records."""
    if type(comments) is not list or len(comments)>MAX_COMMENTS:
        raise Refused("invalid bounded public GitHub comments list")
    latest={}
    keys={}
    for comment in comments:
        if type(comment) is not dict or type(comment.get("body")) is not str:
            continue
        if not comment["body"].startswith(MARKER):
            continue
        try:
            record=marker_record(comment["body"],now=now)
        except Refused:
            # Expired or bad public comments cannot prevent new peers
            # joining, but still cannot be used as trusted bootstrap.
            continue
        peer=record["publicPeerRecord"]
        node=peer["nodeId"]
        pub=peer["executionEnode"].split("@",1)[0]
        old=keys.get(node)
        if old and old!=pub:
            # Conflicting public key for a claimed identity; never pick a
            # privileged commenter or turn a Sybil record into a whitelist.
            raise Refused("conflicting native identity in public rendezvous")
        keys[node]=pub
        if (node not in latest or
                record["expiresAt"]>latest[node]["expiresAt"]):
            latest[node]=record
    if not latest:
        raise Refused("no fresh real native identities published in public issue")
    # Bound per-feed size; untrusted records are hints, not memberships.
    selected=sorted(latest.values(),
                    key=lambda obj:obj["expiresAt"],reverse=True)
    return directory.build(selected[:directory.MAX_RECORDS],now=now)

def discover(*,getter=fetch_public,now=None):
    now=int(datetime.now(timezone.utc).timestamp()) if now is None else now
    feed=compile_comments(getter(),now=now)
    peers=native.parse(json.dumps(feed).encode(),now=now)
    return {
        "schema":SCHEMA,
        "chainId":31340,
        "executionBootnodes":[peer[1] for peer in peers],
        "beaconBootnodes":[peer[2] for peer in peers],
        "candidateNodeCount":len(peers),
        "validSourceCount":1,
        "oneTimeManualEnodeInputRequired":False,
        "actualNativePeersAuthenticated":False,
        "peerReachabilityVerified":False,
        "publisherIdentityOrIndependenceVerified":False,
        "liveDirectoryMirrorsVerified":False,
        "temporaryCentralizedRendezvous":True,
        "independentDiscoveryInfrastructureVerified":False,
        "discoverySource":API,
    }

def gh(args):
    if type(args) is not list:
        raise Refused("invalid CLI args")
    command=["gh","api",*args]
    try:
        result=subprocess.run(
            command,capture_output=True,text=True,check=False,
            timeout=25,env={**os.environ,"GH_PROMPT_DISABLED":"1",
                            "GIT_TERMINAL_PROMPT":"0"})
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise Refused("maintainer GitHub CLI authorization unavailable") from exc
    if result.returncode!=0 or len(result.stdout)>MAX_RESPONSE:
        raise Refused("GitHub public announcement update refused; check own gh auth")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise Refused("invalid GitHub acknowledgement") from exc

def publish(record,*,now=None,read=fetch_public,client=gh):
    now=int(datetime.now(timezone.utc).timestamp()) if now is None else now
    try:
        peer,expiry=directory.parse_record(record,now=now)
    except directory.Refused as exc:
        raise Refused("not a current genuine R156 native identity") from exc
    body=MARKER+json.dumps(record,sort_keys=True,separators=(",",":"))
    if len(body.encode("utf-8"))>MAX_COMMENT:
        raise Refused("public-only identity announcement too large")
    account=client(["user"])
    login=account.get("login") if type(account) is dict else None
    if (type(login) is not str or
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})",login)):
        raise Refused("GitHub publisher identity unavailable")
    matches=[]
    for comment in read():
        if type(comment) is not dict or not isinstance(comment.get("body"),str):
            continue
        user=comment.get("user")
        if type(user) is not dict or user.get("login")!=login:
            continue
        text=comment["body"]
        if not text.startswith(MARKER):
            continue
        try:
            previous=json.loads(text[len(MARKER):],
                                object_pairs_hook=native._unique_keys)
        except (ValueError,UnicodeError):
            continue
        if (type(previous) is dict and
                type(previous.get("publicPeerRecord")) is dict and
                previous["publicPeerRecord"].get("nodeId")==peer["nodeId"]
                and type(comment.get("id")) is int):
            matches.append(comment["id"])
    if len(matches)>1:
        raise Refused("duplicate own announcement comments; no unsafe automatic overwrite")
    if matches:
        path=f"repos/{REPO}/issues/comments/{matches[0]}"
        mode="PATCH"
    else:
        path=f"repos/{REPO}/issues/{ISSUE}/comments"
        mode="POST"
    response=client([path,"--method",mode,"-f","body="+body])
    if (type(response) is not dict or type(response.get("id")) is not int
            or response.get("body")!=body):
        raise Refused("GitHub did not confirm exact updated public-only node announcement")
    return {
        "schema":SCHEMA,
        "nodeId":peer["nodeId"],"expiresAt":expiry,
        "publicCommentId":response["id"],
        "refreshedExistingComment":bool(matches),
        "publicIssueUrl":f"https://github.com/{REPO}/issues/{ISSUE}",
        "nativePeerHandshakeVerified":False,
        "independentInfrastructureVerified":False,
        "githubAccountRequiredForJoining":False,
        "githubAccountUsedOnlyForOptionalPublishing":True,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--discover",action="store_true")
    modes.add_argument("--publish",type=Path,metavar="R156_JSON")
    modes.add_argument("--publish-live",action="store_true",
                       help="read real local Besu+Lighthouse public P2P APIs then update own issue comment")
    p.add_argument("--node-id",
                   help="required for --publish-live; not a validator key or membership credential")
    args=p.parse_args(argv)
    try:
        if args.discover:
            if args.node_id:
                raise Refused("--discover does not need node identity")
            result=discover()
        elif args.publish_live:
            if not args.node_id:
                raise Refused("--publish-live requires local public node ID")
            result=publish(local_identity.capture(args.node_id))
        else:
            if args.node_id:
                raise Refused("--node-id only supported for local live capture")
            result=publish(directory.load_public_record(args.publish))
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,directory.Refused,native.Refused,OSError,ValueError,
            TypeError,KeyError) as exc:
        print("R168_EXPERIMENTAL_GITHUB_RENDEZVOUS_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
