#!/usr/bin/env python3
"""Multi-role Ubuntu service supervision PLAN: role isolation under systemd.

systemd, not an all-powerful network dashboard or one shared wallet daemon,
must supervise separate SSE role processes under separate Linux users.

Only the current *read-only monitor discovery* service is safe to propose.
Provider/consumer key-bearing agents, monitor confirmations and EVM votes
are never started automatically by this helper. It has NO --apply flag.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from sse_node_marketplace import rpc_origin
from sse_node_role_policy import role_manifest

PATH=re.compile(r"/[a-zA-Z0-9_./-]{1,240}\Z")
ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")


class SupervisorPlanError(ValueError):
    pass


def _path(value):
    if (type(value) is not str or not PATH.fullmatch(value) or ".." in Path(value).parts):
        raise SupervisorPlanError("unit path must be an absolute trusted POSIX path")
    return value


def render_monitor_discovery_unit(node, *, python, checkout, manifest,
                                  journal, rpc_url, settlement, chain_id,
                                  start_block, confirmations=2):
    """Return systemd service text for review; NO disk writes or activation."""
    n=role_manifest(node)
    if "monitor" not in n["roles"]:
        raise SupervisorPlanError("node is not configured for the monitor role")
    for val in (python,checkout,manifest,journal):
        _path(val)
    if not journal.startswith("/var/lib/sse-monitor/"):
        raise SupervisorPlanError("monitor journal must live in private systemd StateDirectory")
    url=rpc_origin(rpc_url)
    if re.search(r"[\s;%\\]", url):
        raise SupervisorPlanError("unsafe RPC URL in systemd unit")
    if (type(settlement) is not str or not ADDRESS.fullmatch(settlement)
            or int(settlement,16)==0 or type(chain_id) is not int or chain_id < 1
            or type(start_block) is not int or start_block < 0
            or type(confirmations) is not int or not 0 <= confirmations <= 256):
        raise SupervisorPlanError("invalid monitor discovery chain parameters")
    script=_path(checkout.rstrip("/") + "/services/monitor-agent/monitor_discovery.py")
    command=" ".join([
        python, "-I", script,
        "--node-roles-file", manifest,
        "--journal", journal,
        "--rpc-url", url,
        "--settlement", settlement.lower(),
        "--chain-id", str(chain_id),
        "--start-block",str(start_block),
        "--confirmations",str(confirmations),
        "--watch",
    ])
    return (
        "[Unit]\n"
        "Description=SSE node-local read-only monitor event discovery\n"
        "After=network-online.target\nWants=network-online.target\n\n"
        "[Service]\nType=simple\n"
        "User=ssemonitor\nGroup=ssemonitor\n"
        "StateDirectory=sse-monitor\nStateDirectoryMode=0700\n"
        "WorkingDirectory=" + _path(checkout) + "\n"
        "ExecStart=" + command + "\n"
        "Restart=on-failure\nRestartSec=8\n"
        "NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n"
        "PrivateTmp=yes\nCapabilityBoundingSet=\n"
        "ReadWritePaths=/var/lib/sse-monitor\n"
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6\n"
        "LockPersonality=yes\nRestrictSUIDSGID=yes\n"
        "\n[Install]\nWantedBy=multi-user.target\n"
    )


def role_supervision_plan(node, **kw):
    n=role_manifest(node)
    units={}
    if "monitor" in n["roles"]:
        units["sse-monitor-discovery.service"]=render_monitor_discovery_unit(n,**kw)
    return {
       "kind":"SSE_MULTI_ROLE_SYSTEMD_PLAN", "nodeId":n["nodeId"],
       "configuredRoles":n["roles"], "units":units,
       "monitorDiscoveryOnly":True,
       "providerAutostart":False, "consumerAutostart":False,
       "monitorSignerLoaded":False, "monitorVotesSent":False,
       "systemdUnitWritten":False, "roleActivated":False,
       "ethereumTransactionsSent":False,
       "warning":"Review service ownership, system user, secure RPC and OS packages before installing any unit."
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Safe read-only multi-role systemd unit planning")
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
    a=p.parse_args(argv)
    try:
        if (not a.roles_file.is_absolute() or a.roles_file.is_symlink()
                or not a.roles_file.is_file() or a.roles_file.stat().st_size > 8192):
            raise SupervisorPlanError("expected small trusted absolute node role file")
        node=json.loads(a.roles_file.read_text("utf-8"))
        result=role_supervision_plan(node,python=a.python,checkout=a.checkout,
                manifest=a.manifest,journal=a.journal,rpc_url=a.rpc_url,
                settlement=a.settlement,chain_id=a.chain_id,
                start_block=a.start_block,confirmations=a.confirmations)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (ValueError,OSError,TypeError) as exc:
        print("SSE_MULTI_ROLE_SUPERVISION_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
