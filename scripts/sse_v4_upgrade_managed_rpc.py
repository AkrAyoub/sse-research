#!/usr/bin/env python3
"""Update only an existing R299 user service, retaining its exact TLS trust.
Recognize and replace only our own prior override. Roll back on failed
health check. Never start, stop or change EL/CL/VC.
"""
import argparse,hashlib,json,os,re,ssl,subprocess,time,urllib.request
from pathlib import Path

FP="967643892bf4eeb3028acd87ab8f849073d0e1ff6f93e122dae4640b69c03d3d"
REMOTE="fca0:2328:77e5:740c:ce60::1"
ROOT=Path(__file__).resolve().parents[1]
def run(*argv):
    return subprocess.check_output(argv,text=True).strip()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def probe(mode):
    url="https://["+REMOTE+"]:19443/" if mode=="serve" else "http://127.0.0.1:28545/"
    ctx=ssl.create_default_context(cafile=str(ROOT/"release/chain31340-optional-rpc-vm4709.crt"))
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx))
    for method in ("eth_chainId","eth_blockNumber"):
        req=urllib.request.Request(url,data=json.dumps(dict(jsonrpc="2.0",id=1,method=method,params=[])).encode(),headers={"Content-Type":"application/json"})
        with opener.open(req,timeout=20) as f: result=json.load(f)["result"]
        require(result=="0x7a6c" if method=="eth_chainId" else int(result,16)>0,"unexpected RPC result")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("serve","client"),required=True)
    p.add_argument("--commit",required=True)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--allow-raw-send",action="store_true")
    a=p.parse_args()
    require(os.geteuid()!=0 and run("git","-C",str(ROOT),"rev-parse","HEAD")==a.commit and not run("git","-C",str(ROOT),"status","--porcelain"),"owner pinned clean source required")
    unit="sse-rpc-relay.service" if a.mode=="serve" else "sse-rpc-adapter.service"
    if a.mode=="serve": require(run("id","-un")=="ayoubakrvm4709","existing relay owner only")
    pid=int(run("systemctl","--user","show",unit,"-p","MainPID","--value"))
    require(pid>0,"service not running; inspect before upgrade")
    argv=Path("/proc/"+str(pid)+"/cmdline").read_bytes().rstrip(b"\0").decode().split("\0")
    require(argv[:2]==["/usr/bin/python3","-B"] and len(argv)>4 and argv[2].endswith("/tools/sse_pos_r299_optional_tls_rpc_relay.py") and argv[3]==a.mode,"unexpected service command")
    opts={}; tail=argv[4:]
    allowed={"--cert","--allow-raw-send"}|({"--bind","--key","--upstream-port"} if a.mode=="serve" else {"--remote","--fingerprint","--local-port"})
    while tail:
        k=tail.pop(0); require(k in allowed and k not in opts,"unexpected option")
        opts[k]=True if k=="--allow-raw-send" else tail.pop(0)
    require(hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(opts["--cert"]).read_text())).hexdigest()==FP,"unexpected TLS certificate")
    if a.mode=="serve":
        require(opts.get("--bind")==REMOTE and opts.get("--upstream-port")=="28545" and Path(opts["--key"]).is_file(),"unexpected server configuration")
    else:
        require(opts.get("--remote")==REMOTE and opts.get("--fingerprint")==FP and opts.get("--local-port","28545")=="28545","unexpected client configuration")
    new=argv[:2]+[str(ROOT/"tools/sse_pos_r299_optional_tls_rpc_relay.py")]+argv[3:]
    if a.allow_raw_send and "--allow-raw-send" not in new: new.append("--allow-raw-send")
    require("--allow-raw-send" in new,"existing read-only service requires explicit --allow-raw-send")
    require(all(re.fullmatch(r"[a-zA-Z0-9_./:@-]+",x) for x in new),"unsafe unit argument")
    drop=Path.home()/".config/systemd/user"/(unit+".d")/"90-v4-source.conf"
    require(not drop.is_symlink(),"linked override refused")
    old=drop.read_text() if drop.exists() else None
    if old is not None:
        require(old=="[Service]\nExecStart=\nExecStart="+" ".join(argv)+"\n","existing override differs from running reviewed service")
    print(json.dumps(dict(unit=unit,source=new[2],preserveTLS=True,rawSend=True,apply=a.apply)))
    if not a.apply:return
    drop.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    def write(content):
        tmp=drop.with_name(drop.name+".tmp")
        with tmp.open("x") as f:f.write(content)
        os.replace(tmp,drop)
    write("[Service]\nExecStart=\nExecStart="+" ".join(new)+"\n")
    try:
        run("systemctl","--user","daemon-reload")
        run("systemctl","--user","restart",unit)
        time.sleep(2)
        probe(a.mode)
    except Exception:
        if old is None: drop.unlink()
        else:write(old)
        run("systemctl","--user","daemon-reload")
        run("systemctl","--user","restart",unit)
        raise
    print("RPC_SERVICE_UPGRADE_VERIFIED=true")
if __name__=="__main__":main()
