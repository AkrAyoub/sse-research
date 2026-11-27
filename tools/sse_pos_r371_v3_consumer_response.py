#!/usr/bin/env python3
"""R371 consumer obtains actual signed V3 response for canonical epoch.
Outputs exact authentication arguments; no signing or broadcast.
"""
import argparse,json,time,base64,hashlib
from urllib.error import HTTPError,URLError
from http.client import HTTPException
from eth_keys.exceptions import BadSignature,ValidationError
from pathlib import Path
from urllib.request import Request,ProxyHandler,HTTPSHandler,build_opener
from sse_pos_r362_v3_market_operations import verify,require
from sse_pos_r367_v3_compute_wire import snapshot,check_proposal,validate_reply
from sse_pos_r233_public_v2_compute_terms import canonical
from sse_pos_r232_v2_monitor_probe import NoRedirect,pinned_tls_context,write_create_only,_unique_pairs
from sse_pos_r206_adaptive_v2_deployment_audit import rpc
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proposal",type=Path,required=True)
    p.add_argument("--cert",type=Path,required=True)
    p.add_argument("--fingerprint",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--epoch",type=int,default=0)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    d=json.loads(a.proposal.read_text())
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    s=snapshot(ask,a.lease,a.epoch);check_proposal(d,s)
    require(s["exists"] and not s["sealed"] and not s["authenticated"] and s["headTimestamp"]<s["responseDeadline"],"not awaiting response")
    q={k:s[k] for k in ("leaseId","epochId","requestHash")}
    tls=pinned_tls_context(a.cert,a.fingerprint)
    opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=tls))
    started=time.monotonic()
    observed_at=time.time_ns()
    raw=None
    status=None
    error=None
    try:
        with opener.open(Request(d["profile"]["origin"]+"/v3/challenge",data=canonical(q),headers={"Content-Type":"application/json"},method="POST"),timeout=8) as res:
            status=res.status
            raw=res.read(8193)
    except HTTPError as exc:
        status=exc.code
        error="HTTP_ERROR"
        exc.close()
    except (URLError,OSError,HTTPException) as exc:
        error=type(exc).__name__
    elapsed=round((time.monotonic()-started)*1000)
    # Chain/RPC and local configuration errors deliberately remain fatal.
    fresh=snapshot(ask,a.lease,a.epoch)
    require(fresh["requestHash"]==s["requestHash"],"response epoch changed")
    require(ask("eth_getBlockByNumber",[s["block"],False])["hash"]==s["blockHash"],"epoch anchor reorganized")
    if error is None:
        try:
            require(status==200 and raw is not None and len(raw)<=8192,"invalid provider HTTP reply")
            reply=json.loads(raw,object_pairs_hook=_unique_pairs)
            h=validate_reply(reply,fresh)
        except (ValueError,TypeError,KeyError,BadSignature,ValidationError) as exc:
            error="INVALID_REPLY:"+type(exc).__name__
    if error is None and (fresh["headTimestamp"]>=fresh["responseDeadline"] or fresh["authenticated"] or fresh["sealed"]):
        error="AUTHENTICATION_WINDOW_UNAVAILABLE"
    if error is not None:
        record=dict(schema="SSE_V3_CONSUMER_UNAUTHENTICATED_OBSERVATION_V1",chainId=31340,challenge=q,policyHash=s["policyHash"],anchorBlock=s["block"],anchorHash=s["blockHash"],observedAtUnixNs=observed_at,elapsedMs=elapsed,httpStatus=status,reason=error,authenticateParams=None,qualifiedFailure=False,physicalSlaTruthProved=False)
        if raw is not None:
            record.update(bodyPrefixBase64=base64.b64encode(raw).decode("ascii"),bodyPrefixSha256=hashlib.sha256(raw).hexdigest(),bodyMayBeTruncated=len(raw)>8192)
        write_create_only(a.output,record)
        print("UNAUTHENTICATED_OBSERVATION_ARCHIVED",error,flush=True)
        return
    params={"leaseId":a.lease,"epochId":a.epoch,"responseHash":h,"signature":reply["providerSignature"]}
    write_create_only(a.output,{"reply":reply,"elapsedMs":elapsed,"authenticateParams":params})
    print(json.dumps(params))
if __name__=="__main__":main()
