#!/usr/bin/env python3
"""Owner-local execution of strictly structured V3 marketplace intents.
Public consoles never receive credentials or execute this tool.
"""
import argparse,json,sys
from pathlib import Path
from sse_pos_r362_v3_market_operations import verify,plan,execute,require
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

ACTIONS={
"consumer":frozenset(("request","fund","start","authenticate","close","market-withdraw","finalize","close-evidence","residual","draw","cancel-expired-draw","cancel-unconfirmed","cancel-unaccepted","expire-idle")),
"provider":frozenset(("bid","accept","acknowledge","market-withdraw","residual","finalize","close-evidence")),
"monitor":frozenset(("register","confirm","vote","monitor-exit","ledger-withdraw","market-withdraw","finalize")),
}
def validate(d):
    require(type(d) is dict and set(d)=={"schema","chainId","role","action","params","maxWei"},"invalid intent fields")
    require(d["schema"]=="SSE_V3_OWNER_INTENT_V1" and d["chainId"]==31340,"invalid intent domain")
    require(d["role"] in ACTIONS and d["action"] in ACTIONS[d["role"]],"invalid role/action")
    require(type(d["params"]) is dict and type(d["maxWei"]) is int and 0<d["maxWei"]<=10**18,"invalid spend cap")
    target,data,value=plan(d["action"],d["params"])
    require(0<=value<d["maxWei"],"value exceeds intent cap")
    return target,data,value
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--intent",type=Path,required=True)
    p.add_argument("--address",required=True)
    p.add_argument("--keystore",type=Path)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    p.add_argument("--send",action="store_true")
    a=p.parse_args()
    require(a.intent.is_file() and a.intent.stat().st_size<=16384,"invalid intent size")
    d=json.loads(a.intent.read_text())
    target,data,value=validate(d)
    ask=lambda m,p:rpc(a.rpc,m,p)
    print(json.dumps(verify(ask),indent=2))
    print(json.dumps(d,indent=2))
    print("INTENT_TARGET",target,"VALUE_WEI",value,flush=True)
    execute(ask,d["action"],d["params"],a.address,d["maxWei"],send=a.send,keystore=a.keystore)
if __name__=="__main__":main()
