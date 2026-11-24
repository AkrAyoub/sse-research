#!/usr/bin/env python3
"""R247: compare REAL compiled Solc V2 contract ABI with every Python decoder.

No JSON-RPC, signer, wallet, transaction, Docker, or node control. This
checks the Foundry-built ABI rather than circular Python test fixtures:
21 unsigned contract action signatures, ALL native event topics and
indexed/data parameter order, lease/epoch/committee tuple return layouts,
selected monitor arrays and monitor confirmation getter. Fail closed on
ABI drift before any owner-approved on-chain deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from sse_pos_r226_adaptive_v2_transaction_planner import METHODS
from sse_pos_r227_v2_finalized_event_audit import MARKET_EVENTS,LEDGER_EVENTS
from sse_pos_r229_v2_finalized_lease_snapshot import (
    MARKET_LEASE,LEDGER_COMMITTEE,MARKET_EPOCH,LEDGER_EPOCH,
)

class Refused(ValueError):
    pass


def canonical_type(param):
    if type(param) is not dict or type(param.get("type")) is not str:
        raise Refused("invalid compiled ABI type")
    name=param["type"]
    if name.startswith("tuple"):
        components=param.get("components")
        if type(components) is not list:
            raise Refused("compiled tuple ABI has no members")
        return "("+",".join(canonical_type(x) for x in components)+")"+name[5:]
    if name not in ("address","bytes32","bytes","bool","uint8",
                    "uint64","uint256","address[]"):
        raise Refused("unexpected native V2 ABI type: "+name)
    return name


def signature(entry):
    if type(entry) is not dict or type(entry.get("name")) is not str or type(entry.get("inputs")) is not list:
        raise Refused("invalid compiled function/event declaration")
    return entry["name"]+"("+",".join(canonical_type(p) for p in entry["inputs"])+")"


def load_artifact(path):
    if not isinstance(path,Path) or not path.is_file() or path.is_symlink() or not 100<=path.stat().st_size<=12_000_000:
        raise Refused("missing, unbounded or symlinked actual compiled artifact")
    try:
        artifact=json.loads(path.read_text("utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise Refused("not an actual Foundry JSON artifact") from exc
    if type(artifact) is not dict or type(artifact.get("abi")) is not list:
        raise Refused("compiled Foundry ABI array absent")
    if type(artifact.get("deployedBytecode")) is not dict:
        raise Refused("compiled runtime bytecode envelope absent")
    hexcode=artifact["deployedBytecode"].get("object")
    if (type(hexcode) is not str or not hexcode.startswith("0x") or
        len(hexcode)<=4 or len(hexcode)%2):
        raise Refused("compiled runtime bytecode missing")
    return artifact


def index(abi,kind):
    found={}
    for item in abi:
        if type(item) is not dict:
            raise Refused("invalid compiled ABI entry")
        if item.get("type")!=kind:
            continue
        sig=signature(item)
        if sig in found:
            raise Refused("duplicate compiled "+kind+" declaration "+sig)
        found[sig]=item
    return found


def check_function(abi,signature_string,outputs=None):
    functions=index(abi,"function")
    item=functions.get(signature_string)
    if item is None:
        raise Refused("compiled ABI missing required "+signature_string)
    if outputs is None:
        return
    values=item.get("outputs")
    if type(values) is not list:
        raise Refused("compiled ABI missing outputs for "+signature_string)
    if len(outputs)==1 and type(outputs[0]) is tuple:
        expected=["("+",".join(field_type for _,field_type in outputs[0])+")"]
    else:
        expected=[kind for _,kind in outputs]
    actual=[canonical_type(x) for x in values]
    if actual!=expected:
        raise Refused("compiled return ABI changed for "+signature_string+
                      "; expected "+repr(expected)+"; got "+repr(actual))


def check_events(abi,definitions,role):
    actual=index(abi,"event")
    expect={d[0]:d for d in definitions}
    if set(actual)!=set(expect):
        raise Refused(role+" compiled events no longer match every Python decoder; "+
                      "missing="+repr(sorted(set(actual)-set(expect)))+
                      "; unexpected="+repr(sorted(set(expect)-set(actual))))
    for sig,entry in actual.items():
        _,indexed,fields=expect[sig]
        if entry.get("anonymous") not in (False,None):
            raise Refused("unexpected anonymous V2 event: "+sig)
        expected_flags=[True]*len(indexed)+[False]*len(fields)
        expected_types=[t for _,t in indexed]+[t for _,t in fields]
        inputs=entry["inputs"]
        flags=[x.get("indexed") for x in inputs]
        types=[canonical_type(x) for x in inputs]
        if flags!=expected_flags or types!=expected_types:
            raise Refused(role+" event index/data ABI changed: "+sig)


def check_artifact(role,artifact):
    abi=artifact["abi"]
    definitions=MARKET_EVENTS if role=="market" else LEDGER_EVENTS
    check_events(abi,definitions,role)
    funcs=index(abi,"function")
    checked=0
    for action,(permission,contract,sig,args) in METHODS.items():
        if contract!=role:
            continue
        if sig not in funcs:
            raise Refused(role+" action "+action+" ABI not found: "+sig)
        checked+=1
    if role=="market":
        check_function(abi,"lease(uint256)",[MARKET_LEASE])
        check_function(abi,"epoch(uint256,uint256)",[MARKET_EPOCH])
        check_function(abi,"getBid(uint256,uint256)",[(
            ("provider","address"),("epochFee","uint256"))])
        check_function(abi,"escrowAccounting()",[
            ("balanceWei","uint256"),("outstandingWei","uint256"),
            ("fullyCovered","bool")])
    else:
        check_function(abi,"committee(uint256)",[LEDGER_COMMITTEE])
        check_function(abi,"epoch(uint256,uint256)",[LEDGER_EPOCH])
        check_function(abi,"selected(uint256)",[
            ("selectedMonitors","address[]")])
        check_function(abi,"confirmedMonitor(uint256,address)",[
            ("confirmed","bool")])
    material=json.dumps(abi,sort_keys=True,separators=(",",":"),
                        ensure_ascii=True).encode("ascii")
    return {
        "contract":role,"unsignedRoleActionsChecked":checked,
        "eventSchemasChecked":len(definitions),
        "compiledAbiSha256":hashlib.sha256(material).hexdigest(),
        "actualCompiledRuntimeBytecodePresent":True,
        "onChainRuntimeVerified":False,
        "onChainTransactionSubmitted":False,
    }


def audit(market,ledger):
    m=check_artifact("market",market)
    l=check_artifact("ledger",ledger)
    if m["unsignedRoleActionsChecked"]+l["unsignedRoleActionsChecked"]!=len(METHODS):
        raise Refused("not all V2 role actions attested against compiled Solidity")
    return {
        "schema":"SSE_R247_COMPILED_V2_SOLIDITY_ABI_PARITY_V1",
        "chainTargetId":31340,
        "market":m,"ledger":l,
        "compiledFunctionSignaturesAndReturnTuplesMatch":True,
        "allCompiledEventSignaturesAndIndexedShapesMatch":True,
        "noPrivateKeysOrNetworkCalls":True,
        "onChainContractDeploymentVerified":False,
        "independentPhysicalSlaVerified":False,
    }


def main(argv=None):
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market-artifact",type=Path,default=root/"out/SSEAdaptiveMarketV2.sol/SSEAdaptiveMarketV2.json")
    p.add_argument("--ledger-artifact",type=Path,default=root/"out/SSEAdaptiveVoteLedger.sol/SSEAdaptiveVoteLedger.json")
    a=p.parse_args(argv)
    try:
        m=load_artifact(a.market_artifact)
        l=load_artifact(a.ledger_artifact)
        print(json.dumps(audit(m,l),sort_keys=True,indent=2))
        return 0
    except (Refused,ValueError,TypeError,OSError,KeyError) as exc:
        print("R247_COMPILED_V2_ABI_PARITY_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
