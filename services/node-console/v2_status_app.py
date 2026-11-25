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
import base64
import hashlib
import html
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))

from sse_pos_r141_independent_fleet_audit import (
    Refused as NodeRefused,capture as real_node_capture,
)
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused,load as load_manifest,verify as verify_market,rpc,
)
from sse_pos_r229_v2_finalized_lease_snapshot import (
    Refused as MarketRefused,inspect as finalized_market_lease,query,decode_struct,
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
    if el not in ("http://127.0.0.1:18545","http://127.0.0.1:28545") or bn not in (None,
        "http://127.0.0.1:15052","http://127.0.0.1:25052"
    ) or (bn is not None and el.endswith(":18545") != bn.endswith(":15052")):
        raise Refused("local client RPC/REST port pair not verified for known node")
    if bn is None and (set(roles).intersection({"observer","full_node","validator"}) or market_manifest is None):
        raise Refused("RPC-only console requires application roles and a deployment manifest")
    if market_manifest is not None and (not isinstance(market_manifest, Path) or
        not market_manifest.is_absolute()):
        raise Refused("public R206 manifest must be an explicit absolute file path")
    return {
        "nodeId":node_id,"declaredRoles":sorted(roles),
        "el":el,"bn":bn,"manifest":market_manifest,
    }


def monitor_account(config,proof,transport):
    address=config.get("monitorAddress")
    if address is None:
        return None
    height=proof["finalizedExecutionHeight"]
    market=proof["contracts"]["market"]["address"]
    ledger=proof["contracts"]["ledger"]["address"]
    account=int(address,16)
    def call(contract,signature,fields):
        return decode_struct(query(transport,config["el"],contract,signature,[account],height),fields)
    record=call(market,"monitors(address)",(("bondWei","uint256"),("lockedAssignments","uint256"),("active","bool")))
    balance=transport(config["el"],"eth_getBalance",[address,hex(height)])
    if not isinstance(balance,str) or not re.fullmatch(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)",balance):
        raise Refused("malformed finalized account balance")
    return {"address":address,"finalizedExecutionHeight":height,"active":record["active"],
            "bondWei":str(record["bondWei"]),"lockedAssignments":str(record["lockedAssignments"]),
            "balanceWei":str(int(balance,16)),
            "marketWithdrawableWei":str(call(market,"withdrawable(address)",(("amount","uint256"),))["amount"]),
            "ledgerWithdrawableWei":str(call(ledger,"withdrawable(address)",(("amount","uint256"),))["amount"]),
            "walletOwnershipVerified":False}


def node_status(config,*,capture=real_node_capture,audit=verify_market,transport=rpc):
    if config["bn"] is None:
        manifest=load_manifest(config["manifest"])
        verified=audit(manifest,config["el"],transport=transport)
        head=transport(config["el"],"eth_getBlockByNumber",["latest",False])
        final=transport(config["el"],"eth_getBlockByNumber",["finalized",False])
        height=int(final["number"],16)
        latest=int(head["number"],16)
        lag=int(head["timestamp"],16)-int(final["timestamp"],16)
        if height<verified["finalizedExecutionHeight"] or latest<height or lag<0:
            raise Refused("inconsistent RPC head/finality")
        return {"schema":"SSE_R314_APPLICATION_RPC_STATUS_V1",
                "nodeId":config["nodeId"],"declaredRoles":config["declaredRoles"],
                "chainId":verified["chainId"],"executionBlockNumber":latest,
                "finalizedExecutionHeight":height,"finalityLagSeconds":lag,
                "deploymentAudit":verified,
                "monitorAccount":monitor_account(config,verified,transport),
                "independentLocalConsensusVerified":False,
                "roleActivationVerified":False,"transactionsSignedOrSubmitted":False}
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


DASHBOARD_CSS="""*{box-sizing:border-box}body{margin:0;background:#0c1424;color:#e7edf7;font:15px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:32px 24px 56px}header{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;border-bottom:1px solid #28364b;padding-bottom:20px}h1,h2,p{margin:0}h1{font-size:32px;letter-spacing:-1px}h2{font-size:19px;margin-bottom:12px}.brand{color:#5eead4;font-size:12px;font-weight:700;letter-spacing:2px}.muted{color:#aabbd1}.tag{background:#20374a;color:#b9e7ee;border-radius:6px;padding:6px 12px}a{color:#5eead4;text-decoration:none}a:hover{text-decoration:underline}.intro{margin:28px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric,.panel{background:#142136;border:1px solid #28364b;border-radius:12px;padding:20px}.metric span{display:block;color:#aabbd1;font-size:13px}.metric strong{font-size:28px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.panel{margin-top:16px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 0;border-bottom:1px solid #28364b;vertical-align:top;overflow-wrap:anywhere}th{color:#aabbd1;font-weight:500;width:40%}td{font-variant-numeric:tabular-nums}.good{color:#5eead4}.caution{color:#f5cc80}.notice{border-left:3px solid #f5cc80;padding-left:14px;margin:16px 0;color:#f5cc80}footer{margin-top:24px;color:#aabbd1;font-size:13px} @media(max-width:550px){main{padding:20px 14px}.metric,.panel{padding:14px}h1{font-size:25px}th{width:36%}}"""
DASHBOARD_STYLE_HASH=base64.b64encode(hashlib.sha256(DASHBOARD_CSS.encode("utf-8")).digest()).decode("ascii")


def status_html(payload,public_readonly=False):
    esc=lambda x:html.escape(str(x),quote=True)
    def field(label,value):
        return "<tr><th>"+esc(label)+"</th><td>"+esc(value)+"</td></tr>"
    def metric(label,value):
        return "<div class='metric'><span>"+esc(label)+"</span><strong>"+esc(value)+"</strong></div>"
    def check(label,value):
        return field(label,"Verified" if value is True else "Not verified")
    name=esc(payload["nodeId"])
    roles=", ".join(payload["declaredRoles"])
    app=payload["schema"]=="SSE_R314_APPLICATION_RPC_STATUS_V1"
    if app:
        audit=payload["deploymentAudit"]
        metrics=(("Chain ID",payload["chainId"]),("Execution head",payload["executionBlockNumber"]),
                 ("Finalized block",payload["finalizedExecutionHeight"]),("Finality timestamp gap (s)",payload["finalityLagSeconds"]))
        rows="".join(check(label,audit.get(key)) for label,key in (
            ("Original genesis","originalGenesisVerified"),("Contract runtime code","runtimeCodeSha256Verified"),
            ("Market / ledger bindings","mutualMarketLedgerBindingsVerified"),
            ("Deployment receipt finalized","deploymentReceiptSuccessfulAndFinalized")))
        for key in ("market","ledger"):
            contract=audit.get("contracts",{}).get(key,{})
            rows+=field(key.title()+" contract",contract.get("address","Not available"))
        detail="Verified deployment via configured RPC. Not independent consensus verification or role activation."
        scope="Application RPC observation"
        checks=check("Independent local consensus",payload.get("independentLocalConsensusVerified"))+check("Role activation",payload.get("roleActivationVerified"))+check("Physical SLA",audit.get("independentPhysicalSlaVerified"))
    else:
        chain=payload["executionAndConsensusLocalObservation"]
        metrics=(("Chain ID",chain["chainId"]),("Execution block",chain["executionBlockNumber"]),
                 ("Beacon head slot",chain["beaconHeadSlot"]),("Finalized epoch",chain["finalizedEpoch"]))
        rows="".join(field(label,chain[key]) for label,key in (
            ("Finalized root","finalizedRoot"),("EL native peers","executionNativePeers"),("CL native peers","beaconNativePeers"),
            ("EL syncing","executionSyncing"),("CL syncing","beaconSyncing"),("Captured at UTC","capturedAtUtc")))
        detail="Read-only observed original-chain node health. Declarations are not on-chain registrations or active validator status."
        scope="Local execution and consensus observation"
        checks=check("Active validator",payload.get("stakingValidatorActuallyActiveVerified"))+check("Physical resources",payload.get("providerPhysicalResourceVerified"))+check("Monitor eligibility",payload.get("monitorEligibilityActuallyFundedVerified"))+check("Consumer lease funding",payload.get("consumerLeaseActuallyFundedVerified"))
    account=payload.get("monitorAccount")
    account_panel=""
    if account is not None:
        account_rows="".join(field(label,account[key]) for label,key in (("Public account","address"),("Observed finalized block","finalizedExecutionHeight"),("On-chain active registration","active"),("Native balance (wei)","balanceWei"),("Bond (wei)","bondWei"),("Locked assignments","lockedAssignments"),("Market withdrawable (wei)","marketWithdrawableWei"),("Ledger withdrawable (wei)","ledgerWithdrawableWei")))
        account_panel="<section class='panel'><h2>Monitor account</h2><table>"+account_rows+"</table><p class='muted'>Public address observation only; wallet ownership and committee selection are not established.</p></section>"
    cards="".join(metric(label,value) for label,value in metrics)
    lease_note=("Lease lookups disabled on this public listener." if public_readonly else
                "Finalized lease lookup: /v2/lease/{id} requires a verified deployment manifest.")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>SSE Intercloud / "+name+"</title><style>"+DASHBOARD_CSS+"</style></head><body><main>"
            "<header><div><div class='brand'>SSE INTERCLOUD</div><h1>"+name+"</h1><p class='muted'>"+esc(scope)+"</p></div>"
            "<span class='tag'>Read-only / TEST ETH</span></header><section class='intro'><h2>Network overview</h2>"
            "<p class='muted'>"+esc(detail)+"</p></section><div class='grid'>"+cards+"</div>"
            "<section class='panel'><h2>Selected roles</h2><p>"+esc(roles)+"</p><table>"+checks+"</table>"
            "<p class='notice'>Declared roles do not establish authorization, eligibility or completed work.</p></section>"
            +account_panel+"<section class='panel'><h2>Blockchain evidence</h2><table>"+rows+"</table></section>"
            "<section class='panel'><h2>Public data</h2><p><a href='/'>Refresh observation</a> &middot; <a href='/v2/status'>Live JSON</a></p>"
            "<p class='muted'>"+esc(lease_note)+" Successful observations may be cached for 15 seconds.</p></section>"
            "<footer>No wallet keys, transaction signing or privileged host controls exposed by this console.</footer></main></body></html>").encode("utf-8")


def lease_status(config,lease_id,*,inspect=finalized_market_lease):
    manifest_path=config["manifest"]
    if manifest_path is None:
        raise Refused("market V2 manifest not configured; deployment not verified")
    manifest=load_manifest(manifest_path)
    # Explicit R206 attestation takes place inside the R229 call, every time
    # this endpoint is used. No absent on-chain V2 data fabricated.
    return inspect(manifest,config["el"],lease_id)


class BoundedConsoleServer(ThreadingHTTPServer):
    """Bound concurrent connections; overload closes the connection."""
    request_queue_size=16
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(*args,**kwargs)
    def get_request(self):
        sock,addr=super().get_request()
        sock.settimeout(10)
        return sock,addr
    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self,request,client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self.slots.release()


class StatusCache:
    """Only successful observations are cached; no stale-on-error claims."""
    def __init__(self,ttl=15,clock=time.monotonic):
        self.ttl=ttl
        self.clock=clock
        self.lock=threading.Lock()
        self.value=None
        self.expires=0
    def read(self,loader):
        with self.lock:
            if self.value is not None and self.clock()<self.expires:
                return self.value
            self.value=None
            value=loader()
            self.value=value
            self.expires=self.clock()+self.ttl
            return value


def make_server(config,port=8766,*,capture=real_node_capture,inspect=finalized_market_lease,public_readonly=False):
    if type(port) is not int or port!=0 and not 1024<=port<=65535:
        raise Refused("only local unprivileged console port (0 for tests)")
    if type(config) is not dict or set(config)-{"monitorAddress"}!={"nodeId","declaredRoles","el","bn","manifest"}:
        raise Refused("unexpected node role-local configuration")

    address=config.get("monitorAddress")
    if address is not None and (not isinstance(address,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",address) or int(address,16)==0 or config["bn"] is not None or "monitor" not in config["declaredRoles"]):
        raise Refused("monitor account requires a nonzero public address and application monitor role")
    cache=StatusCache()

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
                             "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; style-src 'sha256-"+DASHBOARD_STYLE_HASH+"'")
            self.send_header("Referrer-Policy","no-referrer")
            self.end_headers()
            self.wfile.write(body)
        def json_reply(self,status,data):
            raw=json.dumps(data,sort_keys=True,separators=(",",":"),
                           ensure_ascii=True,allow_nan=False).encode("utf-8")
            return self.reply(status,raw,"application/json; charset=utf-8")
        def do_GET(self):
            try:
                target=urlsplit(self.path)
                if target.scheme or target.netloc or not self.path.startswith("/"):
                    return self.json_reply(400,{"error":"invalid request target"})
                path=target.path
                if path=="/healthz":
                    return self.json_reply(200,{
                        "schema":"SSE_R238_LOOPBACK_PROCESS_HEALTH_V1",
                        "alive":True,"chainVerifiedByHealthz":False,
                        "transactionsSubmitted":False})
                if path in ("/","/v2/status"):
                    status=cache.read(lambda:node_status(config,capture=capture))
                    if path=="/":
                        return self.reply(200,status_html(status,public_readonly=public_readonly),
                                          "text/html; charset=utf-8")
                    return self.json_reply(200,status)
                match=LEASE_PATH.fullmatch(path)
                if match and not public_readonly:
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

    return BoundedConsoleServer(("127.0.0.1",port),Handler)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id",required=True)
    p.add_argument("--roles",default="observer",help="comma-separated declared local roles, not activation")
    p.add_argument("--el",required=True)
    p.add_argument("--bn",help="local Beacon endpoint; omit for application-only RPC mode")
    p.add_argument("--v2-manifest",type=Path)
    p.add_argument("--monitor-address",default=os.environ.get("SSE_MONITOR_ADDRESS"),help="explicit public monitor account to display; no ownership claim")
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--public-readonly",action="store_true",help="restrict tunnel-facing console to bounded cached status and health; no lease lookups")
    p.add_argument("--serve",action="store_true",
                   help="start owner-local read-only HTTP; TLS proxy is separate")
    a=p.parse_args(argv)
    try:
        conf=approved_options(a.node_id,a.roles.split(","),a.el,a.bn,a.v2_manifest)
        if a.monitor_address:
            conf["monitorAddress"]=a.monitor_address
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
        server=make_server(conf,a.port,public_readonly=a.public_readonly)
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
