#!/usr/bin/env python3
"""R375 exact V3 bilateral residual agreement; local owner signatures only."""
import argparse,json,sys
from pathlib import Path
from getpass import getpass
from eth_account import Account
from eth_account.messages import encode_typed_data
from sse_pos_r362_v3_market_operations import MARKET,call,verify,require
from sse_pos_r367_v3_compute_wire import snapshot,EPOCH
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
from sse_pos_r232_v2_monitor_probe import write_create_only
from sse_pos_r206_adaptive_v2_deployment_audit import rpc

def intent(ask,lease,epoch,provider_share):
    s=snapshot(ask,lease,epoch)
    tag=s["block"]
    e=call(ask,MARKET,"epoch(uint256,uint256)",("uint256","uint256"),(lease,epoch),(EPOCH,),tag=tag)[0]
    a=call(ask,MARKET,"scientificEpoch(uint256,uint256)",("uint256","uint256"),(lease,epoch),("(bytes32,uint8,bool,bool,uint256,uint256,uint256)",),tag=tag)[0]
    require(s["exists"] and s["accounted"] and not s["resolved"] and a[2] and not a[3] and a[6]>0,"residual not eligible")
    require(a[0]==e[0] and 0<=provider_share<=a[6],"invalid residual allocation")
    allocation=dict(unresolvedAmount=a[6],providerShare=provider_share,consumerShare=a[6]-provider_share,nonce=e[3],expiry=e[8]+86400)
    require(s["headTimestamp"]<allocation["expiry"],"agreement expired")
    require(ask("eth_getBlockByNumber",[tag,False])["hash"]==s["blockHash"],"agreement anchor reorganized")
    message=dict(leaseId=lease,epochId=epoch,requestHash=s["requestHash"],**allocation)
    fields=[{"name":k,"type":"bytes32" if k=="requestHash" else "uint256"} for k in message]
    typed=encode_typed_data(domain_data={"name":"SSEAdaptiveMarketV3","version":"1","chainId":31340,"verifyingContract":MARKET},message_types={"ResidualAgreement":fields},message_data=message)
    return s,allocation,message,typed

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role",choices=("consumer","provider"),required=True)
    p.add_argument("--lease",type=int,default=1)
    p.add_argument("--epoch",type=int,default=0)
    p.add_argument("--provider-share",type=int,required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    ask=lambda m,v:rpc(a.rpc,m,v)
    verify(ask)
    s,allocation,message,typed=intent(ask,a.lease,a.epoch,a.provider_share)
    require(sys.stdin.isatty() and sys.stderr.isatty(),"owner terminal required")
    print(json.dumps({"role":a.role,"signer":s[a.role],"message":message,"market":MARKET},indent=2))
    require(input("Type AUTHORIZE-V3-RESIDUAL-AGREEMENT: ")=="AUTHORIZE-V3-RESIDUAL-AGREEMENT","not authorized")
    account=Account.from_key(Account.decrypt(safe_keystore(a.keystore),getpass("Application wallet password: ")))
    require(account.address.lower()==s[a.role].lower(),"wrong party")
    fresh,_,fresh_message,_=intent(ask,a.lease,a.epoch,a.provider_share)
    require(fresh_message==message and fresh[a.role].lower()==account.address.lower(),"agreement changed")
    signature="0x"+bytes(account.sign_message(typed).signature).hex()
    out={"role":a.role,"signer":account.address,"message":message,"allocation":allocation,"signature":signature}
    write_create_only(a.output,out)
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
