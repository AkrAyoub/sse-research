#!/usr/bin/env python3
"""Read-only native consensus evidence collector. No signing or RPC writes.
Archive per observed finalized checkpoint; unavailable rewards remain unknown.
"""
import argparse
import json
import os
import time
import tempfile
import fcntl
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BN = "http://127.0.0.1:25052"
EL = "http://127.0.0.1:28545"

def query(base, path="", body=None):
    req = Request(base+path, data=None if body is None else json.dumps(body).encode(),
                  headers={"Content-Type":"application/json"})
    with urlopen(req, timeout=20) as response:
        return json.load(response)

def rpc(method, params):
    r = query(EL, body={"jsonrpc":"2.0","id":1,"method":method,"params":params})
    if "error" in r:
        raise ValueError(str(r["error"]))
    return r["result"]

def optional(fn):
    try:
        return {"available":True,"response":fn()}
    except HTTPError as e:
        return {"available":False,"httpStatus":e.code}
    except (OSError,ValueError) as e:
        return {"available":False,"errorType":type(e).__name__}

def collect(previous_slot=None):
    if int(rpc("eth_chainId",[]),16)!=31340:
        raise ValueError("wrong chain")
    genesis=rpc("eth_getBlockByNumber",["0x0",False])
    if genesis["hash"].lower()!="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf":
        raise ValueError("wrong genesis")
    cp=query(BN,"/eth/v1/beacon/states/head/finality_checkpoints")
    final=cp["data"]["finalized"]
    epoch=int(final["epoch"])
    header=query(BN,"/eth/v1/beacon/headers/"+final["root"])["data"]
    if header["root"].lower()!=final["root"].lower() or not header["canonical"]:
        raise ValueError("finalized checkpoint header mismatch")
    state_root=header["header"]["message"]["state_root"]
    validators=query(BN,"/eth/v1/beacon/states/"+state_root+"/validators")
    ids=[v["index"] for v in validators["data"] if v["status"].startswith("active_")]
    if not ids:
        raise ValueError("no active validators")
    rewards={}
    for e in range(max(0,epoch-2),epoch+1):
        rewards[str(e)]=optional(lambda e=e:query(BN,"/eth/v1/beacon/rewards/attestations/"+str(e),ids))
    head=query(BN,"/eth/v1/beacon/headers/head")["data"]["header"]["message"]
    slot=int(head["slot"])
    blocks={}
    start=max(0,slot-3) if previous_slot is None else max(0,slot-31,min(previous_slot-3,slot-3))
    for s in range(start,slot+1):
        def block_reward(s=s):
            h=query(BN,"/eth/v1/beacon/headers/"+str(s))
            if not h["data"]["canonical"]:
                raise ValueError("noncanonical block header")
            root=h["data"]["root"]
            return {"header":h,"reward":query(BN,"/eth/v1/beacon/rewards/blocks/"+root)}
        entry=optional(block_reward)
        if entry["available"]:
            pair=entry["response"]
            entry={"available":True,"response":pair["reward"],"header":pair["header"]}
        blocks[str(s)]=entry
    return {"schema":"SSE_NATIVE_REWARD_OBSERVATION_V1","chainId":31340,
            "observedUnixNs":time.time_ns(),"checkpoints":cp,
            "finalizedHeader":header,"finalizedValidators":validators,"attestationRewards":rewards,
            "recentBlockRewards":blocks,"headSlot":slot,"collectionStartSlot":start,
            "gapBeforeStart":previous_slot is not None and start>previous_slot+1,
            "executionFinalized":rpc("eth_getBlockByNumber",["finalized",False])}

def summarize(d):
    rows=[]
    for epoch,entry in d["attestationRewards"].items():
        if not entry["available"]:
            rows.append({"epoch":epoch,**entry})
            continue
        r=entry["response"]
        for v in r["data"]["total_rewards"]:
            rows.append({"epoch":epoch,"validator":v["validator_index"],
                         "netGwei":sum(int(v[k]) for k in ("head","source","target","inactivity")),
                         "apiFinalized":r.get("finalized")})
    return {"headSlot":d["headSlot"],"finalizedEpoch":d["checkpoints"]["data"]["finalized"]["epoch"],
            "attestationRewards":rows,
            "blockRewards":[{"slot":s,**({"proposer":e["response"]["data"]["proposer_index"],
                "totalGwei":e["response"]["data"]["total"],"apiFinalized":e["response"].get("finalized")}
                if e["available"] else e)} for s,e in d["recentBlockRewards"].items()]}

def archive(root,d):
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink() or root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("private owner archive required")
    path=root/("native-"+str(d["observedUnixNs"])+".json")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(d,f,separators=(",",":"))
        f.flush()
        os.fsync(f.fileno())
    return path

def atomic_json(path,value):
    fd,tmp=tempfile.mkstemp(prefix=".native-",dir=path.parent)
    try:
        with os.fdopen(fd,"w") as f:
            json.dump(value,f,separators=(",",":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def compact(d):
    for entry in d["attestationRewards"].values():
        if entry["available"]:
            entry["response"]["data"].pop("ideal_rewards",None)
    return d

def tick(root,limit=2048):
    if not 16<=limit<=100000:
        raise ValueError("retention must be 16..100000 snapshots")
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink() or root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("private owner archive required")
    fd=os.open(root/".collector.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cursor=root/"cursor.json"
        prev=json.loads(cursor.read_text())["headSlot"] if cursor.exists() else None
        d=compact(collect(prev))
        result=summarize(d)
        result["gapBeforeStart"]=d["gapBeforeStart"]
        result["observedUnixNs"]=d["observedUnixNs"]
        dest=root/("sample-"+str(d["observedUnixNs"])+".json")
        atomic_json(dest,d)
        atomic_json(root/"latest.json",result)
        atomic_json(cursor,{"headSlot":d["headSlot"]})
        samples=sorted((p for p in root.glob("sample-*.json")
                        if p.stem[7:].isdigit() and p.is_file() and not p.is_symlink()),
                       key=lambda p:int(p.stem[7:]))
        for p in samples[:-limit]:
            p.unlink()
        return {"headSlot":d["headSlot"],"finalizedEpoch":result["finalizedEpoch"],
                "gapBeforeStart":d["gapBeforeStart"],"archive":str(dest)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=Path.home()/".local/share/sse-native-rewards")
    p.add_argument("--tick",action="store_true")
    p.add_argument("--retain",type=int,default=2048)
    a=p.parse_args()
    if a.tick:
        print(json.dumps(tick(a.output,a.retain)))
        return
    d=collect()
    result=summarize(d)
    result["archive"]=str(archive(a.output,d))
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
