#!/usr/bin/env python3
"""R352: owner-authorized provider response preparation and durable public reply.

No private key persistence, no transaction broadcast. Reuses R237 finalized
authorization and R231 wire validation. Existing valid signed replies are
reused rather than overwritten.
"""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
from sse_pos_r206_adaptive_v2_deployment_audit import load,rpc
from sse_pos_r229_v2_finalized_lease_snapshot import inspect
from sse_pos_r350_v2_canonical_lease_snapshot import inspect_canonical
from sse_pos_r237_v2_approved_local_eip712_sign import public_intent,sign_authorized
from sse_pos_r231_v2_compute_wire import provider_eip712_message,signed_reply,validate_signed_reply
from sse_pos_r232_v2_monitor_probe import write_create_only
from sse_pos_r233_public_v2_compute_terms import resource_hash,policy_hash
from compute_workload import compute_result
from sse_challenge import keccak256

def read_public(path):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=8192:
        raise ValueError("bounded regular public JSON required")
    return json.loads(path.read_text("utf-8"))

def prepare(manifest,url,root,keystore,*,sign=False):
    if not root.is_absolute() or root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.geteuid() or root.stat().st_mode & 0o077:
        raise ValueError("owner-private response directory required")
    payload=read_public(root/"provider-payload.json")
    message=provider_eip712_message(payload)
    if read_public(root/"provider-signing-message.json")!=message:
        raise ValueError("stored message does not bind actual payload")
    lease_id,epoch_id=message["leaseId"],message["epochId"]
    current=inspect_canonical(manifest,url,lease_id,epoch_id)
    lease=current["lease"]
    ep=current["epoch"]["ledger"]
    if lease["phase"]!=4 or not lease["providerAccepted"] or not current["committee"]["ready"] or not ep["exists"] or ep["monitoringSealed"]:
        raise ValueError("canonical epoch is not active")
    profile=read_public(root/"profile.json")
    policy=read_public(root/"policy.json")
    if (payload["profileHash"]!=lease["profileHash"] or payload["policyHash"]!=lease["policyHash"]
        or resource_hash(profile)!=lease["profileHash"] or policy_hash(policy,profile)!=lease["policyHash"]
        or policy["market"].lower()!=current["market"].lower()
        or "0x"+keccak256(profile["origin"].encode("ascii")).hex()!=lease["endpointHash"]
        or message["requestHash"]!=ep["requestHash"]):
        raise ValueError("payload or terms differ from canonical contract")
    expected=compute_result(lease_id,epoch_id,message["requestHash"])
    if payload["workResultDigest"]!=expected["resultDigest"] or payload["workRounds"]!=expected["rounds"]:
        raise ValueError("invalid deterministic workload result")
    if ep["responseAuthenticated"] and ep["responseHash"]!=message["responseHash"]:
        raise ValueError("different response already authenticated")
    path=root/"signed-reply.json"
    result={"provider":lease["provider"],"message":message,
            "canonicalHeight":current["observedExecutionHeight"],
            "signedReplyAvailable":False,"transactionSubmitted":False}
    if not sign:
        return result
    final=inspect(manifest,url,lease_id,epoch_id)
    if path.exists():
        reply=read_public(path)
    else:
        if path.is_symlink() or ep["responseAuthenticated"]:
            raise ValueError("cannot create new reply after authentication")
        if int(rpc(url,"eth_getBlockByNumber",["latest",False])["timestamp"],16)>=ep["responseDeadline"]:
            raise ValueError("response deadline reached")
        intent=public_intent("provider-response",message,current["market"],current["ledger"],lease["provider"],"provider")
        signed=sign_authorized(intent,keystore,manifest,url,confirm=input,get_password=getpass)
        reply=signed_reply(payload,signed["signature"],lease["provider"],current["market"],current["ledger"])
        validate_signed_reply(reply,final)
        write_create_only(path,reply)
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    check=validate_signed_reply(reply,final)
    if check["responseHash"]!=message["responseHash"]:
        raise ValueError("stored reply differs from intended response")
    return {**result,"signedReplyAvailable":True,"signedReplyPath":str(path),
            "authenticateParams":{"leaseId":lease_id,"epochId":epoch_id,
                                  "responseHash":reply["responseHash"],"signature":reply["providerSignature"]}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--keystore",type=Path)
    p.add_argument("--sign",action="store_true")
    a=p.parse_args()
    try:
        if a.sign!=bool(a.keystore):
            raise ValueError("sign mode requires local encrypted keystore")
        print(json.dumps(prepare(load(a.manifest),a.rpc,a.directory,a.keystore,sign=a.sign),indent=2,sort_keys=True))
    except (ValueError,TypeError,KeyError,OSError) as exc:
        p.exit(2,"R352_REFUSED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
