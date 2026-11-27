#!/usr/bin/env python3
"""R232: real HTTP(S) monitor-side V2 observed provider response.

Uses finalized R206/R229 lease provenance; checks selected+confirmed EOA
membership and the lease-committed HTTPS origin; issues a bounded REAL HTTP
request and validates V2 provider EIP-712 attribution and CPU reply. Always
records observed transport/latency as conditional evidence only. No SLA
Failure/Success vote is automatically inferred, signed or broadcast.
No wallet or Docker daemon access. No proxy/redirect, no remote cleartext.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import ipaddress
import ssl
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from urllib.request import Request,HTTPRedirectHandler,ProxyHandler,HTTPSHandler,build_opener

from sse_challenge import keccak256
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,rpc,
)
from sse_pos_r229_v2_finalized_lease_snapshot import (
    Refused as SnapshotRefused, inspect as inspect_lease, query as eth_call,
    decode_struct as decode_state,
)
from sse_pos_r228_v2_typed_data import evidence_commitment,checked_addr
from sse_pos_r231_v2_compute_wire import (
    Refused as WireRefused,validate_signed_reply,
)

MAX_REQUEST_BYTES=1024
MAX_REPLY_BYTES=8192
FQDN=re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\Z")


class Refused(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def canonical_origin(origin):
    if type(origin) is not str or len(origin)>253 or not origin.isascii():
        raise Refused("expected bounded ASCII HTTPS origin")
    u=urlsplit(origin)
    try:
        port=u.port
    except ValueError as exc:
        raise Refused("bad endpoint port") from exc
    if (u.username or u.password or u.query or u.fragment or
        u.path not in ("","/") or u.hostname is None or
        port is not None and not 1<=port<=65535):
        raise Refused("invalid provider root URL")
    host=u.hostname
    if ":" in host:
        try:
            ip=ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise Refused("invalid overlay IPv6 origin") from exc
        if (ip not in ipaddress.IPv6Network("fca0::/16") or
            u.scheme!="https" or port is None or
            origin!=f"https://[{ip}]:{port}"):
            raise Refused("expected canonical authenticated overlay HTTPS origin")
    elif origin!=origin.lower() or not FQDN.fullmatch(host):
        raise Refused("noncanonical provider hostname")
    if u.scheme=="http":
        if host!="127.0.0.1" or port is None:
            raise Refused("remote HTTP forbidden; HTTPS mandatory")
    elif u.scheme!="https":
        raise Refused("expected HTTPS or local development loopback")
    if origin.endswith("/"):
        raise Refused("origin must omit trailing slash")
    # URL is a public, publisher-committed origin. DNS mobility is allowed.
    # TLS authentication is separately verified by the system trust store.
    return origin


def prepared_monitor(snapshot,monitor,origin,*,transport=rpc,rpc_url=None,allow_canonical=False):
    monitor=checked_addr(monitor)
    origin=canonical_origin(origin)
    provisional=(type(snapshot) is dict and
                 snapshot.get("schema")=="SSE_R350_CANONICAL_V2_LEASE_READONLY_V1" and
                 snapshot.get("finalizedAuthorization") is False and
                 snapshot.get("reorganizationPossible") is True)
    if (type(snapshot) is not dict or
        (snapshot.get("schema")!="SSE_R229_FINALIZED_V2_LEASE_READONLY_V1" and
         not (allow_canonical is True and provisional)) or
        snapshot.get("deploymentRuntimeAndWiringAttested") is not True):
        raise Refused("no verified canonical deployment/lease evidence")
    if (snapshot.get("epoch") is None or
        snapshot["epoch"]["market"]["exists"] is not True or
        snapshot["epoch"]["ledger"]["exists"] is not True or
        snapshot["lease"]["providerAccepted"] is not True or
        snapshot["lease"]["phase"]!=4 or
        snapshot["committee"]["ready"] is not True or
        snapshot["epoch"]["ledger"]["monitoringSealed"] is True):
        raise Refused("live monitor epoch not active at verified finalized state")
    if monitor not in snapshot["selectedMonitors"]:
        raise Refused("monitor not selected in actual V2 committee")
    committed="0x"+keccak256(origin.encode("ascii")).hex()
    if snapshot["lease"]["endpointHash"]!=committed:
        raise Refused("real lease endpoint commitment not equal to canonical origin")
    height=snapshot["observedExecutionHeight"] if provisional else snapshot["finalizedExecutionHeight"]
    if provisional and rpc_url is None:
        raise Refused("canonical membership requires live RPC anchor verification")
    if rpc_url is not None:
        if rpc_url not in ("http://127.0.0.1:18545","http://127.0.0.1:28545"):
            raise Refused("unreviewed localhost RPC")
        raw=eth_call(transport,rpc_url,snapshot["ledger"],
                     "confirmedMonitor(uint256,address)",(
                         snapshot["leaseId"],int(monitor,16)),
                     height)
        confirmed=decode_state(raw,(("confirmed","bool"),))["confirmed"]
        if not confirmed:
            raise Refused("real monitor did not confirm selected seat")
        if provisional:
            from sse_pos_r350_v2_canonical_lease_snapshot import block_identity
            if block_identity(transport(rpc_url,"eth_getBlockByNumber",[hex(height),False]))!=(height,snapshot["observedExecutionHash"]):
                raise Refused("canonical membership anchor reorganized")
    return {
        "leaseId":snapshot["leaseId"],"epochId":snapshot["epochId"],
        "requestHash":snapshot["epoch"]["market"]["requestHash"],
        "monitor":monitor,"provider":snapshot["lease"]["provider"],
        "origin":origin,
        **({"observedExecutionHeight":height,"observedExecutionHash":snapshot["observedExecutionHash"]} if provisional else {"finalizedExecutionHeight":height}),
        "selectedMonitorAtFinalized":not provisional,
        "confirmedMonitorAtFinalized":rpc_url is not None and not provisional,
        "confirmedMonitorAtCanonical":provisional,
    }


def _unique_pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise Refused("duplicate provider JSON field")
        out[k]=v
    return out


def pinned_tls_context(certificate,fingerprint):
    if type(fingerprint) is not str or not re.fullmatch(r"[0-9a-f]{64}",fingerprint):
        raise Refused("expected public DER SHA256 fingerprint")
    pem=Path(certificate).read_text("ascii")
    der=ssl.PEM_cert_to_DER_cert(pem)
    if hashlib.sha256(der).hexdigest()!=fingerprint:
        raise Refused("provider certificate fingerprint mismatch")
    ctx=ssl.create_default_context(cadata=pem)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    return ctx


def http_probe(origin,payload,timeout_seconds=5,*,opener=None,tls_context=None):
    canonical_origin(origin)
    if type(timeout_seconds) not in (int,float) or not 0<timeout_seconds<=30:
        raise Refused("probe timeout must be in (0,30]")
    raw_request=json.dumps(payload,sort_keys=True,separators=(",",":"),
                           allow_nan=False).encode("ascii")
    if len(raw_request)>MAX_REQUEST_BYTES:
        raise Refused("request too large")
    if opener is None:
        opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=tls_context))
    req=Request(origin+"/v2/challenge",data=raw_request,method="POST",
                headers={"Content-Type":"application/json","Accept":"application/json"})
    started=time.monotonic_ns()
    try:
        with opener.open(req,timeout=timeout_seconds) as response:
            status=response.status
            content_length=response.headers.get("Content-Length")
            if content_length is not None:
                if not content_length.isdecimal() or int(content_length)>MAX_REPLY_BYTES:
                    raise Refused("HTTP body length outside safe bounds")
            raw=response.read(MAX_REPLY_BYTES+1)
            if len(raw)>MAX_REPLY_BYTES:
                raise Refused("oversized HTTP body")
            if content_length is not None and len(raw)!=int(content_length):
                raise Refused("truncated HTTP response")
    except (HTTPError,URLError,OSError,TimeoutError) as exc:
        elapsed=max(0,(time.monotonic_ns()-started)//1_000_000)
        return {"transportStatus":"UNAVAILABLE_OR_ERROR","httpStatus":None,
                "elapsedMs":elapsed,"body":None,
                "reason":type(exc).__name__}
    elapsed=max(0,(time.monotonic_ns()-started)//1_000_000)
    return {"transportStatus":"HTTP_RESPONSE_OBSERVED","httpStatus":status,
            "elapsedMs":elapsed,"body":raw,"reason":None}


def inspect_response(observation,snapshot,prepared,*,allow_canonical=False):
    if observation["body"] is None:
        return {
            "schema":"SSE_R232_REAL_PROBE_OBSERVATION_V1",
            "leaseId":prepared["leaseId"],"epochId":prepared["epochId"],
            "monitor":prepared["monitor"],"origin":prepared["origin"],
            "transportStatus":observation["transportStatus"],
            "elapsedMs":observation["elapsedMs"],
            "providerSignatureVerified":False,
            "provisionalOnly":True,"onChainVoteOrFailureVerdict":False,
            "physicalSlaTruthVerified":False,
        }
    raw=observation["body"]
    if observation["httpStatus"]!=200:
        raise Refused("provider HTTP result not successful; no success vote")
    try:
        body=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique_pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(Refused("nonfinite")))
    except (UnicodeDecodeError,ValueError,TypeError) as exc:
        raise Refused("invalid bounded provider reply") from exc
    actual=validate_signed_reply(body,snapshot,allow_canonical=True) if allow_canonical else validate_signed_reply(body,snapshot)
    if actual["responseHash"]!=body["responseHash"]:
        raise Refused("signed response message changed")
    now=datetime.now(timezone.utc).isoformat()
    raw_digest=hashlib.sha256(raw).hexdigest()
    observed_record={
        "observedAtUtc":now,"origin":prepared["origin"],
        "leaseId":prepared["leaseId"],"epochId":prepared["epochId"],
        "httpStatus":observation["httpStatus"],
        "elapsedMs":observation["elapsedMs"],
        "responseBodySha256":raw_digest,
        "providerPublicSignatureVerified":True,
    }
    observation_digest=hashlib.sha256(json.dumps(
        observed_record,sort_keys=True,separators=(",",":"),
        ensure_ascii=True,allow_nan=False).encode("ascii")).hexdigest()
    evidence={
        "leaseId":prepared["leaseId"],"epochId":prepared["epochId"],
        "monitor":prepared["monitor"],"observedAtUtc":now,
        "endpoint":prepared["origin"],"method":"POST",
        "responseSha256":raw_digest,"rawObservationSha256":observation_digest,
        "latencyMs":observation["elapsedMs"],"httpStatus":200,
        "source":"R232_REAL_HTTP_POST_AND_V2_PROVIDER_SIGNATURE",
    }
    commitment=evidence_commitment(evidence)
    return {
        "schema":"SSE_R232_REAL_PROBE_OBSERVATION_V1",
        "leaseId":prepared["leaseId"],"epochId":prepared["epochId"],
        "monitor":prepared["monitor"],"origin":prepared["origin"],
        "transportStatus":observation["transportStatus"],
        "elapsedMs":observation["elapsedMs"],
        "signedResponseHash":actual["responseHash"],
        "rawHttpBodySha256":raw_digest,
        "rawObservation":observed_record,
        "rawObservationSha256":observation_digest,
        "provisionalMonitorEvidenceHash":commitment,
        "providerSignatureVerified":True,
        "realFinalizedLeaseScopeVerified":snapshot.get("schema")=="SSE_R229_FINALIZED_V2_LEASE_READONLY_V1",
        "provisionalCanonicalScopeVerified":snapshot.get("schema")=="SSE_R350_CANONICAL_V2_LEASE_READONLY_V1",
        "provisionalOnly":True,"onChainVoteOrFailureVerdict":False,
        "physicalSlaTruthVerified":False,
        "localClockAttested":False,
        "independentMonitorOperatorVerified":False,
    }


def write_bytes_create_only(output,data):
    if type(data) is not bytes or not 0<len(data)<=65536:
        raise Refused("invalid bounded evidence bytes")
    path=Path(output)
    if not path.is_absolute() or path.is_symlink() or path.exists() or ".." in path.parts:
        raise Refused("evidence path must be new absolute non-symlink file")
    parent=path.parent
    if (not parent.is_dir() or parent.is_symlink() or
        parent.stat().st_mode & 0o022):
        raise Refused("evidence directory must exist and not be writable by others")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def write_create_only(output,report):
    raw=(json.dumps(report,sort_keys=True,indent=2)+"\n").encode("utf-8")
    return write_bytes_create_only(output,raw)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--lease-id",type=int,required=True)
    p.add_argument("--epoch-id",type=int,required=True)
    p.add_argument("--monitor",required=True)
    p.add_argument("--origin",required=True)
    p.add_argument("--timeout",type=float,default=5)
    p.add_argument("--tls-cert",type=Path)
    p.add_argument("--tls-fingerprint")
    p.add_argument("--probe",action="store_true",
                   help="make ONE real provider HTTP request; no blockchain write")
    p.add_argument("--output",help="create-once private evidence JSON for --probe")
    p.add_argument("--raw-response-output",help="optional create-once private verbatim signed HTTP reply")
    a=p.parse_args(argv)
    try:
        if bool(a.tls_cert)!=bool(a.tls_fingerprint):
            raise Refused("both public certificate and fingerprint required")
        tls_context=pinned_tls_context(a.tls_cert,a.tls_fingerprint) if a.tls_cert else None
        if (a.output or a.raw_response_output) and not a.probe:
            raise Refused("evidence archival requires explicit --probe")
        snapshot=inspect_lease(load_manifest(a.manifest),a.rpc,
                               a.lease_id,a.epoch_id)
        context=prepared_monitor(snapshot,a.monitor,a.origin,
                                 rpc_url=a.rpc)
        if not a.probe:
            print(json.dumps({
                "schema":"SSE_R232_READONLY_MONITOR_PROBE_PLAN",
                **context,"remoteProviderContacted":False,
                "transactionSignedOrSubmitted":False,
                "physicalIndependenceVerified":False,
            },indent=2,sort_keys=True))
            return 0
        payload={k:context[k] for k in ("leaseId","epochId","requestHash")}
        observation=http_probe(context["origin"],payload,a.timeout,tls_context=tls_context)
        result=inspect_response(observation,snapshot,context)
        if a.raw_response_output:
            if observation["body"] is None:
                raise Refused("cannot archive missing HTTP response")
            write_bytes_create_only(a.raw_response_output,observation["body"])
        if a.output:
            write_create_only(a.output,result)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (Refused,AuditRefused,SnapshotRefused,WireRefused,OSError,
            ValueError,KeyError,TypeError,OverflowError) as exc:
        print("R232_REAL_V2_MONITOR_PROBE_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
