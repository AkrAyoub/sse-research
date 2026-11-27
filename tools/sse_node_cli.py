#!/usr/bin/env python3
"""R335: discover current publisher invocation URL and report live status.
No service mutation, keys, transaction sending or interactive prompts.
"""
import argparse
import json
import re
import subprocess
import sys
from sse_node_install_summary import LOCAL, fetch, summary

UNIT="sse-application-public-dashboard.service"
URL=re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com(?=[\s|]|$)")

def command(args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=8).stdout

def current_url():
    if command(["systemctl","--user","is-active",UNIT]).strip()!="active":
        return None
    invocation=command(["systemctl","--user","show",UNIT,"-p","InvocationID","--value"]).strip()
    if not re.fullmatch(r"[0-9a-f]{32}",invocation) or int(invocation,16)==0:
        return None
    logs=command(["journalctl","--user","-b","-u",UNIT,"_SYSTEMD_INVOCATION_ID="+invocation,"--no-pager","-o","cat","-n","200"])
    urls=URL.findall(logs)
    return urls[-1] if urls else None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=("status","dashboard","logs"))
    a=p.parse_args()
    if a.operation=="logs":
        return subprocess.call(["journalctl","--user","-b","-u","sse-application-rpc.service","-u","sse-application-dashboard.service","-u",UNIT,"--no-pager","-n","80"])
    try:
        local=fetch(LOCAL)
        report=summary(local)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("Local dashboard unavailable: "+str(exc),file=sys.stderr)
        return 2
    candidate=None
    try:
        candidate=current_url()
        if candidate:
            report=summary(local,candidate)
        else:
            report["publicStatus"]="No current tunnel URL available"
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        report["publicStatus"]="Public verification unavailable: "+str(exc)
    if candidate and not report["publicHttpsVerified"]:
        report["unverifiedTunnelCandidate"]=candidate
    if a.operation=="status":
        print(json.dumps(report,indent=2,ensure_ascii=True))
    if report["publicHttpsVerified"]:
        print("Public dashboard: "+report["publicDashboard"])
        return 0
    print("Local dashboard: "+report["localDashboard"])
    print(report.get("publicStatus","Public HTTPS not verified"))
    if candidate:
        print("Unverified tunnel candidate: "+candidate)
    return 3

if __name__=="__main__":
    raise SystemExit(main())
