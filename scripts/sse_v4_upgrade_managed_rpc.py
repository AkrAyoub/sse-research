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
def parse_existing(argv,mode,home):
    """Recognize the R299 script with optional -B / venv interpreter.
    Actual interpreter identity is checked separately via /proc/PID/exe.
    """
    require(len(argv)>=4 and Path(argv[0]).name in ("python","python3","python3.12"),"unexpected Python invocation")
    i=2 if argv[1]=="-B" else 1
    require(len(argv)>i+1 and argv[i+1]==mode,"unexpected service mode")
    script=Path(argv[i])
    require(script.is_absolute() and script.name=="sse_pos_r299_optional_tls_rpc_relay.py"
            and script.parent.name=="tools" and script.resolve().is_relative_to(home.resolve()),
            "unexpected service script; no migration")
    opts={}; tail=list(argv[i+2:])
    allowed={"--cert","--allow-raw-send"}|({"--bind","--key","--upstream-port"} if mode=="serve" else {"--remote","--fingerprint","--local-port"})
    while tail:
        k=tail.pop(0)
        require(k in allowed and k not in opts,"unexpected or duplicate service option")
        require(k=="--allow-raw-send" or bool(tail),"missing option value")
        opts[k]=True if k=="--allow-raw-send" else tail.pop(0)
    require("--cert" in opts,"no pinned certificate")
    return opts,argv[i+1:]

def probe(mode):
    url="https://["+REMOTE+"]:19443/" if mode=="serve" else "http://127.0.0.1:28545/"
    ctx=ssl.create_default_context(cafile=str(ROOT/"release/chain31340-optional-rpc-vm4709.crt"))
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ctx))
    for method,params in (("eth_chainId",[]),("eth_blockNumber",[]),("eth_getBlockByNumber",["0x0",False])):
        req=urllib.request.Request(url,data=json.dumps(dict(jsonrpc="2.0",id=1,method=method,params=params)).encode(),headers={"Content-Type":"application/json"})
        with opener.open(req,timeout=20) as f: result=json.load(f)["result"]
        expected={"eth_chainId":lambda x:x=="0x7a6c","eth_blockNumber":lambda x:int(x,16)>0,
                  "eth_getBlockByNumber":lambda x:x["hash"]=="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"}
        require(expected[method](result),"unexpected RPC result")
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
    require(Path("/proc/"+str(pid)+"/exe").resolve()==Path("/usr/bin/python3").resolve(),"unexpected running Python executable")
    opts,tail=parse_existing(argv,a.mode,Path.home())
    require(hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(opts["--cert"]).read_text())).hexdigest()==FP,"unexpected TLS certificate")
    if a.mode=="serve":
        require(opts.get("--bind")==REMOTE and opts.get("--upstream-port")=="28545" and Path(opts["--key"]).is_file(),"unexpected server configuration")
    else:
        require(opts.get("--remote")==REMOTE and opts.get("--fingerprint")==FP and opts.get("--local-port","28545")=="28545","unexpected client configuration")
    new=["/usr/bin/python3","-B",str(ROOT/"tools/sse_pos_r299_optional_tls_rpc_relay.py")]+tail
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
    if a.mode=="client": probe("serve")  # verify pinned upstream before changing a legacy service
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
        for attempt in range(3):
            try:
                probe(a.mode)
                break
            except Exception:
                if attempt==2: raise
                time.sleep(3)
    except Exception:
        if old is None: drop.unlink()
        else:write(old)
        run("systemctl","--user","daemon-reload")
        run("systemctl","--user","restart",unit)
        raise
    print("RPC_SERVICE_UPGRADE_VERIFIED=true")
if __name__=="__main__":main()
