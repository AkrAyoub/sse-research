#!/usr/bin/env python3
"""R333: truthful terminal onboarding summary from live role-local status.
Optional HTTPS URL must match the local node identity and roles. No writes,
signing, keys, or public endpoint creation. No arbitrary URL redirects.
"""
import argparse
import json
import re
import urllib.request

LOCAL="http://127.0.0.1:8767"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def fetch(base):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(base+"/v2/status",timeout=20) as res:
        raw=res.read(131073)
    if len(raw)>131072:
        raise ValueError("status exceeds bound")
    return json.loads(raw)

def checked_url(url):
    if not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",url):
        raise ValueError("expected HTTPS DNS origin without path, credentials or port")
    return url

def summary(status,public=None,*,reader=fetch):
    node=status["nodeId"]
    roles=status["declaredRoles"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}",node):
        raise ValueError("invalid node identity")
    allowed={"monitor","consumer","provider","validator","observer","full_node","rpc","dashboard","logs"}
    if not isinstance(roles,list) or not roles or not all(r in allowed for r in roles):
        raise ValueError("invalid roles")
    chain=status.get("executionAndConsensusLocalObservation",status)
    if chain["chainId"]!=31340:
        raise ValueError("wrong chain")
    out={"nodeId":node,"roles":roles,"chainId":31340,
         "executionHead":chain["executionBlockNumber"],
         "finalizedExecutionHeight":status.get("finalizedExecutionHeight"),
         "localDashboard":LOCAL+"/","publicDashboard":None,
         "publicHttpsVerified":False}
    account=status.get("monitorAccount")
    if account is not None and "monitor" in roles:
        out["monitor"]={k:account[k] for k in ("address","active","balanceWei","bondWei","finalizedExecutionHeight")}
    if public:
        public=checked_url(public)
        remote=reader(public)
        remote_chain=remote.get("executionAndConsensusLocalObservation",remote)
        if remote.get("nodeId")!=node or remote.get("declaredRoles")!=roles or remote_chain.get("chainId")!=31340:
            raise ValueError("public endpoint does not match local node")
        if account is not None and remote.get("monitorAccount",{}).get("address","").lower()!=account["address"].lower():
            raise ValueError("public monitor account mismatch")
        out["publicDashboard"]=public+"/"
        out["publicHttpsVerified"]=True
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public-https",help="optional existing HTTPS origin to verify")
    a=p.parse_args()
    result=summary(fetch(LOCAL),a.public_https)
    print("\n========== SSE NODE SUMMARY ==========")
    print(json.dumps(result,indent=2,ensure_ascii=True))
    print("Dashboard:",result["publicDashboard"] or result["localDashboard"])
    if not result["publicHttpsVerified"]:
        print("LOCAL ONLY: not an Internet-accessible dashboard.")
    print("Role declarations are not proof of funded activation.")
    print("======================================")
if __name__=="__main__":
    main()
