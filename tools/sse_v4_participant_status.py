#!/usr/bin/env python3
"""Read-only per-host readiness inventory; no secrets, no activation claims."""
import json
import os
from pathlib import Path
import time
import subprocess
import sys
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()
sys.path.insert(0,str(ROOT/"tools"))

def run(*argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=8)
        return p.stdout.strip() if p.returncode==0 else "unavailable"
    except (OSError,subprocess.TimeoutExpired): return "unavailable"

def active(name):
    return run("systemctl","--user","is-active",name)=="active"
def enabled(name):
    return run("systemctl","--user","is-enabled",name)=="enabled"

def main():
    if os.geteuid()==0: raise SystemExit("run as participant owner")
    units=("sse-rpc-adapter.service","sse-v4-console.service","sse-v4-console-public.service","sse-v4-agent.service","sse-v4-provider-outputs.service")
    out={"host":run("id","-un"),"sourceCommit":run("git","-C",str(ROOT),"rev-parse","HEAD"),
         "overlayAddresses":run("ip","-6","-o","addr","show","scope","global"),
         "services":{n:{"active":active(n),"enabled":enabled(n)} for n in units},
         "wallet":None,"roles":[],"deploymentVerified":False,"monitorPosition":None,
         "providerConfigured":False,"localConsoleHTTP":False,"publicURLVerified":False}
    try:
        from sse_v4_agent import load_policy
        p=load_policy(HOME/".config/sse-v4/policy.json")
        out["wallet"]=p["wallet"]; out["roles"]=p["roles"]
        cfg=p.get("provider",{})
        out["providerConfigured"]=bool(cfg.get("workers") and cfg.get("approvedOfferHashes") and cfg.get("capacity",{}).get("maxConcurrentLeases",0)>0)
        out["monitorAutoConfirm"]=p.get("monitor",{}).get("autoConfirm",False)
        out["gasPolicy"]=p["spending"]
    except Exception as e: out["policyStatus"]=type(e).__name__
    try:
        from sse_chain_read import LocalRPC
        import sse_v4_state as st
        import sse_v4_abi as abi
        m=st.load_manifest(ROOT/"release/chain31340-v4-manifest.json")
        ask=LocalRPC("http://127.0.0.1:28545",timeout=15).request
        st.verify_deployment(ask,m)
        out["deploymentVerified"]=True
        out["finalized"]=st.finalized(ask)
        f=ask("eth_getBlockByNumber",["finalized",False])
        out["finalityAgeSeconds"]=int(time.time())-int(f["timestamp"],16)
        out["recentFinality"]=0<=out["finalityAgeSeconds"]<1800
        if out["wallet"]:
            out["finalizedBalanceWei"]=int(ask("eth_getBalance",[out["wallet"],"finalized"]),16)
            if "monitor" in out["roles"]:
                out["monitorPosition"]=abi.view(ask,m["modules"]["registry"],"position(address)",("address",),(out["wallet"],),("uint256",)*4+("bool",),"finalized")
    except Exception as e: out["rpcStatus"]=type(e).__name__
    try:
        with urllib.request.urlopen("http://127.0.0.1:8790/",timeout=5) as r:
            out["localConsoleHTTP"]=r.status==200
    except Exception: pass
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
