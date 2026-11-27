#!/usr/bin/env python3
"""R350 canonical-head lease observation, never a finalized authorization."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from sse_pos_r206_adaptive_v2_deployment_audit import load, rpc, verify
from sse_pos_r229_v2_finalized_lease_snapshot import _inspect_at_height


def block_identity(block):
    if not isinstance(block,dict):
        raise ValueError("missing execution block")
    h=block.get("hash")
    n=block.get("number")
    if not isinstance(h,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",h):
        raise ValueError("invalid block hash")
    if not isinstance(n,str) or not re.fullmatch(r"0x[0-9a-fA-F]+",n):
        raise ValueError("invalid block height")
    return int(n,16),h.lower()


def inspect_canonical(manifest,url,lease_id,epoch_id=None,*,confirmations=1,transport=rpc):
    if type(lease_id) is not int or not 1<=lease_id<2**256:
        raise ValueError("invalid lease ID")
    if epoch_id is not None and (type(epoch_id) is not int or not 0<=epoch_id<2**256):
        raise ValueError("invalid epoch ID")
    if type(confirmations) is not int or not 1<=confirmations<=256:
        raise ValueError("invalid confirmation depth")
    ask=lambda method,params: transport(url,method,params)
    proof=verify(manifest,url,transport=transport)
    head,head_hash=block_identity(ask("eth_getBlockByNumber",["latest",False]))
    if head<proof["finalizedExecutionHeight"]:
        raise ValueError("head behind verified finality")
    height=head-confirmations+1
    if height<0:
        raise ValueError("insufficient chain history")
    actual,digest=block_identity(ask("eth_getBlockByNumber",[hex(height),False]))
    if actual!=height or (confirmations==1 and digest!=head_hash):
        raise ValueError("canonical block selection changed")
    def check_anchor():
        if block_identity(ask("eth_getBlockByNumber",[hex(height),False]))!=(height,digest):
            raise ValueError("canonical anchor reorganized")
    check_anchor()
    for role in ("market","ledger"):
        entry=manifest[role]
        code=ask("eth_getCode",[entry["address"],hex(height)])
        if not isinstance(code,str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+",code):
            raise ValueError("missing canonical runtime")
        if hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()!=entry["runtimeSha256"]:
            raise ValueError("canonical runtime mismatch")
    state=_inspect_at_height(manifest,url,lease_id,epoch_id,height,transport=transport)
    check_anchor()
    latest,_=block_identity(ask("eth_getBlockByNumber",["latest",False]))
    if latest-height+1<confirmations:
        raise ValueError("confirmation depth lost")
    check_anchor()
    # Do not expose the finalized schema or height to existing authorization code.
    state.pop("finalizedExecutionHeight")
    state.update(schema="SSE_R350_CANONICAL_V2_LEASE_READONLY_V1",
                 assurance="CANONICAL_OBSERVATION_NOT_FINALIZED_AUTHORIZATION",
                 observedExecutionHeight=height,observedExecutionHash=digest,
                 observedConfirmations=latest-height+1,
                 deploymentFinalizedHeight=proof["finalizedExecutionHeight"],
                 reorganizationPossible=True,finalizedAuthorization=False)
    return state


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--rpc",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"),required=True)
    p.add_argument("--lease-id",type=int,required=True)
    p.add_argument("--epoch-id",type=int)
    p.add_argument("--confirmations",type=int,default=1)
    a=p.parse_args()
    try:
        print(json.dumps(inspect_canonical(load(a.manifest),a.rpc,a.lease_id,a.epoch_id,confirmations=a.confirmations),indent=2,sort_keys=True))
    except (ValueError,TypeError,KeyError,OSError) as exc:
        p.exit(2,"R350_REFUSED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
