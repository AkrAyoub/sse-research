#!/usr/bin/env python3
"""Owner-assisted original-chain checkpoint export, cross-check and VM4721 repair.
Public SSZ only; no validator keys, no Engine API publishing, no WS bypass.
The receiving owner must independently compare the checkpoint root/state root
on a second established node before authorizing import. No independent operator
claim: both sources may be controlled by the same owner.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import sse_pos_r59_native_ipv6_observer as r59

GENESIS="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
EL_GENESIS="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
BN="http://127.0.0.1:25052"
LIMIT=64*1024*1024
SOURCE="fca0:2328:77b8:6578:a55::1"
PORT=19444
FILES=("manifest.json","state.ssz","block.ssz")
HASH=re.compile(r"0x[0-9a-f]{64}")

def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def get(url,accept="application/json",limit=LIMIT):
    req=urllib.request.Request(url,headers={"Accept":accept})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=90) as r:
        data=r.read(limit+1)
        require(len(data)<=limit and len(data)>0,"response exceeds bound or empty")
        return data
def j(path):
    return json.loads(get(BN+path))
def local_genesis():
    require(j("/eth/v1/beacon/genesis")["data"]["genesis_validators_root"]==GENESIS,"wrong local beacon genesis")
    cl=j("/eth/v1/node/syncing")["data"]
    require(cl["is_syncing"] is False and cl["is_optimistic"] is False and cl.get("el_offline") is False,"source CL not synced/verified")
def anchor(epoch=None):
    local_genesis()
    f=j("/eth/v1/beacon/states/head/finality_checkpoints")["data"]["finalized"]
    current=int(f["epoch"])
    e=current if epoch is None else epoch
    require(0<e<=current and current-e<=2,"checkpoint not recent finalized epoch")
    slot=e*32
    h=j("/eth/v1/beacon/headers/"+str(slot))
    require(h.get("execution_optimistic") is False and h.get("finalized") is True,"header not finalized/verified")
    d=h["data"]
    require(d["canonical"] and int(d["header"]["message"]["slot"])==slot,"checkpoint must have actual epoch-boundary block")
    root=d["root"]; state=d["header"]["message"]["state_root"]
    require(HASH.fullmatch(root) and HASH.fullmatch(state),"invalid roots")
    if epoch is None: require(root==f["root"],"finalized root mismatch")
    b=j("/eth/v2/beacon/blocks/"+root)
    require(b.get("execution_optimistic") is False and b.get("finalized") is True,"block not finalized")
    require(not b["data"]["message"]["body"].get("blob_kzg_commitments",[]),"blob-bearing checkpoint unsupported; choose other recent checkpoint")
    return dict(chainId=31340,genesisValidatorsRoot=GENESIS,epoch=e,slot=slot,blockRoot=root,stateRoot=state)
def export(out):
    require(os.geteuid()!=0,"unprivileged source owner required")
    a=anchor()
    out.mkdir(mode=0o700,parents=False,exist_ok=False)
    data={"state.ssz":get(BN+"/eth/v2/debug/beacon/states/"+str(a["slot"]),"application/octet-stream"),
          "block.ssz":get(BN+"/eth/v2/beacon/blocks/"+a["blockRoot"],"application/octet-stream")}
    for name,raw in data.items(): (out/name).write_bytes(raw)
    a.update(schema="SSE_V4_CHECKPOINT_V1",capturedAt=int(time.time()),
             sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in data.items()})
    (out/"manifest.json").write_text(json.dumps(a,indent=2)+"\n")
    print(json.dumps(a,indent=2),flush=True)
def serve(out):
    require(os.geteuid()!=0,"unprivileged server")
    _,ip=r59.overlay_ip()
    require(ip==SOURCE,"unexpected checkpoint source overlay")
    raw={name:(out/name).read_bytes() for name in FILES}
    require(all(0<len(x)<=LIMIT for x in raw.values()),"bad export size")
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            name=self.path.removeprefix("/")
            if name not in raw: self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type","application/json" if name=="manifest.json" else "application/octet-stream")
            self.send_header("Content-Length",str(len(raw[name])))
            self.end_headers()
            self.wfile.write(raw[name])
        def setup(self):
            super().setup(); self.connection.settimeout(15)
    class S(ThreadingHTTPServer):
        address_family=socket.AF_INET6
        daemon_threads=True
    print("PUBLIC_CHECKPOINT_ONLY_SERVER_READY",flush=True)
    S((ip,PORT),H).serve_forever()
def docker(*args):
    return subprocess.check_output(["docker",*args],text=True).strip()
def repair(epoch,root,state,apply):
    require(os.geteuid()==0 and os.environ.get("SUDO_USER")=="ayoubakrvm4721","VM4721 owner sudo only")
    require(HASH.fullmatch(root) and HASH.fullmatch(state) and epoch>0,"invalid approved checkpoint")
    prefix="sse31340-r137-node-afb8575330a787b6fd90"
    bn=prefix+"-bn"; el=prefix+"-el"
    base=Path("/root/.local/share/sse-r137-node-afb8575330a787b6fd90")
    old=json.loads(docker("inspect",bn))[0]; exe=json.loads(docker("inspect",el))[0]
    require(old["Image"]==r59.LIGHTHOUSE_ID and exe["Image"]==r59.BESU_ID and exe["State"]["Running"],"unexpected native clients")
    require(old["Config"]["Cmd"].count("--allow-insecure-genesis-sync")==1,"unexpected old BN args")
    require(old["Config"]["Entrypoint"]==["lighthouse"],"unexpected old BN entrypoint")
    require(not any(re.search(r"validator|[-_]vc([_-]|$)",n,re.I) for n in docker("ps","-a","--format","{{.Names}}").splitlines()),"possible signer: no recovery")
    require(all(not p.is_symlink() and p.exists() for p in (base,base/"testnet",base/"engine.jwt",base/"beacon")),"existing mounts absent")
    require(set((x["Source"],x["Destination"],x["RW"]) for x in old["Mounts"])==
            {(str(base/"testnet"),"/testnet",False),(str(base/"engine.jwt"),"/jwt/engine.jwt",False),(str(base/"beacon"),"/data",True)},"unexpected existing mounts")
    dst=base/("checkpoint-"+str(epoch))
    newdata=base/("beacon-checkpoint-"+str(epoch))
    backup=bn+"-pre-checkpoint"
    require(not dst.exists() and not newdata.exists() and backup not in docker("ps","-a","--format","{{.Names}}").splitlines(),"existing attempt; inspect, never overwrite")
    url=f"http://[{SOURCE}]:{PORT}/"
    m=json.loads(get(url+"manifest.json",limit=65536))
    require(m.get("schema")=="SSE_V4_CHECKPOINT_V1" and m["chainId"]==31340 and m["genesisValidatorsRoot"]==GENESIS
            and m["epoch"]==epoch and m["slot"]==epoch*32 and m["blockRoot"]==root and m["stateRoot"]==state,"checkpoint differs from separately approved roots")
    require(0<=time.time()-m["capturedAt"]<1800,"export expired")
    data={name:get(url+name,"application/octet-stream") for name in FILES[1:]}
    require(all(hashlib.sha256(raw).hexdigest()==m["sha256"][name] for name,raw in data.items()),"checkpoint file digest mismatch")
    # Verify the local execution genesis without contacting a remote RPC.
    req=urllib.request.Request("http://127.0.0.1:28545",data=b'{"jsonrpc":"2.0","id":1,"method":"eth_getBlockByNumber","params":["0x0",false]}',headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=15) as r:
        require(json.load(r)["result"]["hash"]==EL_GENESIS,"wrong EL genesis")
    print(json.dumps(dict(checkpoint=m,oldBeaconPreserved=True,newBeaconDirectory=str(newdata),executionUnchanged=True),indent=2),flush=True)
    if not apply: return
    require(input("Type RESTORE-NONSIGNING-CHECKPOINT to authorize: ")=="RESTORE-NONSIGNING-CHECKPOINT","not authorized")
    dst.mkdir(mode=0o700); newdata.mkdir(mode=0o700)
    for name,raw in data.items(): (dst/name).write_bytes(raw)
    (dst/"manifest.json").write_text(json.dumps(m,indent=2))
    args=[x for x in old["Config"]["Cmd"] if x!="--allow-insecure-genesis-sync"]
    replacements={"--port6=9000":"--port=9000","--discovery-port6=9000":"--discovery-port=9000","--quic-port6=9001":"--quic-port=9001"}
    args=[replacements.get(x,x) for x in args]
    args+=["--checkpoint-state=/checkpoint/state.ssz","--checkpoint-block=/checkpoint/block.ssz","--weak-subjectivity-checkpoint="+root+":"+str(epoch)]
    ports=old["HostConfig"]["PortBindings"]
    pub=[]
    for container,binds in ports.items():
        for b in binds:
            ip=b["HostIp"]; ip="["+ip+"]" if ":" in ip else ip
            pub+=["--publish",ip+":"+b["HostPort"]+":"+container]
    network=old["HostConfig"]["NetworkMode"]
    require(network==prefix,"unexpected native network")
    docker("update","--restart=no",bn)
    docker("stop",bn)
    docker("rename",bn,backup)
    docker("run","-d","--pull","never","--platform","linux/amd64","--name",bn,"--hostname",bn,
           "--restart","unless-stopped","--stop-timeout","60","--init","--network",network,
           "--user","0:0","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges",
           "--cpus","1.5","--memory","4g","--pids-limit","384","--tmpfs","/tmp:rw,nosuid,noexec,size=256m",
           "--mount",f"type=bind,source={base/'testnet'},target=/testnet,readonly",
           "--mount",f"type=bind,source={base/'engine.jwt'},target=/jwt/engine.jwt,readonly",
           "--mount",f"type=bind,source={newdata},target=/data",
           "--mount",f"type=bind,source={dst},target=/checkpoint,readonly",
           *pub,"--entrypoint","lighthouse",r59.LIGHTHOUSE_REF,*args)
    print("CHECKPOINT_BEACON_SUBMITTED=true; verify loaded root, synchronization and finality")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    ex=sub.add_parser("export"); ex.add_argument("--out",type=Path,required=True)
    se=sub.add_parser("serve"); se.add_argument("--out",type=Path,required=True)
    ck=sub.add_parser("check"); ck.add_argument("--epoch",type=int,required=True)
    re=sub.add_parser("repair"); re.add_argument("--epoch",type=int,required=True); re.add_argument("--root",required=True); re.add_argument("--state-root",required=True); re.add_argument("--apply",action="store_true")
    a=p.parse_args()
    if a.mode=="export": export(a.out)
    elif a.mode=="serve": serve(a.out)
    elif a.mode=="check": print(json.dumps(anchor(a.epoch),indent=2))
    else: repair(a.epoch,a.root,a.state_root,a.apply)
if __name__=="__main__": main()
