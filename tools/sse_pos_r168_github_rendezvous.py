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
import time
import urllib.parse
import urllib.error
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

def _github_get(url, *, allowed_path):
    """Uncached anonymous HTTPS GitHub read, no redirects or private API."""
    parts=urllib.parse.urlsplit(url)
    if (parts.scheme!="https" or parts.hostname!="api.github.com"
            or parts.path!=allowed_path or parts.port not in (None,443)
            or parts.username or parts.password or parts.fragment):
        raise Refused("only pinned public Github rendezvous API paths allowed")
    nonce=str(time.time_ns())
    suffix="&" if parts.query else "?"
    request_url=url+suffix+"sse_refresh="+nonce
    req=urllib.request.Request(request_url,headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"SSE-chain31340-native-peer-discovery",
        "Cache-Control":"no-store, max-age=0",
        "Pragma":"no-cache"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       _NoRedirect())
    try:
        with opener.open(req,timeout=8) as response:
            if response.status!=200 or response.url!=request_url:
                raise Refused("unexpected public GitHub API response")
            raw=response.read(MAX_RESPONSE+1)
    except urllib.error.HTTPError as exc:
        # An unauthenticated GitHub API is limited by egress IP, which
        # may be shared among independent VMs behind a provider NAT.
        # Distinguish rate-exhaustion, abuse throttling and other HTTP
        # responses without ever logging response bodies or credentials.
        remaining=exc.headers.get("X-RateLimit-Remaining")
        if exc.code in (403,429) and remaining=="0":
            raise Refused("GITHUB_ANONYMOUS_API_RATE_LIMIT_EXHAUSTED") from exc
        if exc.code in (403,429):
            raise Refused("GITHUB_ANONYMOUS_API_THROTTLED_OR_FORBIDDEN") from exc
        raise Refused(f"GITHUB_PUBLIC_API_HTTP_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise Refused("GITHUB_PUBLIC_API_DNS_TLS_OR_EGRESS_FAILED") from exc
    except (OSError,TimeoutError) as exc:
        raise Refused("GITHUB_PUBLIC_API_TRANSPORT_UNAVAILABLE") from exc
    if len(raw)>MAX_RESPONSE:
        raise Refused("GitHub public API response exceeds resource limit")
    try:
        return json.loads(raw,object_pairs_hook=native._unique_keys)
    except (ValueError,UnicodeError) as exc:
        raise Refused("invalid anonymous Github response") from exc

def fetch_public(url=API):
    if url!=API:
        raise Refused("only pinned public research rendezvous API is permitted")
    parsed=_github_get(url,allowed_path=f"/repos/{REPO}/issues/{ISSUE}/comments")
    if type(parsed) is not list or len(parsed)>MAX_COMMENTS:
        raise Refused("unbounded public issue comments page")
    # The issue-comments COLLECTION can stay cached after a PATCH despite
    # no-cache headers. Read the latest actual marked record by its dynamic
    # comment ID, never a hardcoded VM identity or permanent peer address.
    for item in parsed:
        if (type(item) is not dict or
                type(item.get("id")) is not int or
                type(item.get("body")) is not str or
                not item["body"].startswith(MARKER)):
            continue
        ident=item["id"]
        # This is a single-peer research experiment. Do not turn public
        # comments into a large N+1 unbounded API request fanout.
        if sum(type(v) is dict and isinstance(v.get("body"),str)
               and v["body"].startswith(MARKER) for v in parsed)>8:
            raise Refused("too many published native comments for bounded live refresh")
        detail=_github_get(
            f"https://api.github.com/repos/{REPO}/issues/comments/{ident}",
            allowed_path=f"/repos/{REPO}/issues/comments/{ident}")
        if (type(detail) is not dict or detail.get("id")!=ident
                or not isinstance(detail.get("body"),str)):
            raise Refused("actual public issue comment readback mismatch")
        item["body"]=detail["body"]
        item["updated_at"]=detail.get("updated_at")
    return parsed

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

def diagnose_public(*,getter=fetch_public,now=None):
    """Read-only public availability diagnostics, without printing enodes/ENRs.

    An immediately created GitHub issue comment may not yet appear in
    anonymous list results. This distinguishes empty lists, stale
    comments and malformed native records; it never fakes a peer.
    """
    now=int(datetime.now(timezone.utc).timestamp()) if now is None else now
    comments=getter()
    counts={"publicCommentsReturned":len(comments),
            "markedNativeComments":0,
            "freshValidNativeComments":0,
            "expiredOrInvalidNativeComments":0}
    for item in comments:
        if type(item) is not dict or not isinstance(item.get("body"),str):
            continue
        if not item["body"].startswith(MARKER):
            continue
        counts["markedNativeComments"]+=1
        try:
            marker_record(item["body"],now=now)
            counts["freshValidNativeComments"]+=1
        except Refused:
            counts["expiredOrInvalidNativeComments"]+=1
    return {
        "schema":"SSE_R169_PUBLIC_RENDEZVOUS_DIAGNOSTIC_V1",
        **counts,
        "publicReadbackProven":counts["freshValidNativeComments"]>0,
        "nativePeerHandshakeVerified":False,
        "independentInfrastructureVerified":False,
        "fullNodeJoinVerified":False,
    }

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
    modes.add_argument("--diagnose-public",action="store_true",
                       help="anonymous cache/expiry diagnostics, never print enode or ENR")
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
        elif args.diagnose_public:
            if args.node_id:
                raise Refused("--diagnose-public does not need node identity")
            result=diagnose_public()
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
