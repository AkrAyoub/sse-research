#!/usr/bin/env python3
"""V3 canonical epoch state and authenticated compute wire. No signing or writes."""
from eth_abi import encode
from eth_utils import keccak
from eth_account import Account
from eth_account.messages import encode_typed_data
from sse_pos_r362_v3_market_operations import MARKET,LEDGER,call,require,verify
from sse_pos_r231_v2_compute_wire import WIRE,payload_from_result,validate_payload
from sse_pos_r233_public_v2_compute_terms import canonical
from compute_workload import compute_result
LEASE="(address,address,bytes32,bytes32,bytes32,bytes32,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint64,uint64,uint64,uint256,uint8,bool,uint64,bool,bytes32,uint64)"
EPOCH="(bytes32,bytes32,uint256,uint256,bool,bool,bool,bool,uint64)"
VOTE="(bytes32,bytes32,uint64,uint64,uint256,uint256,uint256,bool,bool,bool,uint8)"
def hx(v):return "0x"+v.hex()
def snapshot(ask,lease,epoch):
    head=ask("eth_getBlockByNumber",["latest",False])
    tag=head["number"]
    l=call(ask,MARKET,"lease(uint256)",("uint256",),(lease,),(LEASE,),tag=tag)[0]
    e=call(ask,MARKET,"epoch(uint256,uint256)",("uint256","uint256"),(lease,epoch),(EPOCH,),tag=tag)[0]
    v=call(ask,LEDGER,"epoch(uint256,uint256)",("uint256","uint256"),(lease,epoch),(VOTE,),tag=tag)[0]
    require(ask("eth_getBlockByNumber",[tag,False])["hash"]==head["hash"],"snapshot reorganized")
    require(l[22] and l[21] in (3,4),"lease not accepted/active")
    require(e[4]==v[7] and e[0]==v[0],"epoch mismatch")
    return dict(leaseId=lease,epochId=epoch,consumer=l[0],provider=l[1],profileHash=hx(l[2]),policyHash=hx(l[3]),endpointHash=hx(l[4]),requestHash=hx(e[0]),responseHash=hx(v[1]),exists=e[4],resolved=e[5],acknowledged=e[6],accounted=e[7],authenticated=v[8],sealed=v[9],outcome=v[10],responseDeadline=v[2],monitoringClose=v[3],evidenceClose=e[8],successVotes=v[4],failureVotes=v[5],headTimestamp=int(head["timestamp"],16),block=tag,blockHash=head["hash"],nextEpoch=l[9],lastProgressAt=l[26],confirmationSeconds=l[17])
def check_proposal(d,s):
    from sse_pos_r366_v3_scientific_proposal import proposal
    require(proposal(d["profile"])==d,"proposal differs from reproducible policy")
    require(d["profileHash"]==s["profileHash"] and d["policyHash"]==s["policyHash"] and d["terms"]["endpointHash"]==s["endpointHash"],"proposal differs from lease")
def response_hash(payload):
    validate_payload(payload)
    return hx(keccak(b"SSE_V3_COMPUTE_RECEIPT_V1\x00"+canonical(payload)))
def typed(s,kind,response=None):
    fields=[("leaseId","uint256"),("epochId","uint256"),("requestHash","bytes32")]
    msg={k:s[k] for k,t in fields}
    if kind=="ProviderResponse":
        fields.append(("responseHash","bytes32"));msg["responseHash"]=response
    elif kind!="ProviderAck":raise ValueError("unsupported evidence kind")
    return encode_typed_data(domain_data={"name":"SSEAdaptiveMarketV3","version":"1","chainId":31340,"verifyingContract":MARKET},message_types={kind:[{"name":k,"type":t} for k,t in fields]},message_data=msg)
def validate_reply(reply,s):
    require(set(reply)==set(WIRE)|{"responseHash","providerSignature"},"wrong V3 reply fields")
    p={k:reply[k] for k in WIRE}
    expected=payload_from_result(s["leaseId"],s["epochId"],s["requestHash"],s["profileHash"],s["policyHash"],compute_result(s["leaseId"],s["epochId"],s["requestHash"]))
    require(p==expected,"invalid compute output/context")
    h=response_hash(p)
    require(reply["responseHash"]==h,"wrong response commitment")
    require(Account.recover_message(typed(s,"ProviderResponse",h),signature=reply["providerSignature"]).lower()==s["provider"].lower(),"wrong provider signature")
    require(not s["authenticated"] or s["responseHash"]==h,"on-chain response mismatch")
    return h
