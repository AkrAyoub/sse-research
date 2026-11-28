#!/usr/bin/env python3
"""Publish only a separate V4 public console via a pinned Cloudflare quick tunnel.

Explicit --apply authorizes public chain views and unsigned intent preparation.
No wallet policy changes, signer startup, native changes, RPC exposure or
private console forwarding. Quick tunnel URLs are temporary; status rechecks
the live process and external identity. No promise of permanent availability.
"""
import argparse,hashlib,json,os,re,secrets,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()
CONFIG=HOME/".config/sse-v4"
UNITS=HOME/".config/systemd/user"
BIN=HOME/".local/bin/cloudflared"
PY=HOME/".venvs/sse-v4/bin/python"
CONSOLE="sse-v4-console-public.service"
TUNNEL="sse-v4-web-dashboard.service"
DIGEST="56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf"
DOWNLOAD="https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64"
URL=re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def run(*cmd):
    return subprocess.check_output(cmd,text=True,timeout=30).strip()
def active(name):
    return subprocess.run(["systemctl","--user","is-active","--quiet",name]).returncode==0
def write(path,text):
    require(not path.is_symlink(),"linked file refused")
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".sse-web-")
    try:
        with os.fdopen(fd,"w") as f:f.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def identity():
    p=CONFIG/"public-instance"
    require(p.is_file() and not p.is_symlink(),"public instance not configured")
    v=p.read_text().strip()
    require(re.fullmatch(r"[0-9a-f]{32}",v),"invalid instance")
    return v
def read_json(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","Cache-Control":"no-cache"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=8) as r:
        require(r.status==200 and r.geturl()==url,"unexpected redirect/status")
        return json.loads(r.read(65537))
def verify(url,instance):
    require(read_json(url+"/api/mode")=={"mode":"public"},"not public console")
    require(read_json(url+"/api/public-instance")=={"instance":instance,"chainId":31340},"wrong public instance")
def current_url():
    require(active(CONSOLE) and active(TUNNEL),"web services inactive")
    pid=run("systemctl","--user","show",TUNNEL,"-p","MainPID","--value")
    require(pid.isdigit() and int(pid)>0,"no tunnel pid")
    logs=run("journalctl","--user","-u",TUNNEL,"_PID="+pid,"-n","100","--no-pager","-o","cat")
    urls=URL.findall(logs)
    require(bool(urls),"current tunnel URL not announced")
    url=urls[-1]
    verify(url,identity())
    return url
def ensure_bin():
    require(not BIN.is_symlink(),"linked cloudflared binary")
    if not BIN.exists():
        BIN.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"cloudflared"
            subprocess.run(["curl","-fL","--proto","=https","--proto-redir","=https","--max-time","180",DOWNLOAD,"-o",str(target)],check=True)
            require(hashlib.sha256(target.read_bytes()).hexdigest()==DIGEST,"download digest mismatch")
            subprocess.run(["install","-m","700",str(target),str(BIN)],check=True)
    require(BIN.is_file() and BIN.stat().st_uid==os.getuid() and hashlib.sha256(BIN.read_bytes()).hexdigest()==DIGEST,"existing binary not reviewed pin; preserve")
class Pending(RuntimeError): pass

def wait_url(seconds):
    deadline=time.monotonic()+seconds
    while True:
        try: return current_url()
        except Exception:
            if time.monotonic()>=deadline: raise Pending("tunnel active but external HTTPS not verified")
            time.sleep(min(3,max(0,deadline-time.monotonic())))

def apply(seconds=180):
    require(os.geteuid()!=0 and run("uname","-m")=="x86_64","unprivileged amd64 owner required")
    require(not run("git","-C",str(ROOT),"status","--porcelain"),"clean pinned source required")
    require(PY.is_file() and active("sse-v4-console.service"),"local V4 preparation required")
    for p in (HOME/".local",BIN.parent,HOME/".config",CONFIG,UNITS.parent,UNITS):
        require(not p.is_symlink(),"linked directory refused")
    require(CONFIG.is_dir() and CONFIG.stat().st_uid==os.getuid() and not CONFIG.stat().st_mode&0o077,"private config required")
    for p in (PY,ROOT,BIN,HOME):
        require(re.fullmatch(r"/[a-zA-Z0-9_./-]+",str(p)),"unsupported service path")
    # Reuse verified local RPC selection from the installer without changing wallets.
    sys.path.insert(0,str(ROOT/"scripts"))
    import sse_v4_app_install as app
    import sse_v4_state as st
    from sse_chain_read import LocalRPC
    rpc=app.pick_rpc(st.load_manifest(app.MANIFEST),lambda u:LocalRPC(u,timeout=20).request)
    instance_file=CONFIG/"public-instance"
    if not instance_file.exists() and not instance_file.is_symlink():
        fd=os.open(instance_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:f.write(secrets.token_hex(16)+"\n")
    instance=identity()
    ensure_bin()
    # Never pass private state or keystore paths to this public process.
    console="[Unit]\nDescription=SSE V4 public web console\n[Service]\nExecStart="+str(PY)+" -B "+str(ROOT/"tools/sse_v4_console.py")+" --manifest "+str(app.MANIFEST)+" --rpc "+rpc+" --mode public --port 8791 --public-instance "+instance+"\nRestart=on-failure\nRestartSec=10\nNoNewPrivileges=yes\nUMask=0077\n[Install]\nWantedBy=default.target\n"
    tunnel="[Unit]\nDescription=SSE V4 public HTTPS quick tunnel\nAfter="+CONSOLE+"\nRequires="+CONSOLE+"\n[Service]\nExecStart="+str(BIN)+" tunnel --url http://127.0.0.1:8791 --no-autoupdate\nRestart=always\nRestartSec=10\nNoNewPrivileges=yes\nUMask=0077\n[Install]\nWantedBy=default.target\n"
    target=UNITS/TUNNEL
    if target.exists(): require(not target.is_symlink() and target.read_text()==tunnel,"existing tunnel differs; preserve")
    old=UNITS/CONSOLE
    if old.exists(): require(not old.is_symlink() and "--mode public --port 8791" in old.read_text() and "sse_v4_console.py" in old.read_text(),"unexpected existing public service")
    write(old,console)
    if not target.exists():write(target,tunnel)
    run("systemctl","--user","daemon-reload")
    run("systemctl","--user","enable","--now",CONSOLE)
    run("systemctl","--user","restart",CONSOLE)
    for i in range(12):
        try:verify("http://127.0.0.1:8791",instance);break
        except Exception:time.sleep(2)
    else:raise RuntimeError("public-mode local console not verified; no new tunnel started")
    run("systemctl","--user","enable","--now",TUNNEL)
    url=wait_url(seconds)
    print("PUBLIC_DASHBOARD_URL="+url,flush=True)
    print("PUBLIC_DASHBOARD_HTTPS_VERIFIED=true",flush=True)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply",action="store_true");g.add_argument("--status",action="store_true")
    p.add_argument("--wait-seconds",type=int,default=180,help="bounded external readiness wait")
    a=p.parse_args()
    if not 0<=a.wait_seconds<=300: p.error("wait must be 0..300")
    try:
        if a.apply:apply(a.wait_seconds)
        else:
            print("PUBLIC_DASHBOARD_URL="+wait_url(a.wait_seconds))
            print("PUBLIC_DASHBOARD_HTTPS_VERIFIED=true")
    except Pending as e:
        if active(CONSOLE) and active(TUNNEL):
            print("PUBLIC_DASHBOARD_PENDING: "+str(e),file=sys.stderr)
            return 3
        print("PUBLIC_DASHBOARD_NOT_VERIFIED: services inactive",file=sys.stderr)
        return 2
    except Exception as e:
        print("PUBLIC_DASHBOARD_NOT_VERIFIED: "+str(e),file=sys.stderr)
        return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
