#!/usr/bin/env python3
"""Install persistent V3 public console from an existing verified checkout.
Does not install a chain or change wallet, RPC, validator or tunnel services.
"""
import argparse,os,re,subprocess,sys
from pathlib import Path
def run(*args):subprocess.run(args,check=True)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node-id",required=True)
    p.add_argument("--roles",required=True)
    p.add_argument("--el",default="http://127.0.0.1:28545")
    p.add_argument("--bn")
    p.add_argument("--port",type=int,default=8770)
    p.add_argument("--manifest",type=Path)
    a=p.parse_args()
    if os.getuid()==0:raise ValueError("run as node owner")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",a.node_id):raise ValueError("invalid node ID")
    roles=a.roles.split(",")
    if not roles or not set(roles)<={"observer","full_node","validator","consumer","provider","monitor","rpc","dashboard","logs"}:raise ValueError("invalid roles")
    if not 1024<=a.port<=65535:raise ValueError("invalid port")
    root=Path(__file__).resolve().parents[1]
    app=root/"services/node-console/v2_status_app.py"
    args=[sys.executable,"-B",str(app),"--node-id",a.node_id,"--roles",a.roles,"--el",a.el,"--market-v3","--port",str(a.port),"--public-readonly","--serve"]
    if a.bn:args+=["--bn",a.bn,"--block-explorer"]
    if a.manifest:args+=["--v2-manifest",str(a.manifest.resolve())]
    for arg in args:
        if not re.fullmatch(r"[A-Za-z0-9_./,:@+=-]+",arg):raise ValueError("unsafe unit argument")
    run(*[x for x in args if x!="--serve"])
    # Persistence requires a user manager that survives logout.
    uid=str(os.getuid())
    def linger():
        return subprocess.check_output(["loginctl","show-user",uid,"-p","Linger","--value"],text=True).strip()=="yes"
    if not linger():
        attempt=subprocess.run(["loginctl","enable-linger",uid],check=False)
        if attempt.returncode!=0 or not linger():
            raise ValueError("cannot enable user linger; host administrator must authorize this prerequisite")
    if not linger():raise ValueError("user linger not enabled")

    unit=Path.home()/".config/systemd/user/sse-v3-console.service"
    unit.parent.mkdir(parents=True,exist_ok=True)
    body="[Unit]\nDescription=SSE V3 public marketplace console\nAfter=network-online.target\n\n[Service]\nType=simple\nExecStart="+" ".join(args)+"\nRestart=on-failure\nRestartSec=5\nUMask=0077\nNoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n"
    if unit.exists() or unit.is_symlink():
        if unit.is_symlink() or not unit.is_file() or unit.stat().st_uid!=os.getuid() or unit.read_text()!=body:
            raise ValueError("existing unit differs; preserve it and review upgrade")
    else:
        fd=os.open(unit,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as f:f.write(body)
    run("systemctl","--user","daemon-reload")
    run("systemctl","--user","enable","--now",unit.name)
    run("systemctl","--user","is-active",unit.name)
    print("SSE_V3_CONSOLE_SERVICE_ENABLED=true")
    import time
    from urllib.request import urlopen
    for i in range(30):
        try:
            with urlopen("http://127.0.0.1:"+str(a.port)+"/healthz",timeout=2) as response:
                import json
                health=json.loads(response.read(8192))
                if response.status==200 and health.get("alive") is True:break
        except (OSError,ValueError):pass
        time.sleep(1)
    else:raise ValueError("dashboard readiness check failed; inspect service journal")
    print("SSE_V3_CONSOLE_HTTP_READY=true")
    print("LOCAL_DASHBOARD=http://127.0.0.1:"+str(a.port))
    print("LINGER_STATUS:")
    run("loginctl","show-user",str(os.getuid()),"-p","Linger")
if __name__=="__main__":main()
