#!/usr/bin/env python3
"""Upgrade existing participant loopback adapter, preserving pinned TLS trust.
Only RPC adapter restart, not native clients or V3 agents.
"""
import argparse
import hashlib
from pathlib import Path
import os
import re
import ssl
import subprocess
import json

def run(*cmd):
    return subprocess.check_output(cmd,text=True).strip()

def require(ok,msg):
    if not ok:
        raise RuntimeError(msg)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-sha",required=True)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    require(os.geteuid()!=0 and run("git","-C",str(repo),"rev-parse","HEAD")==args.source_sha and not run("git","-C",str(repo),"status","--porcelain"),"pinned clean owner source required")
    unit="sse-rpc-adapter.service"
    pid=int(run("systemctl","--user","show",unit,"-p","MainPID","--value"))
    require(pid>0,"adapter not running")
    argv=Path(f"/proc/{pid}/cmdline").read_bytes().rstrip(b"\0").decode().split("\0")
    require(len(argv)>=12 and argv[:2]==["/usr/bin/python3","-B"] and argv[2].endswith("/tools/sse_pos_r299_optional_tls_rpc_relay.py") and argv[3]=="client","unexpected client argv")
    opts={}
    tail=argv[4:]
    while tail:
        key=tail.pop(0)
        require(key in ("--remote","--cert","--fingerprint","--local-port","--allow-raw-send") and key not in opts,"unexpected adapter argument")
        opts[key]=True if key=="--allow-raw-send" else tail.pop(0)
    fp="967643892bf4eeb3028acd87ab8f849073d0e1ff6f93e122dae4640b69c03d3d"
    require(opts.get("--remote")=="fca0:2328:77e5:740c:ce60::1" and opts.get("--fingerprint")==fp and opts.get("--local-port","28545")=="28545","unexpected adapter configuration")
    require(hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(opts["--cert"]).read_text())).hexdigest()==fp,"certificate pin mismatch")
    require(opts.get("--allow-raw-send") is True,"old adapter is read-only; explicit owner review needed")
    new=argv[:2]+[str(repo/"tools/sse_pos_r299_optional_tls_rpc_relay.py")]+argv[3:]
    require(all(re.fullmatch(r"[a-zA-Z0-9_./:@-]+",x) for x in new),"unsafe unit argument")
    print(json.dumps({"service":unit,"oldSource":argv[2],"newSource":new[2],"sameTLS":True,"rawSendAlreadyEnabled":True},indent=2))
    if not args.apply:
        return
    if argv==new:
        subprocess.run(["systemctl","--user","restart",unit],check=True)
        return
    drop=Path.home()/".config/systemd/user"/(unit+".d")/"90-v4-source.conf"
    require(not drop.exists() and not drop.is_symlink(),"existing override; inspect")
    drop.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with drop.open("x") as f:
        f.write("[Service]\nExecStart=\nExecStart="+" ".join(new)+"\n")
    subprocess.run(["systemctl","--user","daemon-reload"],check=True)
    subprocess.run(["systemctl","--user","restart",unit],check=True)

if __name__=="__main__":
    main()
