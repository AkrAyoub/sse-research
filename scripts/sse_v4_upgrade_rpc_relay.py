#!/usr/bin/env python3
"""Owner-only upgrade of existing VM4709 TLS relay, preserving current argv.
Never modifies native clients, certificates, old source, or engine RPC.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import json
import urllib.request
import ssl

def run(*argv):
    return subprocess.check_output(argv, text=True).strip()

def require(ok,msg):
    if not ok:
        raise RuntimeError(msg)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-sha",required=True)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    require(os.geteuid()!=0 and run("id","-un")=="ayoubakrvm4709","existing relay owner only")
    require(run("git","-C",str(repo),"rev-parse","HEAD")==args.source_sha and not run("git","-C",str(repo),"status","--porcelain"),"source not pinned/clean")
    unit="sse-rpc-relay.service"
    pid=int(run("systemctl","--user","show",unit,"-p","MainPID","--value"))
    require(pid>0,"relay not active")
    argv=Path(f"/proc/{pid}/cmdline").read_bytes().rstrip(b"\0").decode().split("\0")
    require(len(argv)>=11 and argv[:2]==["/usr/bin/python3","-B"] and argv[2].endswith("/tools/sse_pos_r299_optional_tls_rpc_relay.py") and argv[3]=="serve","unexpected running relay argv")
    opts={}
    tail=argv[4:]
    while tail:
        key=tail.pop(0)
        require(key in ("--bind","--cert","--key","--upstream-port","--allow-raw-send") and key not in opts,"unexpected relay argument")
        opts[key]=True if key=="--allow-raw-send" else tail.pop(0)
    require(set(opts)>={"--bind","--cert","--key","--upstream-port"},"incomplete relay arguments")
    require(opts["--bind"]=="fca0:2328:77e5:740c:ce60::1" and opts["--upstream-port"]=="28545","unexpected live relay bind/upstream")
    cert=Path(opts["--cert"]); key=Path(opts["--key"])
    require(cert.is_absolute() and key.is_absolute() and cert.is_file() and key.is_file(),"existing certificate/key unavailable")
    der=ssl.PEM_cert_to_DER_cert(cert.read_text())
    require(hashlib.sha256(der).hexdigest()=="967643892bf4eeb3028acd87ab8f849073d0e1ff6f93e122dae4640b69c03d3d","unexpected TLS identity")
    new=argv[:2]+[str(repo/"tools/sse_pos_r299_optional_tls_rpc_relay.py")]+argv[3:]
    require(all(re.fullmatch(r"[a-zA-Z0-9_./:@-]+",x) for x in new),"unsafe unit argument")
    require("--allow-raw-send" in new,"existing relay is read-only; separate raw-send authorization needed")
    drop=Path.home()/".config/systemd/user"/(unit+".d")/"90-v4-source.conf"
    require(not drop.exists() and not drop.is_symlink(),"existing override: inspect, do not overwrite")
    print(json.dumps({"service":unit,"oldSource":argv[2],"newSource":new[2],"sameTLS":True,"sameUpstream":True,"rawSendAlreadyEnabled":True},indent=2))
    if not args.apply:
        return
    require(input("Type UPGRADE-V4-RPC-RELAY to replace only this service source: ")=="UPGRADE-V4-RPC-RELAY","not approved")
    drop.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with drop.open("x") as f:
        f.write("[Service]\nExecStart=\nExecStart="+" ".join(new)+"\n")
    subprocess.run(["systemctl","--user","daemon-reload"],check=True)
    subprocess.run(["systemctl","--user","restart",unit],check=True)
    print("RELAY_RESTART_SUBMITTED=true; verify TLS RPC before activation")
if __name__=="__main__":
    main()
