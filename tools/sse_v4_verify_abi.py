#!/usr/bin/env python3
"""Offline gate for compiled Foundry artifacts. No RPC, signing or deployment."""
import argparse
import json
from pathlib import Path
import sse_v4_abi as a

CONTRACTS = dict(market="SSEAdaptiveMarketV4", board="SSEServiceBoardV4",
                 registry="SSEMonitorRegistryV4", standby="SSEStandbyCommittee",
                 ledger="SSEAdaptiveVoteLedgerV4Candidate")
STRUCTS = [
    ("market", "lease(uint256)", a.LEASE_FIELDS),
    ("market", "epoch(uint256,uint256)", a.MARKET_EPOCH_FIELDS),
    ("market", "scientificEpoch(uint256,uint256)", a.SCIENTIFIC_EPOCH_FIELDS),
    ("board", "request(uint256)", a.REQUEST_FIELDS),
    ("ledger", "epoch(uint256,uint256)", a.LEDGER_EPOCH_FIELDS),
    ("ledger", "committee(uint256)", a.COMMITTEE_FIELDS),
    ("standby", "assignment(uint256)", a.ASSIGNMENT_FIELDS),
]
CALLS = {
    "market": [a.AWARD_AND_FUND_SIG, "resolveResidual(uint256,uint256," + a.tuple_type(a.ALLOCATION_FIELDS) + ",bytes,bytes)",
               "acceptLease(uint256,bytes32)", "startEpoch(uint256,bytes32)",
               "authenticateProviderResponse(uint256,uint256,bytes32,bytes)", "submitAcknowledgment(uint256,uint256,bytes)",
               "scientificAccounting(uint256)", "domainSeparator()", "withdraw()"] +
               [n+"(uint256)" for n in ("drawCommittee","activateCommittee","cancelExpiredDraw","cancelUnformed","cancelUnaccepted","closeLease","forceCloseIdle")] +
               [n+"(uint256,uint256)" for n in ("finalizeEpoch","closeEpochEvidence")],
    "board": ["createRequest("+a.tuple_type(a.REQUEST_INPUT_FIELDS)+")", "cancelRequest(uint256)",
              "placeBid(uint256,uint256,uint32,uint64,bytes32,bytes32)", "withdrawBid(uint256,uint256)",
              "bidsInRange(uint256,uint256,uint256)", "nextRequestId()"],
    "registry": ["register(uint256)","updateBond(uint256)","requestExit()","completeExit()","withdraw()",
                 "position(address)","available(address)","rosterLength()","activeEntries()","perSeatBond()",
                 "eligibleInRange(uint256,uint256,address,address)","reservedFor(uint256)"],
    "standby": ["confirm(uint256)","advance(uint256)","confirmed(uint256,address)"],
    "ledger": ["submitVoteDirect(uint256,uint256,uint8,bytes32)","selected(uint256)","withdraw()","voted(uint256,uint256,address)"],
}
def typ(p):
    t=p["type"]
    return "("+",".join(typ(x) for x in p["components"])+")"+t[5:] if t.startswith("tuple") else t

def signature(item):
    return item["name"]+"("+",".join(typ(x) for x in item["inputs"])+")"

def fields(items):
    return tuple((p["name"],typ(p)) for p in items)

def verify(artifacts):
    errors=[]
    functions={m:{signature(x):x for x in v if x["type"]=="function"} for m,v in artifacts.items()}
    for m,calls in CALLS.items():
        for sig in calls:
            if sig not in functions[m]: errors.append(f"{m}: missing function {sig}")
    for m,sig,expected in STRUCTS:
        entry=functions[m].get(sig)
        if not entry or len(entry["outputs"])!=1 or fields(entry["outputs"][0].get("components",[]))!=expected:
            errors.append(f"{m}: struct output mismatch {sig}")
    for m,sig,index,expected in [
        ("market",a.AWARD_AND_FUND_SIG,2,a.TERMS_FIELDS),
        ("board","createRequest("+a.tuple_type(a.REQUEST_INPUT_FIELDS)+")",0,a.REQUEST_INPUT_FIELDS),
        ("market","resolveResidual(uint256,uint256,"+a.tuple_type(a.ALLOCATION_FIELDS)+",bytes,bytes)",2,a.ALLOCATION_FIELDS)]:
        entry=functions[m].get(sig)
        if not entry or fields(entry["inputs"][index].get("components",[]))!=expected:
            errors.append(f"{m}: input tuple mismatch {sig}")
    bid=functions["board"].get("bidsInRange(uint256,uint256,uint256)")
    if not bid or len(bid["outputs"])!=1 or bid["outputs"][0]["type"]!="tuple[]" or fields(bid["outputs"][0].get("components",[]))!=a.BID_FIELDS:
        errors.append("board: bid array output mismatch")
    for name,(module,expected) in a.EVENTS.items():
        for m in (("market","registry","ledger") if module=="*" else (module,)):
            matches=[x for x in artifacts[m] if x["type"]=="event" and signature(x)==a.event_signature(name)]
            if len(matches)!=1 or matches[0].get("anonymous") or tuple((p["name"],typ(p),p["indexed"]) for p in matches[0]["inputs"])!=tuple(expected):
                errors.append(f"{m}: event mismatch {name}")
    for m in ("market","registry","ledger"):
        for sig in ("withdrawable(address)",):
            if sig not in functions[m]: errors.append(f"{m}: missing {sig}")
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=Path("out"))
    args=p.parse_args()
    artifacts={}
    for m,c in CONTRACTS.items():
        path=args.out/(c+".sol")/(c+".json")
        artifacts[m]=json.loads(path.read_text())["abi"]
    errors=verify(artifacts)
    print(json.dumps({"schema":"SSE_V4_ABI_CHECK_V1","passed":not errors,"errors":errors,
                      "scope":"listed application functions, tuple fields and event layouts; not digest or runtime proof"},indent=2))
    return int(bool(errors))
if __name__=="__main__":
    raise SystemExit(main())
