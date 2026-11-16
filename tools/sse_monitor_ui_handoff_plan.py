#!/usr/bin/env python3
"""R6: render-only multi-user Ubuntu monitor-public-display handoff plan.

This helper NEVER creates users/groups, writes a unit, installs a timer,
starts services, grants file ACLs, reads private wallets, or submits a
blockchain transaction. It produces human-reviewable unit/drop-in text.

Trust boundary: ssemonitor reads its own owner-only SQLite journal and
publishes ONLY a bounded nonsecret queue summary to a separate group-readable
directory. sseagent receives read-only group access to *that directory*,
not to the monitor SQLite journal, signer keys, or archived SLA evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from sse_multi_role_systemd import _path, render_monitor_discovery_unit
from sse_node_role_policy import role_manifest
from sse_node_marketplace import rpc_origin

DISPLAY_DIR = "/run/sse-monitor-display"
DISPLAY_FILE = DISPLAY_DIR + "/tasks.json"
UNIT = "sse-monitor-review-export.service"
TIMER = "sse-monitor-review-export.timer"
NODE_DROPIN = "sse-vm-role-agent.service.d/20-monitor-display.conf"
_SAFE_RPC = re.compile(r"[\s;%\\]")


def render_handoff_plan(node, *, python, checkout, manifest, journal,
                        rpc_url, settlement, chain_id, start_block,
                        confirmations=2, refresh_seconds=45):
    normalized=role_manifest(node)
    if "monitor" not in normalized["roles"]:
        raise ValueError("read-only display needs a locally configured monitor role")
    if type(refresh_seconds) is not int or not 15 <= refresh_seconds <= 90:
        raise ValueError("refresh interval must be an integer 15..90 seconds")
    # Reuse the accepted R5 supervisor's strict POSIX paths/chain/RPC checks.
    render_monitor_discovery_unit(
        normalized,python=python,checkout=checkout,manifest=manifest,
        journal=journal,rpc_url=rpc_url,settlement=settlement,chain_id=chain_id,
        start_block=start_block,confirmations=confirmations)
    url=rpc_origin(rpc_url)
    if _SAFE_RPC.search(url):
        raise ValueError("RPC origin unsafe in systemd unit")
    script=_path(checkout.rstrip("/")+
                 "/services/monitor-agent/monitor_discovery.py")
    command=" ".join((
        _path(python), "-I", script,
        "--node-roles-file", _path(manifest),
        "--journal", _path(journal), "--rpc-url", url,
        "--settlement", settlement.lower(), "--chain-id", str(chain_id),
        "--start-block", str(start_block), "--confirmations",
        str(confirmations), "--review",
        "--export-review-snapshot", DISPLAY_FILE,
        "--shared-display-group-read",
    ))
    service=(
        "[Unit]\n"
        "Description=SSE monitor nonsecret work-review snapshot refresh\n"
        "After=network-online.target sse-monitor-discovery.service\n"
        "Wants=network-online.target\n\n"
        "[Service]\nType=oneshot\n"
        "User=ssemonitor\nGroup=ssemonitor-display\n"
        "RuntimeDirectory=sse-monitor-display\n"
        "RuntimeDirectoryMode=0750\n"
        "RuntimeDirectoryPreserve=yes\n"
        "WorkingDirectory="+_path(checkout)+"\n"
        "ExecStart="+command+"\n"
        "UMask=0077\n"
        "NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n"
        "PrivateTmp=yes\nCapabilityBoundingSet=\n"
        "RestrictSUIDSGID=yes\nLockPersonality=yes\n"
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6\n"
        "ReadOnlyPaths=/var/lib/sse-monitor\n"
        "ReadWritePaths="+DISPLAY_DIR+"\n"
        "StandardOutput=null\n\n"
        "# This unit has no [Install] section: activate ONLY via reviewed timer.\n"
    )
    timer=(
        "[Unit]\n"
        "Description=Periodic owner-local nonsecret monitor work snapshot\n\n"
        "[Timer]\n"
        "OnBootSec=30s\n"
        "OnUnitActiveSec="+str(refresh_seconds)+"s\n"
        "AccuracySec=5s\nPersistent=no\n"
        "Unit="+UNIT+"\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    dropin=(
        "# Review operator-managed sse-vm-role-agent.service before applying.\n"
        "[Service]\nSupplementaryGroups=ssemonitor-display\n"
        "Environment=SSE_MONITOR_WORK_SNAPSHOT_FILE="+DISPLAY_FILE+"\n"
        "Environment=SSE_MONITOR_WALLET="+
        normalized["wallets"]["monitor"]+"\n"
    )
    return {
        "kind":"SSE_R6_MONITOR_UI_ISOLATED_HANDOFF_PLAN",
        "nodeId":normalized["nodeId"],
        "roles":normalized["roles"],
        "units":{UNIT:service,TIMER:timer,NODE_DROPIN:dropin},
        "accountsToProvisionManually":["ssemonitor","sseagent"],
        "sharedGroupToProvisionManually":"ssemonitor-display",
        "privateMonitorJournalShared":False,
        "privateSigningKeysShared":False,
        "snapshotReadOnlyToUi":True,
        "publicSnapshotMode":"0640",
        "publicSnapshotDirectoryMode":"0750",
        "unitFilesWritten":False,
        "servicesStarted":False,
        "ethereumTransactionsSent":False,
        "automaticVotesEnabled":False,
        "operatorApprovalRequired":True,
        "warning":("Requires explicit Ubuntu user/group provisioning, unit "
                   "inspection, controlled installation and cross-account "
                   "permission/failure tests before real activation."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="R6 render-only monitor UI handoff systemd plan")
    p.add_argument("--roles-file",type=Path,required=True)
    p.add_argument("--python",required=True)
    p.add_argument("--checkout",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--journal",required=True)
    p.add_argument("--rpc-url",required=True)
    p.add_argument("--settlement",required=True)
    p.add_argument("--chain-id",type=int,required=True)
    p.add_argument("--start-block",type=int,required=True)
    p.add_argument("--confirmations",type=int,default=2)
    p.add_argument("--refresh-seconds",type=int,default=45)
    a=p.parse_args(argv)
    try:
        if (not a.roles_file.is_absolute() or a.roles_file.is_symlink()
                or not a.roles_file.is_file() or a.roles_file.stat().st_size > 8192):
            raise ValueError("roles file must be a small absolute existing regular file")
        roles=json.loads(a.roles_file.read_text("utf-8"))
        plan=render_handoff_plan(
            roles,python=a.python,checkout=a.checkout,manifest=a.manifest,
            journal=a.journal,rpc_url=a.rpc_url,settlement=a.settlement,
            chain_id=a.chain_id,start_block=a.start_block,
            confirmations=a.confirmations,refresh_seconds=a.refresh_seconds)
        print(json.dumps(plan,indent=2,sort_keys=True))
        return 0
    except (ValueError,OSError,TypeError) as exc:
        print("SSE_R6_MONITOR_HANDOFF_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
