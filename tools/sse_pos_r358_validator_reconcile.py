#!/usr/bin/env python3
"""Read-only native deposit reconciliation and consensus activation status."""
import argparse
import json
from pathlib import Path
from eth_abi import decode
from eth_utils import keccak
from sse_pos_r358_validator_deposit import verify_deposit,read_deposit,beacon,BEACON_ROOT,CONTRACT
from sse_pos_r206_adaptive_v2_deployment_audit import rpc,GENESIS

def inspect(root,url):
    plan=verify_deposit(read_deposit(root/"deposit-data.json"))
    journal=json.loads((root/"deposit-intent.json").read_text())
    if (journal["chainId"]!=31340 or journal["validatorPubkey"]!=plan["validatorBlsPubkey"]
        or journal["depositDataRoot"]!=plan["depositDataRoot"] or journal["valueWei"]!=int(plan["depositValueTestWei"])
        or journal["sender"]!=plan["withdrawalAddress"]):
        raise ValueError("deposit intent mismatch")
    if rpc(url,"eth_chainId",[])!=hex(31340) or rpc(url,"eth_getBlockByNumber",["0x0",False])["hash"]!=GENESIS or beacon("/eth/v1/beacon/genesis")["genesis_validators_root"]!=BEACON_ROOT:
        raise ValueError("wrong original chain")
    digest=journal["transactionHash"]
    tx=rpc(url,"eth_getTransactionByHash",[digest])
    receipt=rpc(url,"eth_getTransactionReceipt",[digest])
    result={"chainId":31340,"transactionHash":digest,"validatorPubkey":plan["validatorBlsPubkey"],"receiptSuccessful":False,"executionFinalized":False,"validatorRegistered":False,"validatorActive":False}
    if tx is None or receipt is None:
        return {**result,"state":"PENDING_OR_UNKNOWN_DO_NOT_RESEND"}
    if (tx["hash"].lower()!=digest or receipt["transactionHash"].lower()!=digest or tx["from"].lower()!=journal["sender"]
        or tx["to"].lower()!=CONTRACT.lower() or int(tx["nonce"],16)!=journal["nonce"]
        or int(tx["value"],16)!=journal["valueWei"] or tx["input"].lower()!=plan["calldata"].lower()):
        raise ValueError("transaction differs from intent")
    height=int(receipt["blockNumber"],16)
    block=rpc(url,"eth_getBlockByNumber",[hex(height),False])
    if block["hash"]!=receipt["blockHash"] or tx["blockHash"]!=block["hash"]:
        return {**result,"state":"NONCANONICAL_DO_NOT_RESEND"}
    if receipt["status"]!="0x1":
        return {**result,"state":"REVERTED_REVIEW_REQUIRED"}
    record=read_deposit(root/"deposit-data.json")
    topic="0x"+keccak(text="DepositEvent(bytes,bytes,bytes,bytes,bytes)").hex()
    matches=[]
    for log in receipt["logs"]:
        if log["address"].lower()==CONTRACT.lower() and log["topics"]==[topic]:
            pub,wd,amount,sig,index=decode(["bytes"]*5,bytes.fromhex(log["data"][2:]))
            if pub.hex()==record["pubkey"] and wd.hex()==record["withdrawal_credentials"] and len(amount)==8 and int.from_bytes(amount,"little")==record["amount"] and sig.hex()==record["signature"] and len(index)==8:
                matches.append(int.from_bytes(index,"little"))
    if len(matches)!=1:
        raise ValueError("exact deposit event missing or duplicated")
    finalized=rpc(url,"eth_getBlockByNumber",["finalized",False])
    result.update(receiptSuccessful=True,includedBlock=height,depositIndex=matches[0],executionFinalized=int(finalized["number"],16)>=height,state="CANONICAL_DEPOSIT")
    validators=beacon("/eth/v1/beacon/states/head/validators?id="+plan["validatorBlsPubkey"])
    if len(validators)>1:
        raise ValueError("duplicate consensus validator")
    if validators:
        v=validators[0]
        if v["validator"]["pubkey"].lower()!=plan["validatorBlsPubkey"] or v["validator"]["withdrawal_credentials"].lower()!=plan["withdrawalCredentials"]:
            raise ValueError("consensus identity mismatch")
        result.update(validatorRegistered=True,validatorActive=v["status"]=="active_ongoing",validatorStatus=v["status"],validatorIndex=v["index"],balanceGwei=v["balance"],activationEpoch=v["validator"]["activation_epoch"],activationEligibilityEpoch=v["validator"]["activation_eligibility_epoch"])
    if rpc(url,"eth_getBlockByNumber",[hex(height),False])["hash"]!=block["hash"]:
        raise ValueError("receipt anchor reorganized")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545")
    a=p.parse_args()
    try: print(json.dumps(inspect(a.directory,a.rpc),indent=2,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError) as exc: p.exit(2,"R358_RECONCILE_REFUSED: "+str(exc)+"\n")
if __name__=="__main__": main()
