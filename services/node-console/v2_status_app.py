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
from datetime import datetime, timezone
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
    Refused as NodeRefused,capture as real_node_capture,http_json as beacon_json,
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


def market_overview(config,proof,transport):
    height=proof["finalizedExecutionHeight"]
    market=proof["contracts"]["market"]["address"]
    def read(signature,args,fields):
        return decode_struct(query(transport,config["el"],market,signature,args,height),fields)
    def count(signature):
        return read(signature,[],(("value","uint256"),))["value"]
    next_request=count("nextRequestId()")
    next_lease=count("nextLeaseId()")
    if next_request<1 or next_lease<1:
        raise Refused("invalid finalized market counters")
    recent=[]
    for request_id in range(max(1,next_request-3),next_request):
        record=read("requests(uint256)",[request_id],(("consumer","address"),("profileHash","bytes32"),("policyHash","bytes32"),("maxEpochFeeWei","uint256"),("biddingClose","uint64"),("selected","bool")))
        if int(record["consumer"],16)==0:
            raise Refused("missing request in finalized market range")
        record["maxEpochFeeWei"]=str(record["maxEpochFeeWei"])
        record["requestId"]=str(request_id)
        record["bidCount"]=str(read("bidCount(uint256)",[request_id],(("value","uint256"),))["value"])
        recent.append(record)
    return {"finalizedExecutionHeight":height,"requestsCreated":str(next_request-1),
            "leasesCreated":str(next_lease-1),"activeMonitorCount":str(count("activeMonitorCount()")),
            "recentRequests":recent,"recentRequestLimit":3}


def recent_blocks(config,transport=rpc,start=None):
    """Bounded real canonical execution headers, with transaction hashes."""
    final=transport(config["el"],"eth_getBlockByNumber",["finalized",False])
    height=int(final["number"],16)
    if start is None:
        start=height
    if type(start) is not int or not 0<=start<=height:
        raise Refused("requested block outside finalized history")
    blocks=[]
    expected_hash=final["hash"] if start==height else None
    for number in range(start,max(-1,start-8),-1):
        block=transport(config["el"],"eth_getBlockByNumber",[hex(number),False])
        if int(block["number"],16)!=number or (expected_hash is not None and block["hash"]!=expected_hash):
            raise Refused("inconsistent canonical block sequence")
        txs=block["transactions"]
        if not isinstance(txs,list) or any(not isinstance(t,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",t) for t in txs[:16]):
            raise Refused("malformed block transactions")
        record={key:block[key] for key in ("hash","parentHash","stateRoot","transactionsRoot","receiptsRoot")}
        if any(not isinstance(v,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",v) for v in record.values()):
            raise Refused("malformed block header roots")
        record.update(number=number,timestamp=int(block["timestamp"],16),gasUsed=str(int(block["gasUsed"],16)),gasLimit=str(int(block["gasLimit"],16)),transactionCount=len(txs),transactionHashes=txs[:16],transactionHashesTruncated=len(txs)>16)
        recipient=block.get("miner")
        if recipient is not None and (not isinstance(recipient,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",recipient)):
            raise Refused("malformed fee recipient")
        record["feeRecipient"]=recipient
        blocks.append(record)
        expected_hash=record["parentHash"]
    return {"finalizedHeight":height,"pageStart":start,"blocks":blocks,"source":"configured execution RPC","localDiskStorageVerified":False,"transactionHashLimitPerBlock":16}


def proposer_identity(config,block,transport=beacon_json):
    if config["bn"] is None:
        return None
    base=config["bn"]
    genesis=transport(base+"/eth/v1/beacon/genesis")
    elapsed=block["timestamp"]-int(genesis["genesis_time"])
    if elapsed<=0 or elapsed%12:
        return None
    slot=elapsed//12
    data=transport(base+"/eth/v2/beacon/blocks/"+str(slot),max_size=4194304)
    message=data["message"]
    if int(message["slot"])!=slot or message["body"]["execution_payload"]["block_hash"].lower()!=block["hash"].lower():
        raise Refused("Beacon block does not match execution hash")
    index=int(message["proposer_index"])
    validator=transport(base+"/eth/v1/beacon/states/"+str(slot)+"/validators/"+str(index))
    pubkey=validator["validator"]["pubkey"]
    if int(validator["index"])!=index or not re.fullmatch(r"0x[0-9a-fA-F]{96}",pubkey):
        raise Refused("invalid historical proposer record")
    return {"slot":slot,"validatorIndex":index,"validatorPublicKey":pubkey,"executionHashMatched":True}


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
                "marketOverview":market_overview(config,verified,transport) if config.get("marketOverview") else None,
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


DASHBOARD_CSS="""*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f5f7fb;color:#17263b;font:14px/1.55 system-ui,sans-serif}a{color:#1659c7;text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:3px solid #2563eb;outline-offset:4px}.shell{display:grid;grid-template-columns:235px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:#101c30;color:#c4d1e3;padding:28px 18px;display:flex;flex-direction:column;gap:24px}.brand{font-size:19px;font-weight:800;color:white;letter-spacing:-.5px}.brand small{display:block;font-size:10px;letter-spacing:2px;color:#8baccd;margin-top:4px}.nav-label{font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:#8baccd;margin:0 10px 8px}.sidebar a{display:block;color:#d9e5f5;padding:10px 12px;border-radius:7px;margin:3px 0}.sidebar a:hover{background:#243a56;text-decoration:none}.sidebar .network{margin-top:auto;border-top:1px solid #34445b;padding-top:16px;font-size:12px}.workspace{min-width:0}.topbar{background:white;border-bottom:1px solid #e0e6ef;padding:18px 34px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.topbar strong{font-size:13px}.tag{display:inline-block;padding:5px 10px;border-radius:6px;background:#eaf0fa;color:#315581;font-size:12px;font-weight:600}.button{display:inline-block;background:#1858b8;color:white;padding:9px 14px;border-radius:7px;font-weight:600}.button:hover{background:#114898;text-decoration:none}main{max-width:1440px;margin:auto;padding:30px 34px 50px}h1,h2,p{margin:0}h1{font-size:30px;letter-spacing:-1px;line-height:1.2}h2{font-size:18px;letter-spacing:-.3px;margin-bottom:12px}h3{font-size:14px;margin:0 0 8px}.muted{color:#5d6b80}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#54749b;margin-bottom:8px}.intro{margin-bottom:22px;display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}.intro p{margin-top:8px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metric,.panel{background:white;border:1px solid #e0e6ef;border-radius:12px;box-shadow:0 2px 5px #182c4805;padding:20px}.metric span{display:block;font-size:12px;font-weight:600;color:#5d6b80}.metric strong{display:block;font-size:28px;letter-spacing:-1px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;margin-top:12px}.panel{margin-top:18px;scroll-margin-top:24px}.panel>p{margin-bottom:12px}.role-tags{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.role-tags span{background:#e9f0fd;color:#204b90;padding:6px 11px;border-radius:6px;font-weight:600}.notice{border-left:3px solid #bc7b17;background:#fff8ec;padding:12px;margin:14px 0;color:#80550e;border-radius:0 5px 5px 0}.good{color:#087849}.caution{color:#8f610c}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{text-align:left;padding:11px 8px;border-bottom:1px solid #edf0f5;vertical-align:top;overflow-wrap:anywhere}th{font-size:12px;color:#5d6b80;font-weight:600;width:35%}td{font-variant-numeric:tabular-nums}tr:last-child th,tr:last-child td{border-bottom:0}.blockstrip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.blocktile{border:1px solid #dce5f1;background:#f5f8fe;border-radius:9px;padding:12px;color:#1c4e8e}.blocktile strong,.blocktile small{display:block}.blocktile strong{font-size:16px}.blocktile small{font-size:11px;color:#5d6b80}.blocktile:hover{background:#eaf1ff;text-decoration:none}.blockdetail{border-top:1px solid #e0e6ef;scroll-margin-top:20px}.blockdetail summary{padding:13px 4px;cursor:pointer;font-weight:600}.blockdetail ul{padding-left:24px;overflow-wrap:anywhere}.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}.split .panel{min-width:0}.money{font-variant-numeric:tabular-nums}.footer{margin-top:24px;color:#5d6b80;font-size:12px}.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.subtle{font-size:12px;color:#5d6b80}@media(max-width:1100px){.grid,.blockstrip{grid-template-columns:repeat(2,minmax(0,1fr))}.split{grid-template-columns:1fr}}@media(max-width:740px){.shell{display:block}.sidebar{height:auto;position:static;padding:16px;gap:12px}.sidebar nav{display:flex;flex-wrap:wrap;gap:3px}.sidebar a{padding:7px 10px}.sidebar .network,.nav-label{display:none}.topbar{padding:12px 16px}main{padding:22px 14px}.metric,.panel{padding:15px}.metric strong{font-size:22px}h1{font-size:25px}th{width:38%}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}"""
DASHBOARD_STYLE_HASH=base64.b64encode(hashlib.sha256(DASHBOARD_CSS.encode("utf-8")).digest()).decode("ascii")


def status_html(payload,public_readonly=False):
    esc=lambda x:html.escape(str(x),quote=True)
    def eth(value):
        whole,fraction=divmod(int(value),10**18)
        return (str(whole)+"."+str(fraction).zfill(18)).rstrip("0").rstrip(".")+" TEST ETH"
    def utc(value):
        return datetime.fromtimestamp(int(value),timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    def field(label,value):
        return "<tr><th>"+esc(label)+"</th><td>"+esc(value)+"</td></tr>"
    def metric(label,value):
        return "<div class='metric'><span>"+esc(label)+"</span><strong>"+esc(f"{value:,}" if isinstance(value,int) else value)+"</strong></div>"
    def check(label,value):
        return field(label,"Verified" if value is True else "Not verified")
    name=esc(payload["nodeId"])
    roles=", ".join(payload["declaredRoles"])
    app=payload["schema"]=="SSE_R314_APPLICATION_RPC_STATUS_V1"
    if app:
        audit=payload["deploymentAudit"]
        metrics=(("Chain ID",payload["chainId"]),("Execution head",payload["executionBlockNumber"]),
                 ("Finalized block",payload["finalizedExecutionHeight"]),("Finality timestamp gap",str(payload["finalityLagSeconds"]//60)+"m "+str(payload["finalityLagSeconds"]%60)+"s"))
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
        account_rows="".join(field(label,eth(account[key]) if key.endswith("Wei") else ("Active" if account[key] else "Inactive") if key=="active" else account[key]) for label,key in (("Public account","address"),("Observed finalized block","finalizedExecutionHeight"),("On-chain active registration","active"),("Native balance","balanceWei"),("Bond","bondWei"),("Locked assignments","lockedAssignments"),("Market withdrawable","marketWithdrawableWei"),("Ledger withdrawable","ledgerWithdrawableWei")))
        account_panel="<section class='panel' id='account'><div class='eyebrow'>Role / Monitor</div><h2>Monitor account</h2><table>"+account_rows+"</table><p class='muted'>Public address observation only; wallet ownership and committee selection are not established.</p></section>"
    overview=payload.get("marketOverview")
    market_panel=""
    if overview is not None:
        market_rows="".join(field(label,overview[key]) for label,key in (("Finalized block","finalizedExecutionHeight"),("Requests created (cumulative)","requestsCreated"),("Leases created (cumulative)","leasesCreated"),("Active registered monitors","activeMonitorCount")))
        for request in reversed(overview["recentRequests"]):
            market_rows+=field("Request #"+request["requestId"],"Bids: "+request["bidCount"]+" | Selected: "+str(request["selected"])+" | Max fee: "+eth(request["maxEpochFeeWei"])+" | Bidding close: "+utc(request["biddingClose"]))
        market_panel="<section class='panel' id='market'><div class='eyebrow'>Network / Marketplace</div><h2>Finalized marketplace</h2><table>"+market_rows+"</table><p class='muted'>Latest three requests at most. Counts do not establish independent hosts or active service delivery.</p></section>"
    explorer=payload.get("blockExplorer") if not app and set(payload["declaredRoles"]) & {"observer","full_node","validator"} else None
    block_panel=""
    if explorer is not None:
        parts=[]
        tiles=[]
        for block in explorer["blocks"]:
            block_rows="".join(field(label,block[key]) for label,key in (("Block hash","hash"),("Parent hash","parentHash"),("State root","stateRoot"),("Transactions root","transactionsRoot"),("Receipts root","receiptsRoot"),("Timestamp (Unix UTC)","timestamp"),("Gas used","gasUsed"),("Gas limit","gasLimit"),("Transaction count","transactionCount")))
            block_rows+=field("Execution fee recipient (not proposer)",block.get("feeRecipient") or "Unavailable")
            proposer=block.get("proposer")
            if proposer:
                block_rows+=field("Beacon slot",proposer["slot"])+field("Proposer index",proposer["validatorIndex"])+field("Validator public key",proposer["validatorPublicKey"])
            else:
                block_rows+=field("Consensus proposer","Not resolved")
            hashes="".join("<li>"+esc(tx)+"</li>" for tx in block["transactionHashes"])
            tiles.append("<a class='blocktile' href='/blocks/"+esc(block["number"])+"'><small>FINALIZED BLOCK</small><strong>#"+esc(block["number"])+"</strong><small>"+esc(block["transactionCount"])+" transactions</small></a>")
            parts.append("<details class='blockdetail' id='block-"+esc(block["number"])+"'><summary>Block "+esc(block["number"])+" / "+esc(block["transactionCount"])+" transactions</summary><table>"+block_rows+"</table><ul>"+hashes+"</ul>"+("<p>Transaction list truncated.</p>" if block["transactionHashesTruncated"] else "")+"</details>")
        first=explorer["blocks"][0]["number"]
        nav_history="<p><a href='/blocks/"+str(explorer["finalizedHeight"])+"'>Latest</a>"
        if first>=8:
            nav_history+=" · <a href='/blocks/"+str(first-8)+"'>Older blocks</a>"
        if first<explorer["finalizedHeight"]:
            nav_history+=" · <a href='/blocks/"+str(min(first+8,explorer["finalizedHeight"]))+"'>Newer blocks</a>"
        nav_history+=" · <a href='/blocks/0'>Genesis</a> · <a href='/v2/blocks/"+str(first)+"'>Page JSON</a></p>"
        block_panel="<section class='panel' id='blocks'><div class='eyebrow'>Network / Explorer</div><h2>Finalized block explorer</h2><p class='muted'>Finalized execution history from configured RPC. Local disk storage is not verified.</p>"+nav_history+"<div class='blockstrip'>"+"".join(tiles)+"</div>"+"".join(parts)+"</section>"
    v3=payload.get("marketV3")
    v3_panel=""
    if v3 is not None:
        v3_panel="<section class='panel' id='market-v3'><div class='eyebrow'>Marketplace / Scientific V3</div><h2>Scientific market</h2>"
        if "error" in v3:
            v3_panel+="<p class='notice'>Finalized V3 evidence unavailable.</p>"
        else:
            v3_panel+= "<div class='grid'>"+metric("Requests",v3["requestsCreated"])+metric("Leases",v3["leasesCreated"])+metric("Active monitors",v3["activeMonitors"])+metric("Finalized height",v3["deployment"]["finalizedHeight"])+"</div>"
            for req in v3["recentRequests"]:
                v3_panel+="<details class='blockdetail' open><summary>Request "+esc(req["id"])+" / "+esc(req["bidCount"])+" bids</summary><table>"+"".join(field(k,eth(v) if k.endswith("Wei") else v) for k,v in req.items() if k not in ("id","bids"))+"</table>"
                for bid in req.get("bids",[]):
                    v3_panel+="<details class='blockdetail'><summary>Bid "+esc(bid["index"])+" / "+esc(eth(bid["feeWei"]))+"</summary><table>"+field("Provider",bid["provider"])+"</table></details>"
                v3_panel+="</details>"
            for lease in v3["recentLeases"]:
                a=lease["accounting"]
                v3_panel+="<details class='blockdetail' open><summary>Lease "+esc(lease["id"])+" / exposure "+esc(eth(a["exposureWei"]))+"</summary><table>"
                v3_panel+="".join(field(k,eth(v) if k.endswith("Wei") else v) for k,v in lease.items() if k not in ("id","accounting","epochs"))
                v3_panel+="".join(field(k,eth(v) if k.endswith("Wei") else v) for k,v in a.items())+"</table>"
                for epoch in lease["epochs"]:
                    outcome="Pending" if not epoch["accounted"] else {0:"Inconclusive",1:"Success",2:"Failure"}.get(epoch["outcome"],"Unknown")
                    histories=", ".join(label for bit,label in ((1,"N"),(2,"F"),(4,"S")) if epoch["historyMask"] & bit)
                    v3_panel+="<details class='blockdetail'><summary>Epoch "+esc(epoch["id"])+" / "+esc(outcome)+" / "+esc(histories)+"</summary><table>"+"".join(field(k,eth(v) if k.endswith("Wei") else v) for k,v in epoch.items())+"</table></details>"
                v3_panel+="</details>"
            v3_panel+="<p class='muted'>Finalized contract observations; committee evidence is conditional, not proof of physical truth.</p>"
        v3_panel+="</section>"
    intent_panel=""
    if v3 is not None:
        from sse_pos_r389_v3_intent_forms import render
        intent_panel=render(payload["declaredRoles"])
    cards="".join(metric(label,value) for label,value in metrics)
    lease_note=("Lease lookups disabled on this public listener." if public_readonly else
                "Finalized lease lookup: /v2/lease/{id} requires a verified deployment manifest.")
    links=[("Overview","#overview"),("Selected roles","#roles")]
    if account is not None: links.append(("Monitor account","#account"))
    if overview is not None: links.append(("Marketplace","#market"))
    if v3 is not None:
        links.append(("Scientific V3","#market-v3"))
        links.append(("Prepare operations","#market-actions"))
    if explorer is not None: links.append(("Blockchain explorer","#blocks"))
    links.append(("Verification","#evidence"))
    links.append(("Raw JSON","/v2/status"))
    nav="".join("<a href='"+href+"'>"+esc(label)+"</a>" for label,href in links)
    tags="".join("<span>"+esc(role.replace("_"," ").title())+"</span>" for role in payload["declaredRoles"])
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>SSE Intercloud / "+name+"</title><style>"+DASHBOARD_CSS+"</style></head><body><div class='shell'>"
            "<aside class='sidebar'><div class='brand'>SSE / Intercloud<small>NODE CONSOLE</small></div><div><div class='nav-label'>Workspace</div><nav aria-label='Dashboard sections'>"+nav+"</nav></div>"
            "<div class='network'>Research network<br>Native TEST ETH<br>Read-only public view</div></aside>"
            "<div class='workspace'><header class='topbar'><strong>Node workspace / "+name+"</strong><div class='actions'><span class='tag'>"+esc(scope)+"</span><a class='button' href='/'>Refresh data</a></div></header>"
            "<main id='overview'><section class='intro'><div><div class='eyebrow'>Network overview</div><h1>"+name+"</h1><p class='muted'>"+esc(detail)+"</p></div><span class='tag'>Read-only / TEST ETH</span></section>"
            "<div class='grid'>"+cards+"</div>"
            "<section class='panel' id='roles'><h2>Selected roles</h2><div class='role-tags'>"+tags+"</div><p class='subtle'>"+esc(roles)+"</p><table>"+checks+"</table>"
            "<p class='notice'>Declared roles do not establish authorization, eligibility or completed work.</p></section>"
            +account_panel+market_panel+v3_panel+intent_panel+block_panel+"<section class='panel' id='evidence'><div class='eyebrow'>Trust / Evidence</div><h2>Blockchain evidence</h2><table>"+rows+"</table></section>"
            "<footer class='footer'><p>"+esc(lease_note)+" Successful observations may be cached for 15 seconds.</p>"
            "<p>No wallet keys, transaction signing or privileged host controls exposed by this console.</p></footer></main></div></div></body></html>").encode("utf-8")


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


def block_explorer_allowed(config):
    return (config.get('blockExplorer') is True and config.get('bn') is not None
            and bool(set(config['declaredRoles']) & {'observer','full_node','validator'}))


def make_server(config,port=8766,*,capture=real_node_capture,inspect=finalized_market_lease,public_readonly=False):
    if type(port) is not int or port!=0 and not 1024<=port<=65535:
        raise Refused("only local unprivileged console port (0 for tests)")
    if type(config) is not dict or set(config)-{"monitorAddress","marketOverview","blockExplorer","marketV3"}!={"nodeId","declaredRoles","el","bn","manifest"}:
        raise Refused("unexpected node role-local configuration")

    address=config.get("monitorAddress")
    if address is not None and (not isinstance(address,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",address) or int(address,16)==0 or config["bn"] is not None or "monitor" not in config["declaredRoles"]):
        raise Refused("monitor account requires a nonzero public address and application monitor role")
    if config.get("marketOverview") and config["bn"] is not None:
        raise Refused("market overview currently requires application RPC mode")
    cache=StatusCache()
    history_lock=threading.Lock()
    history_cache={}
    last_history_read=[-100.0]
    def historical(start):
        with history_lock:
            now=time.monotonic()
            if start in history_cache and now-history_cache[start][0]<60:
                return history_cache[start][1]
            if now-last_history_read[0]<3:
                return None
            last_history_read[0]=now
            cache.read(load_status)
            result=recent_blocks(config,start=start)
            if config["bn"] is not None:
                try:
                    result["blocks"][0]["proposer"]=proposer_identity(config,result["blocks"][0])
                except (NodeRefused,Refused,KeyError,ValueError,TypeError,OSError):
                    result["blocks"][0]["proposer"]=None
            if len(history_cache)>=32:
                history_cache.pop(next(iter(history_cache)))
            history_cache[start]=(now,result)
            return result
    def load_status():
        status=node_status(config,capture=capture)
        if block_explorer_allowed(config):
            status["blockExplorer"]=recent_blocks(config)
        if config.get("marketV3"):
            try:
                from sse_pos_r384_v3_dashboard import overview
                status["marketV3"]=overview(lambda m,p:rpc(config["el"],m,p))
            except (AuditRefused,ValueError,TypeError,KeyError,OSError,OverflowError):
                status["marketV3"]={"error":"finalized V3 evidence unavailable"}
        return status

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
                             "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; style-src 'sha256-"+DASHBOARD_STYLE_HASH+"'")
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
                    status=cache.read(load_status)
                    if path=="/":
                        return self.reply(200,status_html(status,public_readonly=public_readonly),
                                          "text/html; charset=utf-8")
                    return self.json_reply(200,status)
                history=re.fullmatch(r"/(?:v2/)?blocks/([0-9]{1,12})",path)
                if history and block_explorer_allowed(config):
                    start=int(history.group(1))
                    result=historical(start)
                    if result is None:
                        return self.json_reply(429,{"error":"historical reader busy; retry shortly"})
                    if path.startswith("/v2/"):
                        return self.json_reply(200,result)
                    status=dict(cache.read(load_status))
                    status["blockExplorer"]=result
                    return self.reply(200,status_html(status,public_readonly=public_readonly),"text/html; charset=utf-8")
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
            if self.path!="/v3/intent" or not config.get("marketV3"):
                return self.json_reply(405,{"error":"console never signs or changes roles"})
            try:
                if self.headers.get("Transfer-Encoding") or self.headers.get_content_type()!="application/x-www-form-urlencoded":
                    return self.json_reply(415,{"error":"form encoding required"})
                lengths=self.headers.get_all("Content-Length") or []
                if len(lengths)!=1 or not lengths[0].isdigit() or not 0<int(lengths[0])<=4096:
                    return self.json_reply(400,{"error":"invalid form size"})
                from sse_pos_r389_v3_intent_forms import parse
                body=self.rfile.read(int(lengths[0]))
                if len(body)!=int(lengths[0]): raise ValueError("incomplete form")
                data=parse(body,config["declaredRoles"])
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Disposition",'attachment; filename="sse-v3-intent.json"')
                self.send_header("Content-Length",str(len(data)))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                self.wfile.write(data)
            except (ValueError,KeyError,TypeError,OSError,OverflowError):
                return self.json_reply(400,{"error":"invalid unsigned intent"})
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
    p.add_argument("--block-explorer",action="store_true",default=os.environ.get("SSE_BLOCK_EXPLORER")=="1",help="bounded finalized execution block inspection")
    p.add_argument("--market-v3",action="store_true",default=os.environ.get("SSE_MARKET_V3")=="1",help="bounded finalized V3 scientific market panel")
    p.add_argument("--market-overview",action="store_true",default=os.environ.get("SSE_MARKET_OVERVIEW")=="1",help="bounded finalized marketplace observation")
    p.add_argument("--monitor-address",default=os.environ.get("SSE_MONITOR_ADDRESS"),help="explicit public monitor account to display; no ownership claim")
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--public-readonly",action="store_true",help="restrict tunnel-facing console to bounded cached status and health; no lease lookups")
    p.add_argument("--serve",action="store_true",
                   help="start owner-local read-only HTTP; TLS proxy is separate")
    a=p.parse_args(argv)
    try:
        conf=approved_options(a.node_id,a.roles.split(","),a.el,a.bn,a.v2_manifest)
        if a.block_explorer:
            conf["blockExplorer"]=True
        if a.market_v3:
            conf["marketV3"]=True
        if a.market_overview:
            conf["marketOverview"]=True
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
