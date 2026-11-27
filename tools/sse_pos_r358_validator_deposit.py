#!/usr/bin/env python3
"""R358b: verify real chain31340 BLS deposits and prepare native staking calldata.
Read-only. No secrets, funding, signing, or broadcast.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from py_ecc.bls import G2ProofOfPossession as bls
from sse_pos_r358_validator_key import signing_root,deposit_message_root,FORK
from sse_pos_validator_deposit import validate,read_deposit,CONTRACT,VALUE_WEI
from sse_pos_deposit_predeploy import standard_reference
from sse_pos_r206_adaptive_v2_deployment_audit import rpc,GENESIS
from sse_pos_r228_v2_typed_data import checked_addr

BEACON_ROOT="0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"

def beacon(path):
    url="http://127.0.0.1:25052"+path
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url,timeout=10) as res:
        if res.status!=200: raise ValueError("Beacon HTTP failure")
        raw=res.read(1048577)
    if len(raw)>1048576: raise ValueError("Beacon response oversized")
    return json.loads(raw)["data"]

def verify_deposit(record):
    plan=validate(record,expected_fork="0x"+FORK.hex())
    pub=bytes.fromhex(record["pubkey"])
    wd=bytes.fromhex(record["withdrawal_credentials"])
    sig=bytes.fromhex(record["signature"])
    if wd[:12]!=b"\x01"+bytes(11) or not any(wd[12:]):
        raise ValueError("explicit nonzero execution withdrawal credential required")
    if record.get("deposit_message_root")!=deposit_message_root(pub,wd).hex():
        raise ValueError("deposit message root mismatch")
    if not bls.KeyValidate(pub) or not bls.Verify(pub,signing_root(pub,wd),sig):
        raise ValueError("invalid BLS proof of possession")
    return {**plan,"chainId":31340,"cryptographicBlsProofVerified":True,
            "withdrawalAddress":"0x"+wd[12:].hex()}

def prepare(record,url,sender):
    sender=checked_addr(sender)
    plan=verify_deposit(record)
    if rpc(url,"eth_chainId",[])!=hex(31340) or rpc(url,"eth_getBlockByNumber",["0x0",False])["hash"]!=GENESIS:
        raise ValueError("wrong execution chain")
    genesis=beacon("/eth/v1/beacon/genesis")
    if genesis["genesis_validators_root"]!=BEACON_ROOT or genesis["genesis_fork_version"]!="0x"+FORK.hex():
        raise ValueError("wrong consensus genesis")
    spec=beacon("/eth/v1/config/spec")
    if int(spec["DEPOSIT_CHAIN_ID"])!=31340 or spec["DEPOSIT_CONTRACT_ADDRESS"].lower()!=CONTRACT.lower():
        raise ValueError("wrong live deposit configuration")
    sync=beacon("/eth/v1/node/syncing")
    if any(sync.get(k) is not False for k in ("is_syncing","is_optimistic","el_offline")) or int(sync["sync_distance"])!=0:
        raise ValueError("local beacon not synchronized and execution-verified")
    code=standard_reference()["code"].lower()
    genesis_code=rpc(url,"eth_getCode",[CONTRACT,"0x0"])
    if genesis_code is not None and (not isinstance(genesis_code,str) or genesis_code.lower()!=code):
        raise ValueError("genesis deposit runtime mismatch")
    finalized=rpc(url,"eth_getBlockByNumber",["finalized",False])
    if not isinstance(finalized,dict) or int(finalized["number"],16)<=0:
        raise ValueError("finalized execution anchor unavailable")
    height=finalized["number"]
    for block in (height,"latest"):
        actual=rpc(url,"eth_getCode",[CONTRACT,block])
        if not isinstance(actual,str) or actual.lower()!=code:
            raise ValueError("deposit runtime unavailable or mismatched at "+block)
    if rpc(url,"eth_getBlockByNumber",[height,False])["hash"]!=finalized["hash"]:
        raise ValueError("finalized deposit runtime anchor changed")
    validators=beacon("/eth/v1/beacon/states/head/validators")
    if any(v["validator"]["pubkey"].lower()==plan["validatorBlsPubkey"] for v in validators):
        raise ValueError("validator already registered; never duplicate deposit")
    call={"from":sender,"to":CONTRACT,"value":hex(VALUE_WEI),"data":plan["calldata"]}
    balance=int(rpc(url,"eth_getBalance",[sender,"latest"]),16)
    gas=int(rpc(url,"eth_estimateGas",[call]),16) if balance>=VALUE_WEI else None
    price=int(rpc(url,"eth_gasPrice",[]),16)
    return {**plan,"sender":sender,"originalELCLGenesisVerified":True,
            "standardDepositRuntimeVerified":True,
            "historicalGenesisDepositCodeAvailable":genesis_code is not None,
            "finalizedDepositRuntimeHeight":int(height,16),"registeredValidatorCount":len(validators),
            "senderBalanceWei":str(balance),"gasEstimate":gas,"gasPriceWei":str(price),
            "fundingRequiredWei":str(max(0,VALUE_WEI+(gas or 0)*price-balance)),
            "readyForOwnerDeposit":gas is not None and balance>=VALUE_WEI+gas*price,
            "pendingDuplicateDepositExcluded":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--deposit-data",type=Path,required=True)
    p.add_argument("--sender",required=True)
    p.add_argument("--rpc",default="http://127.0.0.1:28545",choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    a=p.parse_args()
    try:
        result=prepare(read_deposit(a.deposit_data),a.rpc,a.sender)
        print(json.dumps({k:v for k,v in result.items() if k!="calldata"},indent=2,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(2,"R358_DEPOSIT_REFUSED: "+str(exc)+"\n")
if __name__=="__main__":
    main()
