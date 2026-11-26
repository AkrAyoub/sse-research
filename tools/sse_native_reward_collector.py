#!/usr/bin/env python3
"""Read-only native consensus evidence collector. No signing or RPC writes.
Archive per observed finalized checkpoint; unavailable rewards remain unknown.
"""
import argparse
import json
import os
import time
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

def collect():
    if int(rpc("eth_chainId",[]),16)!=31340:
        raise ValueError("wrong chain")
    genesis=rpc("eth_getBlockByNumber",["0x0",False])
    if genesis["hash"].lower()!="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf":
        raise ValueError("wrong genesis")
    cp=query(BN,"/eth/v1/beacon/states/head/finality_checkpoints")
    final=cp["data"]["finalized"]
    epoch=int(final["epoch"])
    validators=query(BN,"/eth/v1/beacon/states/"+final["root"]+"/validators")
    ids=[v["index"] for v in validators["data"] if v["status"].startswith("active_")]
    if not ids:
        raise ValueError("no active validators")
    rewards={}
    for e in range(max(0,epoch-2),epoch+1):
        rewards[str(e)]=optional(lambda e=e:query(BN,"/eth/v1/beacon/rewards/attestations/"+str(e),ids))
    head=query(BN,"/eth/v1/beacon/headers/head")["data"]["header"]["message"]
    slot=int(head["slot"])
    blocks={}
    # Recent slots only: avoid repeated huge historical queries.
    for s in range(max(0,slot-3),slot+1):
        blocks[str(s)]=optional(lambda s=s:query(BN,"/eth/v1/beacon/rewards/blocks/"+str(s)))
    return {"schema":"SSE_NATIVE_REWARD_OBSERVATION_V1","chainId":31340,
            "observedUnixNs":time.time_ns(),"checkpoints":cp,
            "finalizedValidators":validators,"attestationRewards":rewards,
            "recentBlockRewards":blocks,"headSlot":slot,
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

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=Path.home()/".local/share/sse-native-rewards")
    a=p.parse_args()
    d=collect()
    result=summarize(d)
    result["archive"]=str(archive(a.output,d))
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
