#!/usr/bin/env python3
"""V3 public dashboard discovery. No signing or privileged routes."""
import argparse,json,re,subprocess,sys
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler
UNIT="sse-v3-public-dashboard.service"
LOCAL="http://127.0.0.1:8770"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def cmd(*a):return subprocess.check_output(a,text=True,timeout=10).strip()
def current_url():
    if cmd("systemctl","--user","is-active",UNIT)!="active":raise ValueError("publisher inactive")
    inv=cmd("systemctl","--user","show",UNIT,"-p","InvocationID","--value")
    if not re.fullmatch("[0-9a-f]{32}",inv) or int(inv,16)==0:raise ValueError("no current invocation")
    logs=cmd("journalctl","--user","-b","-u",UNIT,"_SYSTEMD_INVOCATION_ID="+inv,"--no-pager","-o","cat","-n","200")
    urls=re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com(?=[\s|]|$)",logs)
    if not urls:raise ValueError("no current URL")
    return urls[-1]
def fetch(base):
    with build_opener(ProxyHandler({}),NoRedirect()).open(base+"/v2/status",timeout=30) as r:
        raw=r.read(2**20+1)
        if len(raw)>2**20:raise ValueError("response too large")
        d=json.loads(raw)
    v=d["marketV3"]
    if v["deployment"]["chainId"]!=31340 or "error" in v:raise ValueError("wrong market")
    return d
def main():
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("status","dashboard","logs"))
    a=p.parse_args()
    if a.operation=="logs":
        return subprocess.call(["journalctl","--user","-b","-u","sse-v3-console.service","-u",UNIT,"--no-pager","-n","80"])
    try:
        local=fetch(LOCAL)
        if a.operation=="status":print(json.dumps(local,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("Local dashboard unavailable:",e,file=sys.stderr);return 2
    try:
        url=current_url()
        remote=fetch(url)
        for k in ("nodeId","declaredRoles"):
            if remote[k]!=local[k]:raise ValueError("public node mismatch")
        for k in ("chainId","market","ledger"):
            if remote["marketV3"]["deployment"][k]!=local["marketV3"]["deployment"][k]:raise ValueError("public deployment mismatch")
        if current_url()!=url:raise ValueError("publisher changed during verification")
        print("Public dashboard:",url)
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
        print("Public HTTPS not verified:",e,file=sys.stderr)
        print("Local dashboard:",LOCAL)
        return 3
if __name__=="__main__":raise SystemExit(main())
