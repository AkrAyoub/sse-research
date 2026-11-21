#!/usr/bin/env python3
"""R149: public immutable chain31340 genesis archive acquisition.

Downloads only from explicitly released HTTPS mirrors, validates original
R59 archive SHA256 and member hashes, then installs via exclusive atomic
file creation. Empty mirror lists are an explicit blocker, not permission
to recreate genesis. This code does not fetch peer IPs or change live nodes.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request

SCHEMA = "SSE_CHAIN31340_PUBLIC_RELEASE_V1"
ARCHIVE_SHA = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
EL_GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
CL_GENESIS = "0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
MAX_ARCHIVE = 6_000_000
MANIFEST_FIELDS = frozenset((
    "schema","chainId","executionGenesisHash","beaconGenesisValidatorsRoot",
    "originalGenesisArchiveSha256","originalGenesisArchiveSources",
    "replaceablePeerDirectorySources","currentPublicReleaseStatus",
    "noFixedBootstrapPeerOrIp","noMemberAllowlist","noAutomaticGenesisRecreation",
))

class Refused(ValueError):
    pass

def verify_url(value):
    if type(value) is not str or not 10 <= len(value) <= 1024:
        raise Refused("invalid public HTTPS mirror")
    parts=urllib.parse.urlsplit(value)
    if (parts.scheme!="https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.fragment
            or parts.port not in (None,443) or not parts.path or parts.path=="/"):
        raise Refused("only public HTTPS document mirrors allowed")
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise Refused("IP address mirror forbidden")
    if parts.hostname=="localhost" or "." not in parts.hostname:
        raise Refused("public mirror domain required")
    if not re.fullmatch(r"[a-z0-9.-]+",parts.hostname):
        raise Refused("invalid public mirror DNS name")
    return value

def manifest(value):
    if type(value) is not dict or set(value)!=MANIFEST_FIELDS:
        raise Refused("invalid release manifest schema")
    if (value["schema"]!=SCHEMA or type(value["chainId"]) is not int
            or value["chainId"]!=31340
            or value["executionGenesisHash"]!=EL_GENESIS
            or value["beaconGenesisValidatorsRoot"]!=CL_GENESIS
            or value["originalGenesisArchiveSha256"]!=ARCHIVE_SHA
            or value["noFixedBootstrapPeerOrIp"] is not True
            or value["noMemberAllowlist"] is not True
            or value["noAutomaticGenesisRecreation"] is not True):
        raise Refused("chain identity or permissionless release invariants violated")
    for field in ("originalGenesisArchiveSources","replaceablePeerDirectorySources"):
        entries=value[field]
        if (type(entries) is not list or len(entries)>16
                or len(entries)!=len(set(entries))):
            raise Refused("invalid release source list")
        for source in entries:
            verify_url(source)
    status=value["currentPublicReleaseStatus"]
    if status not in ("BLOCKED_UNPUBLISHED_ORIGINAL_GENESIS_AND_DISCOVERY",
                      "PUBLIC_GENESIS_MIRRORED_NATIVE_DISCOVERY_PENDING",
                      "PUBLIC_GENESIS_AND_NATIVE_PEER_HINTS_PUBLISHED"):
        raise Refused("unrecognized public release stage")
    if (not value["originalGenesisArchiveSources"] and
            status!="BLOCKED_UNPUBLISHED_ORIGINAL_GENESIS_AND_DISCOVERY"):
        raise Refused("cannot advertise published genesis without mirrors")
    return value

def read_manifest(path):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=16384:
        raise Refused("unavailable or oversized release manifest")
    try:
        return manifest(json.loads(path.read_text("utf-8")))
    except (ValueError,UnicodeError) as exc:
        raise Refused("malformed release manifest") from exc

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def download(url):
    verify_url(url)
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler(),_NoRedirect())
    try:
        with opener.open(urllib.request.Request(
                url,headers={"Accept":"application/octet-stream"}),timeout=15) as response:
            if response.status!=200 or response.url!=url:
                raise Refused("unexpected artifact response")
            blob=response.read(MAX_ARCHIVE+1)
    except (OSError,ValueError) as exc:
        raise Refused("public archive mirror unreachable") from exc
    if not 0<len(blob)<=MAX_ARCHIVE:
        raise Refused("missing or oversized original chain archive")
    if hashlib.sha256(blob).hexdigest()!=ARCHIVE_SHA:
        raise Refused("original immutable genesis archive SHA256 mismatch")
    return blob

def acquire(release,target,downloader=download):
    data=manifest(release)
    sources=data["originalGenesisArchiveSources"]
    if not sources:
        raise Refused("ORIGINAL_GENESIS_NOT_YET_PUBLICLY_RELEASED")
    target=Path(target)
    if target.exists() or target.is_symlink():
        raise Refused("genesis archive path already exists; no overwrite")
    for source in sources:
        try:
            blob=downloader(source)
            if (type(blob) is not bytes or len(blob)>MAX_ARCHIVE
                    or hashlib.sha256(blob).hexdigest()!=ARCHIVE_SHA):
                raise Refused("original genesis artifact digest mismatch")
        except (Refused,OSError,ValueError,TypeError):
            continue
        # Install only after digest verified, never on a live node's data root.
        target.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(blob)
            out.flush()
            os.fsync(out.fileno())
        return {"schema":"SSE_R149_PUBLIC_GENESIS_ACQUIRED_V1",
                "sha256Verified":True,"bytes":len(blob),
                "chainId":31340,"noGenesisRecreated":True}
    raise Refused("no source supplied verified ORIGINAL chain31340 archive")
