#!/usr/bin/env python3
"""R238: per-node public-information UI, loopback-only until HTTPS proxy approved.

Independent peer-owned GET-only operator console; not an account-creation
or network admission authority. It reads REAL local chain31340 Besu and
Lighthouse native clients with R141, and optionally finalized market V2
lease state with R206/R229. Role choices are operator DECLARATIONS, not
automatic funded/validator/monitor authorization. Never handles passwords,
wallets, signing, raw ETH transactions, Docker socket or validator keys.

--serve starts ONLY a localhost listener. Internet reachability/dynamic IP
and HTTPS/TLS ownership are separately required; no claims that source
deployment alone makes a public dashboard reachable.
"""
from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))

from sse_pos_r141_independent_fleet_audit import (
    Refused as NodeRefused,capture as real_node_capture,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,
)
from sse_pos_r229_v2_finalized_lease_snapshot import (
    Refused as MarketRefused,inspect as finalized_market_lease,
)

ROLES=frozenset((
    "observer","full_node","validator","consumer",
    "provider","monitor","rpc","dashboard","logs"
))
IDENT=re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
LEASE_PATH=re.compile(r"/v2/lease/([1-9][0-9]{0,17})\Z")
MAX_RESPONSE_BYTES=131072


class Refused(ValueError):
    pass


def approved_options(node_id,roles,el,bn,market_manifest=None):
    if type(node_id) is not str or not IDENT.fullmatch(node_id):
        raise Refused("invalid operator-owned node public label")
    if type(roles) is not list or not roles or len(roles)!=len(set(roles)) or any(
        role not in ROLES for role in roles
    ):
        raise Refused("only unique approved locally declared roles supported")
    if el not in ("http://127.0.0.1:18545","http://127.0.0.1:28545") or bn not in (
        "http://127.0.0.1:15052","http://127.0.0.1:25052"
    ) or (el.endswith(":18545") != bn.endswith(":15052")):
        raise Refused("local client RPC/REST port pair not verified for known node")
    if market_manifest is not None and (type(market_manifest) is not Path or
        not market_manifest.is_absolute()):
        raise Refused("public R206 manifest must be an explicit absolute file path")
    return {
        "nodeId":node_id,"declaredRoles":sorted(roles),
        "el":el,"bn":bn,"manifest":market_manifest,
    }


def node_status(config,*,capture=real_node_capture):
    report=capture(config["nodeId"],config["el"],config["bn"])
    # Explicit new truth values are NOT derived from the declared role tags.
    return {
        "schema":"SSE_R238_ROLE_LOCAL_PUBLIC_STATUS_V1",
        "nodeId":config["nodeId"],
        "declaredRoles":config["declaredRoles"],
        "executionAndConsensusLocalObservation":report,
        "marketV2ManifestConfigured":config["manifest"] is not None,
        "marketV2ContractDeploymentVerifiedByThisStatus":False,
        "stakingValidatorActuallyActiveVerified":False,
        "providerPhysicalResourceVerified":False,
        "monitorEligibilityActuallyFundedVerified":False,
        "consumerLeaseActuallyFundedVerified":False,
        "zeroBalanceObserverMayJoinWithoutAWallet":True,
        "remotePublicHttpsReachabilityVerified":False,
        "keysOrWalletsAccessed":False,
        "transactionsSignedOrSubmitted":False,
    }


def status_html(payload):
    # All node IDs/values are escaped, not interpolated into JS or DOM
    # attributes; CSP explicitly disables inline script and active assets.
    chain=payload["executionAndConsensusLocalObservation"]
    name=html.escape(payload["nodeId"],quote=True)
    roles=", ".join(html.escape(x,quote=True) for x in payload["declaredRoles"])
    def field(label,value):
        return "<tr><th>"+html.escape(label)+"</th><td>"+html.escape(str(value))+"</td></tr>"
    rows="".join((
        field("Chain ID",chain["chainId"]),
        field("Execution block",chain["executionBlockNumber"]),
        field("Beacon head slot",chain["beaconHeadSlot"]),
        field("Finalized epoch",chain["finalizedEpoch"]),
        field("Finalized root",chain["finalizedRoot"]),
        field("EL native peers",chain["executionNativePeers"]),
        field("CL native peers",chain["beaconNativePeers"]),
        field("EL syncing",chain["executionSyncing"]),
        field("CL syncing",chain["beaconSyncing"]),
        field("Captured at UTC",chain["capturedAtUtc"]),
    ))
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>SSE node / "+name+"</title></head>"
            "<body><main><h1>SSE / "+name+"</h1>"
            "<p>Declared local roles: "+roles+"</p>"
            "<p>Read-only observed original-chain node health. No operator "
            "admission or global authority; declarations are not on-chain "
            "registrations, physical SLA proof or active validator status.</p>"
            "<table>"+rows+"</table>"
            "<p>Read-only <a href='/v2/status'>raw node status JSON</a>. "
            "Finalized market lease lookup: /v2/lease/{id}, only once a "
            "verified V2 deployment manifest is installed by the operator.</p>"
            "<p>HTTPS reachability, funding, independent operators, real "
            "compute and live SSE transactions are not implied.</p>"
            "</main></body></html>").encode("utf-8")


def lease_status(config,lease_id,*,inspect=finalized_market_lease):
    manifest_path=config["manifest"]
    if manifest_path is None:
        raise Refused("market V2 manifest not configured; deployment not verified")
    manifest=load_manifest(manifest_path)
    # Explicit R206 attestation takes place inside the R229 call, every time
    # this endpoint is used. No absent on-chain V2 data fabricated.
    return inspect(manifest,config["el"],lease_id)


def make_server(config,port=8766,*,capture=real_node_capture,inspect=finalized_market_lease):
    if type(port) is not int or port!=0 and not 1024<=port<=65535:
        raise Refused("only local unprivileged console port (0 for tests)")
    if type(config) is not dict or set(config)!={"nodeId","declaredRoles","el","bn","manifest"}:
        raise Refused("unexpected node role-local configuration")

    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,body,content_type):
            if type(body) is not bytes or len(body)>MAX_RESPONSE_BYTES:
                raise Refused("public response exceeds bound")
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy","no-referrer")
            self.end_headers()
            self.wfile.write(body)
        def json_reply(self,status,data):
            raw=json.dumps(data,sort_keys=True,separators=(",",":"),
                           ensure_ascii=True,allow_nan=False).encode("utf-8")
            return self.reply(status,raw,"application/json; charset=utf-8")
        def do_GET(self):
            try:
                if self.path=="/healthz":
                    return self.json_reply(200,{
                        "schema":"SSE_R238_LOOPBACK_PROCESS_HEALTH_V1",
                        "alive":True,"chainVerifiedByHealthz":False,
                        "transactionsSubmitted":False})
                if self.path in ("/","/v2/status"):
                    status=node_status(config,capture=capture)
                    if self.path=="/":
                        return self.reply(200,status_html(status),
                                          "text/html; charset=utf-8")
                    return self.json_reply(200,status)
                match=LEASE_PATH.fullmatch(self.path)
                if match:
                    return self.json_reply(200,lease_status(
                        config,int(match.group(1)),inspect=inspect))
                return self.json_reply(404,{"error":"unknown read-only route"})
            except (Refused,NodeRefused,MarketRefused,AuditRefused,OSError,
                    ValueError,TypeError,KeyError,OverflowError):
                return self.json_reply(503,{
                    "error":"real original-chain or finalized market evidence unavailable",
                    "fabricatedServiceStatus":False})
        def do_POST(self):
            return self.json_reply(405,{"error":"read-only console never signs or changes roles"})
        def log_message(self,*args):
            return

    return ThreadingHTTPServer(("127.0.0.1",port),Handler)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id",required=True)
    p.add_argument("--roles",default="observer",help="comma-separated declared local roles, not activation")
    p.add_argument("--el",required=True)
    p.add_argument("--bn",required=True)
    p.add_argument("--v2-manifest",type=Path)
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--serve",action="store_true",
                   help="start owner-local read-only HTTP; TLS proxy is separate")
    a=p.parse_args(argv)
    try:
        conf=approved_options(a.node_id,a.roles.split(","),a.el,a.bn,a.v2_manifest)
        if not a.serve:
            print(json.dumps({
                "schema":"SSE_R238_PUBLIC_NODE_CONSOLE_SOURCE_PLAN_V1",
                "config":{"nodeId":conf["nodeId"],"declaredRoles":conf["declaredRoles"],
                          "el":conf["el"],"bn":conf["bn"],
                          "v2ManifestConfigured":conf["manifest"] is not None},
                "httpServerStarted":False,
                "publicInternetHttpsVerified":False,
                "nodeOrValidatorChanged":False,"transactionSubmitted":False,
            },sort_keys=True,indent=2))
            return 0
        if not 1024<=a.port<=65535:
            raise Refused("--serve requires explicit owner-local unprivileged port")
        server=make_server(conf,a.port)
        print("R238_ROLE_LOCAL_PUBLIC_STATUS_HTTP_LOOPBACK_READY=true",flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    except (Refused,NodeRefused,AuditRefused,MarketRefused,
            ValueError,TypeError,OSError) as exc:
        print("R238_ROLE_LOCAL_STATUS_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
