#!/usr/bin/env python3
"""Collect and validate four PUBLIC Ubuntu validator host reports.

Each host executes 'collect' itself after a pinned Git checkout and local
validator key ceremony. Operator obtains reports through separately pinned
SSH channels and uses 'audit' to reject accidental VM clones/collisions.
No credential, private key, Tailscale auth key, Ethereum tx, or destructive
operation is accessed. Reports are NOT cryptographic remote attestation.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from eth_keys import keys

from sse_qbft_validator_identity import inspect_local, IdentityError
from sse_qbft_network_assembly import (validate_roster, AssemblyError, PUBLIC_FIELDS)
from sse_network_peers import validate_enode, PeerCatalogError

SCHEMA="SSE_QBFT_HOST_REPORT_V1"
SHA=re.compile(r"[0-9a-f]{40}\Z")
SSHFP=re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
MAXAGE=4*3600
MAXSIZE=16384
FIELDS={"schema","nodeId","gitCommit","collectedAt","hostName",
        "sshEd25519Fingerprint","tailscaleStableId","tailscaleDnsName",
        "overlayIPv4","validatorPublic","privateKeysIncluded",
        "operatorIdentityIndependenceProved","networkStarted"}


class FleetError(ValueError):
    pass


def _command(args):
    try:
        result=subprocess.run(args,text=True,capture_output=True,
                              check=True,timeout=10)
    except (OSError,subprocess.SubprocessError):
        raise FleetError("local command unavailable: "+args[0]) from None
    return result.stdout.strip()


def ssh_public_fingerprint(public_text: str) -> str:
    if type(public_text) is not str or len(public_text)>2048:
        raise FleetError("invalid SSH host public key")
    parts=public_text.strip().split()
    if len(parts)<2 or parts[0]!="ssh-ed25519":
        raise FleetError("SSH host key must be ed25519")
    try:
        raw=base64.b64decode(parts[1],validate=True)
    except (ValueError,binascii.Error):
        raise FleetError("unparseable SSH host key") from None
    if (len(raw)!=51 or int.from_bytes(raw[:4],"big")!=11
            or raw[4:15]!=b"ssh-ed25519"
            or int.from_bytes(raw[15:19],"big")!=32):
        raise FleetError("invalid SSH ed25519 wire encoding")
    return "SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")


def _git_rev():
    revision=_command(["git","rev-parse","HEAD"])
    if not SHA.fullmatch(revision):
        raise FleetError("Git checkout revision invalid")
    if _command(["git","status","--porcelain","--untracked-files=no"]):
        raise FleetError("tracked source files modified locally")
    return revision


def collect(*, private_dir:Path, public_file:Path, expected_commit:str,
            ssh_host_public_file:Path=Path("/etc/ssh/ssh_host_ed25519_key.pub"),
            run=_command, now:int|None=None, linux_only=True) -> dict:
    if linux_only and (platform.system()!="Linux" or os.geteuid()==0):
        raise FleetError("collect on Ubuntu as owning NONROOT validator account")
    if type(expected_commit) is not str or not SHA.fullmatch(expected_commit):
        raise FleetError("expected immutable reviewed Git commit is required")
    local_revision=_git_rev() if run is _command else run(["git","rev-parse","HEAD"])
    if local_revision!=expected_commit:
        raise FleetError("node checkout is not approved Git revision")
    identity=inspect_local(private_dir,public_file=public_file)
    try:
        st=json.loads(run(["tailscale","status","--json"]))
        own=st["Self"]
        if (st["BackendState"]!="Running" or own["Online"] is not True
                or identity["overlayIPv4"] not in own["TailscaleIPs"]):
            raise FleetError("Tailscale overlay not active at approved node IP")
        stable=own.get("StableID") or own.get("ID")
        dns=own.get("DNSName")
        if (type(stable) is not str or not 2<=len(stable)<=128
                or type(dns) is not str or not dns.endswith(".ts.net.")):
            raise FleetError("Tailscale identity or MagicDNS absent")
        if (not ssh_host_public_file.is_file()
                or ssh_host_public_file.is_symlink()
                or ssh_host_public_file.stat().st_size>2048):
            raise FleetError("missing normal SSH host PUBLIC key")
        fingerprint=ssh_public_fingerprint(ssh_host_public_file.read_text("ascii"))
    except (OSError,KeyError,TypeError,ValueError,UnicodeError):
        raise FleetError("invalid local Tailscale/SSH public identity") from None
    return {
        "schema":SCHEMA,"nodeId":identity["nodeId"],
        "gitCommit":expected_commit,
        "collectedAt":int(time.time()) if now is None else now,
        "hostName":platform.node(),
        "sshEd25519Fingerprint":fingerprint,
        "tailscaleStableId":stable,
        "tailscaleDnsName":dns.lower(),
        "overlayIPv4":identity["overlayIPv4"],
        "validatorPublic":identity,
        "privateKeysIncluded":False,
        "operatorIdentityIndependenceProved":False,
        "networkStarted":False,
    }


def validate_public_report(doc:dict, *, revision:str, now:int) -> dict:
    if type(doc) is not dict or set(doc)!=FIELDS or doc.get("schema")!=SCHEMA:
        raise FleetError("unknown host report fields")
    if type(doc["gitCommit"]) is not str or doc["gitCommit"]!=revision:
        raise FleetError("mixed source revisions in fleet")
    t=doc["collectedAt"]
    if type(t) is not int or not 0<=now-t<=MAXAGE:
        raise FleetError("stale or future-dated VM report")
    for field in ("nodeId","hostName","tailscaleStableId","tailscaleDnsName",
                  "overlayIPv4","sshEd25519Fingerprint"):
        v=doc[field]
        if type(v) is not str or not 1<=len(v)<=255:
            raise FleetError("invalid public field "+field)
    if not SSHFP.fullmatch(doc["sshEd25519Fingerprint"]):
        raise FleetError("invalid SSH host key fingerprint")
    if not doc["tailscaleDnsName"].endswith(".ts.net."):
        raise FleetError("not an approved Tailscale FQDN")
    if (doc["privateKeysIncluded"] is not False
            or doc["networkStarted"] is not False
            or doc["operatorIdentityIndependenceProved"] is not False):
        raise FleetError("public pre-start host report attestation mismatch")
    identity=doc["validatorPublic"]
    if (type(identity) is not dict or set(identity)!=PUBLIC_FIELDS
            or identity.get("nodeId")!=doc["nodeId"]
            or identity.get("schema")!="SSE_QBFT_PUBLIC_VALIDATOR_V1"
            or type(identity.get("chainId")) is not int
            or identity["chainId"]!=31338
            or identity.get("privateKeyIncluded") is not False
            or identity.get("chainParticipationStarted") is not False
            or identity.get("physicalIndependenceProved") is not False):
        raise FleetError("node role/public key does not match host")
    if identity.get("overlayIPv4")!=doc["overlayIPv4"]:
        raise FleetError("overlay IP differs from attested P2P locator")
    pub=identity.get("enodePublicKey")
    try:
        if type(pub) is not str or len(pub)!=128:
            raise FleetError("wrong enode public key length")
        derived=keys.PublicKey(bytes.fromhex(pub)).to_checksum_address().lower()
        key, host, port=validate_enode(identity.get("enode"))
        if (derived!=identity.get("validatorAddress")
                or key!=pub or host!=identity["overlayIPv4"] or port!=30303):
            raise FleetError("invalid validator public address or P2P key binding")
    except (ValueError,TypeError,PeerCatalogError):
        raise FleetError("invalid node public key binding") from None
    return identity


def audit(reports:list[dict], *, revision:str, now:int|None=None) ->dict:
    if len(reports)!=4 or type(revision) is not str or not SHA.fullmatch(revision):
        raise FleetError("four reports and one exact source revision required")
    now=int(time.time()) if now is None else now
    identities=[validate_public_report(r,revision=revision,now=now) for r in reports]
    try:
        validate_roster(identities)
    except AssemblyError:
        raise FleetError("duplicated validator/node/overlay identity") from None
    unique_fields=("sshEd25519Fingerprint","tailscaleStableId","tailscaleDnsName")
    for field in unique_fields:
        if len({r[field].lower() for r in reports})!=4:
            raise FleetError("duplicate "+field+" suggests cloned or reused VM identity")
    names=[r["hostName"] for r in reports]
    return {
        "kind":"SSE_QBFT_FOUR_HOST_PUBLIC_IDENTITY_GATE_V1",
        "gitCommit":revision,
        "reportCount":4,
        "uniqueValidatorKeys":4,
        "uniqueOverlayAddresses":4,
        "uniqueTailscaleDeviceIDs":4,
        "uniqueSSHHostKeys":4,
        "hostNamesAllDistinct":len(set(names))==4,
        "nodeIds":sorted(r["nodeId"] for r in reports),
        "physicalIndependenceCryptographicallyProved":False,
        "operatorIndependentAuditsStillRequired":True,
        "networkStarted":False,
        "transactionsSent":False,
    }


def _write_new(path:Path, doc:dict):
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise FleetError("output must be a new file in an existing directory")
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
               (os.O_NOFOLLOW if hasattr(os,"O_NOFOLLOW") else 0),0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(doc,f,indent=2,sort_keys=True)
        f.write("\n")


def main(argv=None):
    p=argparse.ArgumentParser(description="Ubuntu public validator identity collection and fleet audit")
    sub=p.add_subparsers(dest="action",required=True)
    c=sub.add_parser("collect")
    c.add_argument("--private-dir",required=True,type=Path)
    c.add_argument("--public-file",required=True,type=Path)
    c.add_argument("--expected-commit",required=True)
    c.add_argument("--output",required=True,type=Path)
    a=sub.add_parser("audit")
    a.add_argument("--report",action="append",required=True,type=Path)
    a.add_argument("--expected-commit",required=True)
    a.add_argument("--output",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        if args.action=="collect":
            result=collect(private_dir=args.private_dir,public_file=args.public_file,
                           expected_commit=args.expected_commit)
        else:
            if len(args.report)!=4:
                raise FleetError("audit requires exactly four host reports")
            docs=[]
            for file in args.report:
                if file.is_symlink() or not file.is_file() or file.stat().st_size>MAXSIZE:
                    raise FleetError("unsafe host report")
                docs.append(json.loads(file.read_text("utf-8")))
            result=audit(docs,revision=args.expected_commit)
        _write_new(args.output,result)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (FleetError,IdentityError,OSError,ValueError,TypeError,KeyError) as exc:
        print("SSE_QBFT_FLEET_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
