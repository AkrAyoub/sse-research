#!/usr/bin/env python3
"""Read-only canonical audit of owner-run V4 CREATEs; no signing or broadcasting.
Output is a candidate public manifest, only after all five receipts are finalized.
Compare exact creation input including constructor arguments and compiled runtime
outside compiler-declared immutable slots. Validate wiring, bond and domains.
"""
import argparse
import hashlib
import json
from pathlib import Path
import rlp
from eth_abi import encode
from eth_utils import keccak
import sse_v4_state as st
import sse_v4_abi as a
import sse_v4_terms as t
from sse_chain_read import LocalRPC
from sse_v4_verify_abi import CONTRACTS

ORDER = ("board", "registry", "ledger", "standby", "market")
SOURCE = "f0ea53355e9367991a8f42f635282594b1999bee"

def check(ok, message):
    if not ok:
        raise ValueError(message)

def blob(s):
    return bytes.fromhex(s.removeprefix("0x"))

def runtime_match(artifact, actual):
    d = artifact["deployedBytecode"]
    expected = blob(d["object"])
    check(len(actual) == len(expected) and 0 < len(actual) <= 24576, "runtime size mismatch")
    allowed = set()
    for refs in d.get("immutableReferences", {}).values():
        values = []
        for ref in refs:
            start, size = ref["start"], ref["length"]
            check(0 <= start < start+size <= len(expected), "invalid immutable offset")
            slots = set(range(start,start+size))
            check(not allowed.intersection(slots), "overlapping immutable slots")
            allowed.update(slots)
            values.append(actual[start:start+size])
        check(values and len(set(values)) == 1, "inconsistent immutable value")
    check(all(x==y or i in allowed for i,(x,y) in enumerate(zip(expected,actual))), "runtime outside immutables differs")
    return len(allowed)

def audit(ask, plan, broadcast, out):
    check(plan["chainId"]==st.CHAIN_ID and plan["genesisHash"]==st.GENESIS, "wrong deployment plan")
    check(ask("eth_chainId",[])==hex(st.CHAIN_ID), "wrong RPC chain")
    check(ask("eth_getBlockByNumber",["0x0",False])["hash"].lower()==st.GENESIS,"wrong RPC genesis")
    sender=plan["deployer"].lower()
    nonce=plan["startingNonce"]
    bond=plan["perSeatBondWei"]
    check(bond==10**15,"unexpected bond")
    mods={k:v.lower() for k,v in plan["predictedModules"].items()}
    check(set(mods)==set(ORDER),"bad modules")
    txs=broadcast["transactions"]
    check(len(txs)==5,"expected exactly five broadcast entries")
    height,root=st.finalized(ask)
    rows=[]
    for i,m in enumerate(ORDER):
        predicted="0x"+keccak(rlp.encode([blob(sender),nonce+i]))[-20:].hex()
        check(predicted==mods[m],"CREATE address mismatch")
        h=txs[i]["hash"]
        check(isinstance(h,str) and st.HASH.fullmatch(h.lower()),"missing transaction hash")
        tx=ask("eth_getTransactionByHash",[h])
        rc=ask("eth_getTransactionReceipt",[h])
        check(tx and rc,"missing tx or receipt: DO NOT RESEND")
        n=int(rc["blockNumber"],16)
        check(n<=height,"deployment not finalized yet: DO NOT RESEND")
        canon=ask("eth_getBlockByNumber",[hex(n),False])
        check(rc["status"]=="0x1" and rc["blockHash"]==canon["hash"]==tx["blockHash"],"failed or noncanonical receipt")
        check(tx["hash"].lower()==h.lower()==rc["transactionHash"].lower(),"transaction identity mismatch")
        check(tx["from"].lower()==sender==rc["from"].lower() and int(tx["nonce"],16)==nonce+i,"sender/nonce mismatch")
        check(tx["to"] is None and rc["contractAddress"].lower()==predicted and int(tx["value"],16)==0,"not expected CREATE")
        contract=CONTRACTS[m]
        artifact=json.loads((out/(contract+".sol")/(contract+".json")).read_text())
        if m=="market":
            args=encode(["address"]*4,[mods[x] for x in ("board","registry","standby","ledger")])
        elif m=="registry":
            args=encode(["address","uint256"],[mods["market"],bond])
        else:
            args=encode(["address"],[mods["market"]])
        creation=blob(artifact["bytecode"]["object"])+args
        check(blob(tx["input"])==creation,"creation input mismatch: "+m)
        code=blob(ask("eth_getCode",[predicted,hex(height)]))
        masked=runtime_match(artifact,code)
        rows.append(dict(module=m,address=predicted,transactionHash=h,block=n,blockHash=rc["blockHash"],
                         gasUsed=int(rc["gasUsed"],16),runtimeBytes=len(code),immutableBytes=masked,
                         runtimeSha256=hashlib.sha256(code).hexdigest(),
                         creationSha256=hashlib.sha256(creation).hexdigest()))
    manifest=dict(schema="SSE_V4_DEPLOYMENT_MANIFEST_V1",status="FINALIZED_NATIVE_DEPLOYMENT",
                  chainId=st.CHAIN_ID,genesisHash=st.GENESIS,deploymentBlock=max(r["block"] for r in rows),
                  modules=mods,runtimeSha256={r["module"]:r["runtimeSha256"] for r in rows},
                  rpcHints=[],sourceCommit=SOURCE,compiler=dict(forge="1.9.0",solc="0.8.24",optimizerRuns=200))
    report=st.verify_deployment(ask,manifest)
    check(a.view(ask,mods["registry"],"perSeatBond()",tag=hex(height))[0]==bond,"bond mismatch")
    for m,name in (("market",t.MARKET_NAME),("ledger",t.LEDGER_NAME)):
        check(a.view(ask,mods[m],"domainSeparator()",out=("bytes32",),tag=hex(height))[0]==
              t.domain_separator(name,st.CHAIN_ID,mods[m]),"domain mismatch "+m)
    check(st.block_identity(ask("eth_getBlockByNumber",[hex(height),False]))==(height,root),"finalized anchor changed")
    return dict(manifest=manifest,receipts=rows,finalizedHeight=height,finalizedHash=root,
                actualDeploymentGas=sum(r["gasUsed"] for r in rows),verification=report,
                exactCreationInputs=True,runtimeOutsideImmutableSlotsMatched=True,
                bondAndDomainsMatched=True,scope="Native canonical deployment; not SLA evidence")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--broadcast",type=Path,required=True)
    p.add_argument("--out",type=Path,default=Path("out"))
    args=p.parse_args()
    result=audit(LocalRPC("http://127.0.0.1:28545",timeout=15).request,
                 json.loads(args.plan.read_text()),json.loads(args.broadcast.read_text()),args.out)
    print(json.dumps(result,indent=2))
    print("V4_NATIVE_DEPLOYMENT_AUDIT_PASSED=true")

if __name__=="__main__":
    main()
