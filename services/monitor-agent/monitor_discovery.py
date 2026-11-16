#!/usr/bin/env python3
"""Node-local monitor assignment discovery (dry-run by default, read-only RPC).

The signer and Docker daemon are deliberately NOT imported or configured.
--scan checks one bounded RPC range and advances a crash-safe local cursor.
--watch repeats the read-only scan; never submits confirmations or votes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))

from sse_node_marketplace import RPC
from sse_monitor_discovery import MonitorDiscovery, DiscoveryError
from sse_monitor_action_queue import MonitorActionQueue
from sse_monitor_public_snapshot import write_snapshot
from sse_node_role_policy import role_manifest


def main(argv=None):
    p=argparse.ArgumentParser(description="SSE read-only monitor committee/epoch event discovery")
    p.add_argument("--node-roles-file", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--rpc-url", required=True)
    p.add_argument("--settlement", required=True)
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--start-block", type=int, required=True,
                   help="approved contract deployment block; no implicit genesis scan")
    p.add_argument("--confirmations", type=int, default=2,
                   help="additional chain-block delay, NOT consensus finality")
    p.add_argument("--max-blocks", type=int, default=128)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true",
                      help="explicitly read chain once and persist cursor")
    mode.add_argument("--watch", action="store_true",
                      help="explicitly poll chain read-only until interrupted")
    mode.add_argument("--review", action="store_true",
                      help="read existing event journal only; recheck proposed owner tasks")
    p.add_argument("--review-limit", type=int, default=64)
    p.add_argument("--export-review-snapshot", type=Path,
                   help="only with --review: atomically publish bounded nonsecret node-local display file")
    p.add_argument("--interval-seconds", type=float, default=5.0)
    args=p.parse_args(argv)
    try:
        f=args.node_roles_file
        if (not f.is_absolute() or f.is_symlink() or not f.is_file()
                or f.stat().st_size > 8192):
            raise DiscoveryError("expected existing small absolute role manifest")
        node=role_manifest(json.loads(f.read_text("utf-8")))
        if "monitor" not in node["roles"]:
            raise DiscoveryError("monitor role not configured on this node")
        if args.interval_seconds < 1 or args.interval_seconds > 3600:
            raise DiscoveryError("poll interval must be between 1 and 3600 seconds")
        if args.export_review_snapshot is not None and not args.review:
            raise DiscoveryError("--export-review-snapshot requires explicit --review")
        if not (args.scan or args.watch or args.review):
            print(json.dumps({
                "kind":"SSE_MONITOR_DISCOVERY_PLAN", "nodeId":node["nodeId"],
                "monitor":node["wallets"]["monitor"],
                "startBlock":args.start_block,
                "confirmationBlocks":args.confirmations,
                "maxBlocksPerPass":args.max_blocks,
                "rpcCalled":False, "journalWritten":False,
                "roleWalletLoaded":False, "ethereumTransactionsSent":False,
                "automaticMonitorVotes":False
            },sort_keys=True,indent=2))
            return 0
        if args.review:
            # The reviewer opens an EXISTING monitor journal via SQLite mode=ro.
            # It does not mutate the event cursor or load role signing keys.
            queue=MonitorActionQueue(node,args.journal,args.chain_id,
                                     args.settlement,limit=args.review_limit)
            result=queue.review(RPC(args.rpc_url))
            if args.export_review_snapshot is not None:
                write_snapshot(args.export_review_snapshot,result)
            print(json.dumps(result,sort_keys=True,indent=2))
            return 0
        scanner=MonitorDiscovery(args.journal,node,args.chain_id,args.settlement,
                                 args.start_block,args.confirmations,args.max_blocks)
        rpc=RPC(args.rpc_url)
        while True:
            result=scanner.scan(rpc)
            print(json.dumps({
                "kind":"SSE_MONITOR_EVENT_DISCOVERY", "nodeId":node["nodeId"],
                "new":result["new"],"cursor":result["status"]["lastBlock"],
                "waitingForBlocks":result["waitingForBlocks"],
                "finalityVerified":False,"votesSubmitted":False,
                "ethereumTransactionsSent":False,
            },sort_keys=True),flush=True)
            if not args.watch:
                return 0
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print("SSE_MONITOR_DISCOVERY_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
