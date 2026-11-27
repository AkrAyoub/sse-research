#!/usr/bin/env python3
"""Read-only original-chain local native health gate. No third-party RPC."""
import json
import urllib.request
import time

EL="http://127.0.0.1:28545"
BN="http://127.0.0.1:25052"
def rpc(method,params=None):
    req=urllib.request.Request(EL,data=json.dumps(dict(jsonrpc="2.0",id=1,method=method,params=params or [])).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=15) as r:
        x=json.load(r)
    if "result" not in x:
        raise RuntimeError("native RPC refused "+method)
    return x["result"]
def beacon(path):
    with urllib.request.urlopen(BN+path,timeout=15) as r:
        return json.load(r)["data"]
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def main():
    require(rpc("eth_chainId")=="0x7a6c","wrong chain")
    require(rpc("eth_getBlockByNumber",["0x0",False])["hash"]=="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf","wrong EL genesis")
    require(beacon("/eth/v1/beacon/genesis")["genesis_validators_root"]=="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd","wrong CL genesis")
    require(rpc("eth_syncing") is False,"EL syncing")
    cl=beacon("/eth/v1/node/syncing")
    require(cl["is_syncing"] is False and cl["is_optimistic"] is False and cl.get("el_offline") is False,"CL not fully verified")
    f=rpc("eth_getBlockByNumber",["finalized",False])
    require(int(f["number"],16)>0 and 0<=time.time()-int(f["timestamp"],16)<1800,"stale or missing finalized head")
    require(int(rpc("net_peerCount"),16)>0 and int(beacon("/eth/v1/node/peer_count")["connected"])>0,"missing native peers")
    print(json.dumps(dict(finalizedHeight=int(f["number"],16),finalizedHash=f["hash"],nativeHealthGatePassed=True)))
if __name__=="__main__": main()
