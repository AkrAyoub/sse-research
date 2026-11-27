#!/usr/bin/env python3
"""Explicit owner-authorized TEST ETH funding or V4 monitor registration.
Read-only plan by default; private durable journal before every broadcast.
No private keys, passwords, or raw signed transactions in logs. Never retry
unknown outcomes. Funding uses the existing application-only deployer.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
from getpass import getpass

from eth_account import Account
from eth_utils import to_checksum_address
from sse_chain_read import LocalRPC
from sse_pos_r237_v2_approved_local_eip712_sign import safe_keystore
import sse_v4_state as st
import sse_v4_abi as a

ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()
DEPLOYER="0xed0ed5e0526898c6e0e3c83140efca12672e7ff0"
MAX_PRICE=10**6

def require(ok,msg):
    if not ok:
        raise RuntimeError(msg)

def q(ask,method,params):
    return int(ask(method,params),16)

def monitor_intent(position, capacity, bond_per_seat, resize=False):
    """Explicit capacity admission; no implicit resizing of an existing position."""
    require(type(capacity) is int and 1 <= capacity <= 64,"capacity must be 1..64")
    require(bond_per_seat == 10**15,"unexpected immutable bond")
    bond, old_capacity, reserved, entry, exiting = position
    require(not exiting,"exiting monitor must complete exit first")
    if not entry:
        require(not resize and tuple(position)==(0,0,0,0,False),"new position requires registration")
        return a.register_monitor(capacity, capacity*bond_per_seat)
    if old_capacity == capacity:
        return None
    require(resize,"existing capacity differs; explicit --resize required")
    require(capacity>=reserved,"capacity below reserved seats")
    return a.update_bond(capacity, max(0,capacity*bond_per_seat-bond))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fund",action="append",help="public participant address; repeat for batch")
    p.add_argument("--register",action="store_true")
    p.add_argument("--capacity",type=int,default=1,help="concurrent monitor seats, 1..64; measure actual host capacity")
    p.add_argument("--resize",action="store_true",help="explicitly update existing monitor capacity")
    p.add_argument("--fund-to-wei",type=int,default=2*10**16)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--status",action="store_true")
    args=p.parse_args()
    require(bool(args.fund)!=args.register,"choose funding OR registration")
    require(not(args.apply and args.status),"choose apply OR status")
    require(1<=args.capacity<=64 and (not args.resize or args.register),"invalid capacity/resize request")
    require(not args.fund or args.capacity==1,"capacity is registration-only")
    require(os.geteuid()!=0,"nonroot owner only")
    manifest=st.load_manifest(ROOT/"release/chain31340-v4-manifest.json")
    ask=LocalRPC("http://127.0.0.1:28545",timeout=20).request
    st.verify_deployment(ask,manifest)
    if args.fund:
        require(os.environ.get("USER")=="ayoubakrvm4707","fund from original dedicated application owner")
        key=HOME/".local/share/sse-v2-app-only/adaptive-v2-deployer.keystore.json"
        state=st.private_dir(HOME/".local/share/sse-v4-owner-funding")
    else:
        policy=st.read_json(HOME/".config/sse-v4/policy.json")
        require(isinstance(policy,dict) and "monitor" in policy["roles"],"monitor policy required")
        key=Path(policy["keystore"])
        state=st.private_dir(HOME/".local/share/sse-v4")
    doc=safe_keystore(key)
    sender="0x"+doc["address"].lower().removeprefix("0x")
    require(st.ADDR.fullmatch(sender) and sender!="0x13fb73aace8a11be2899d047635a757a224ce00b","invalid signer")
    require(sender== (DEPLOYER if args.fund else policy["wallet"].lower()),"wrong signer")
    lock=open(state/"agent.lock","a")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    j=st.Journal(state)
    for e in j.unresolved(sender):
        print(json.dumps(j.reconcile(ask,e),sort_keys=True),flush=True)
    if args.status:
        print(json.dumps(j.entries(),indent=2))
        return
    require(not j.unresolved(sender),"previous transaction not finalized: use --status; no resend")
    nonce=q(ask,"eth_getTransactionCount",[sender,"latest"])
    require(all(q(ask,"eth_getTransactionCount",[sender,tag])==nonce for tag in ("pending","finalized")),"sender activity not finalized")
    price=q(ask,"eth_gasPrice",[])
    require(0<price<=MAX_PRICE,"native TEST ETH gas quote outside cap")
    actions=[]
    if args.fund:
        require(0<args.fund_to_wei<=10**17 and 1<=len(args.fund)<=16,"bounded funding only")
        addresses=[to_checksum_address(x).lower() for x in args.fund]
        require(len(set(addresses))==len(addresses),"duplicate recipient")
        for target in addresses:
            require(target not in (sender,"0x"+"0"*40,"0x13fb73aace8a11be2899d047635a757a224ce00b") and ask("eth_getCode",[target,"latest"])=="0x","not a participant EOA")
            bal=q(ask,"eth_getBalance",[target,"finalized"])
            require(bal==q(ask,"eth_getBalance",[target,"latest"]),"recipient activity not finalized")
            if bal<args.fund_to_wei:
                actions.append((target,"0x",args.fund_to_wei-bal,21000,"fund participant"))
    else:
        reg=manifest["modules"]["registry"]
        def position(tag):
            return a.view(ask,reg,"position(address)",("address",),(sender,),("uint256",)*4+("bool",),tag)
        pos=position("finalized")
        require(pos==position("latest"),"registration not finalized")
        bond=a.view(ask,reg,"perSeatBond()")[0]
        intent=monitor_intent(pos,args.capacity,bond,args.resize)
        if intent is None:
            print("EXISTING_MONITOR_POSITION=",pos)
            return
        _,data,value=intent
        call={"from":sender,"to":reg,"data":data,"value":hex(value)}
        ask("eth_call",[call,"latest"])
        gas=q(ask,"eth_estimateGas",[call])*12//10
        require(0<gas<=500000,"registration gas above cap")
        actions.append((reg,data,value,gas,("resize" if pos[3] else "register")+" capacity "+str(args.capacity)))
    if not actions:
        print("NO_NEW_TRANSACTION_REQUIRED=true")
        return
    total=sum(x[2]+x[3]*price for x in actions)
    require(q(ask,"eth_getBalance",[sender,"finalized"])>=total,"insufficient finalized balance")
    print(json.dumps({"chainId":31340,"sender":sender,"firstNonce":nonce,"legacyGasPriceWei":price,
                      "maxDebitWei":total,"actions":[dict(to=x[0],valueWei=x[2],gas=x[3],action=x[4]) for x in actions]},indent=2),flush=True)
    if not args.apply:
        print("PLAN_ONLY=true")
        return
    phrase="SEND-V4-TEST-ETH-"+str(total)
    require(input("Type "+phrase+" to authorize this exact batch: ")==phrase,"not authorized")
    account=Account.from_key(Account.decrypt(doc,getpass("Local application keystore passphrase: ")))
    require(account.address.lower()==sender,"keystore signer mismatch")
    st.verify_deployment(ask,manifest)
    require(q(ask,"eth_getTransactionCount",[sender,"latest"])==nonce==q(ask,"eth_getTransactionCount",[sender,"pending"]),"nonce changed")
    for target,data,value,gas,label in actions:
        require(q(ask,"eth_getTransactionCount",[sender,"latest"])==nonce==q(ask,"eth_getTransactionCount",[sender,"pending"]),"nonce changed")
        require(q(ask,"eth_getBalance",[sender,"latest"])>=value+gas*price,"insufficient remaining funds")
        call={"from":sender,"to":target,"data":data,"value":hex(value)}
        if args.fund:
            require(q(ask,"eth_getBalance",[target,"latest"])+value==args.fund_to_wei and ask("eth_getCode",[target,"latest"])=="0x","recipient state changed")
        else:
            ask("eth_call",[call,"latest"])
        task=j.task_id(target,data,value,"owner funding or registration")
        require(not j.find_task(task),"task already attempted: no automatic retry")
        signed=account.sign_transaction(dict(chainId=31340,nonce=nonce,to=to_checksum_address(target),
                    data=data,value=value,gas=gas,gasPrice=price))
        h="0x"+bytes(signed.hash).hex()
        path=j.record(sender,nonce,h,task,target,data,value,label)
        print("JOURNALED_TRANSACTION="+h,flush=True)
        try:
            ack=ask("eth_sendRawTransaction",["0x"+bytes(signed.raw_transaction).hex()])
            require(ack.lower()==h,"broadcast acknowledgement mismatch")
        except Exception:
            j.update(st.read_json(path),status="BROADCAST_ERROR_UNKNOWN")
            raise
        j.update(st.read_json(path),status="BROADCAST")
        for _ in range(30):
            e=j.reconcile(ask,st.read_json(path))
            if e["status"] in ("CANONICAL_SUCCESS","FINALIZED_SUCCESS"):
                print("CANONICAL_INCLUDED="+h,flush=True)
                break
            require(e["status"] not in ("CANONICAL_REVERTED","FINALIZED_REVERTED","NONCANONICAL_RECEIPT"),"transaction failed; stop")
            time.sleep(3)
        else:
            raise RuntimeError("receipt unknown/pending: stop; use --status, never resend")
        nonce+=1
    print("OWNER_BATCH_INCLUDED_AWAIT_FINALITY=true")

if __name__=="__main__":
    main()
