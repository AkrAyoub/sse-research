#!/usr/bin/env python3
"""R227: bounded READ-ONLY finalized SSE V2 on-chain event verifier.

Uses an operator-supplied R206 deployment manifest, verified against the
actual original chain31340 genesis, finalized creation receipt, immutable
runtime SHA-256, and bidirectional market/ledger address bindings. Event
proofs verify canonical block hashes, not remote physical resource/SLA truth.
NO wallets, eth_sendRawTransaction, signatures, Docker or node control.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from sse_challenge import keccak256
from sse_pos_r206_adaptive_v2_deployment_audit import (
    Refused as AuditRefused, load as load_manifest, rpc, verify,
)

HEX32=re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")
HEXDATA=re.compile(r"0x(?:[0-9a-fA-F]{64})*\Z")
HNUM=re.compile(r"0x[0-9a-fA-F]+\Z")
BATCH_BLOCKS=256
MAX_BLOCKS=50_000
MAX_EVENTS=4096

# All event types are statically encoded; Solidity enum Outcome is uint8.
# A tuple: (event canonical signature, indexed fields, data fields).
MARKET_EVENTS=(
    ("MonitorJoined(address,uint256)",(("monitor","address"),),(("bondWei","uint256"),)),
    ("MonitorExited(address)",(("monitor","address"),),()),
    ("ResourceRequested(uint256,address,bytes32,bytes32)",
     (("requestId","uint256"),("consumer","address")),
     (("profileHash","bytes32"),("policyHash","bytes32"))),
    ("BidPlaced(uint256,uint256,address,uint256)",
     (("requestId","uint256"),("bidIndex","uint256"),("provider","address")),
     (("epochFeeWei","uint256"),)),
    ("LeaseFunded(uint256,uint256,address,address,uint256,uint256)",
     (("leaseId","uint256"),("requestId","uint256")),
     (("consumer","address"),("provider","address"),
      ("serviceWei","uint256"),("monitorWei","uint256"))),
    ("EligibilityFrozen(uint256,bytes32,uint256,uint256)",
     (("leaseId","uint256"),("snapshotRoot","bytes32")),
     (("eligibleCount","uint256"),("entropyBlock","uint256"))),
    ("CommitteeDrawn(uint256,bytes32,uint256,uint256)",
     (("leaseId","uint256"),("entropyHash","bytes32")),
     (("seats","uint256"),("quorum","uint256"))),
    ("ProviderAccepted(uint256)",(("leaseId","uint256"),),()),
    ("EpochStarted(uint256,uint256,bytes32)",
     (("leaseId","uint256"),("epochId","uint256")),(("requestHash","bytes32"),)),
    ("ProviderResponseVerified(uint256,uint256,bytes32)",
     (("leaseId","uint256"),("epochId","uint256")),(("responseHash","bytes32"),)),
    ("EpochConcluded(uint256,uint256,uint8)",
     (("leaseId","uint256"),("epochId","uint256")),(("outcome","uint8"),)),
    ("InconclusiveAllocated(uint256,uint256,uint256,uint256)",
     (("leaseId","uint256"),("epochId","uint256")),
     (("consumerShareWei","uint256"),("providerShareWei","uint256"))),
    ("LeaseIdleExpired(uint256,uint256,uint256)",
     (("leaseId","uint256"),),
     (("unresolvedFeeWei","uint256"),("refundedUnusedWei","uint256"))),
    ("LeaseClosed(uint256,uint256)",(("leaseId","uint256"),),(("refundWei","uint256"),)),
    ("LeaseCancelled(uint256)",(("leaseId","uint256"),),()),
    ("Withdrawal(address,uint256)",(("account","address"),),(("amountWei","uint256"),)),
)
LEDGER_EVENTS=(
    ("CommitteeFrozen(uint256,bytes32,uint256,uint256)",
     (("leaseId","uint256"),("snapshotRoot","bytes32")),
     (("seats","uint256"),("quorum","uint256"))),
    ("SeatSelected(uint256,address)",
     (("leaseId","uint256"),("monitor","address")),()),
    ("SeatConfirmed(uint256,address,uint256)",
     (("leaseId","uint256"),("monitor","address")),(("confirmed","uint256"),)),
    ("CommitteeReady(uint256)",(("leaseId","uint256"),),()),
    ("CommitteeConfirmationExpired(uint256,uint256)",
     (("leaseId","uint256"),),(("missing","uint256"),)),
    ("EpochOpened(uint256,uint256,bytes32)",
     (("leaseId","uint256"),("epochId","uint256")),(("requestHash","bytes32"),)),
    ("ResponseAuthenticated(uint256,uint256,bytes32)",
     (("leaseId","uint256"),("epochId","uint256")),(("responseHash","bytes32"),)),
    ("VoteRecorded(uint256,uint256,address,uint8,bytes32)",
     (("leaseId","uint256"),("epochId","uint256"),("monitor","address")),
     (("outcome","uint8"),("evidenceHash","bytes32"))),
    ("MonitoringSealed(uint256,uint256,uint8)",
     (("leaseId","uint256"),("epochId","uint256")),(("outcome","uint8"),)),
    ("ReportRewardEarned(uint256,uint256,address,uint256)",
     (("leaseId","uint256"),("epochId","uint256"),("monitor","address")),
     (("amountWei","uint256"),)),
    ("ReportingClosed(uint256,uint256)",
     (("leaseId","uint256"),),(("unspentRefundWei","uint256"),)),
    ("Withdrawal(address,uint256)",(("beneficiary","address"),),(("amountWei","uint256"),)),
)


class Refused(ValueError):
    pass


def event_topic(signature):
    return "0x"+keccak256(signature.encode("ascii")).hex()


def specs():
    return {
        role:{event_topic(sig):(sig.split("(")[0],indexed,data)
              for sig,indexed,data in events}
        for role,events in (("market",MARKET_EVENTS),("ledger",LEDGER_EVENTS))
    }


def hex_number(raw,label):
    if type(raw) is not str or not HNUM.fullmatch(raw):
        raise Refused("invalid "+label)
    return int(raw,16)


def hex_hash(raw,label):
    if type(raw) is not str or not HEX32.fullmatch(raw):
        raise Refused("invalid "+label)
    return raw.lower()


def decode_word(word,kind):
    if type(word) is not bytes or len(word)!=32:
        raise Refused("invalid event ABI word")
    if kind=="bytes32":
        return "0x"+word.hex()
    if kind=="address":
        if any(word[:12]):
            raise Refused("noncanonical ABI address padding")
        return "0x"+word[12:].hex()
    if kind=="uint8":
        if any(word[:31]) or word[31]>2:
            raise Refused("noncanonical SSE Outcome value")
        return word[31]
    if kind=="uint256":
        # Use JSON decimal strings to avoid JavaScript precision loss.
        return str(int.from_bytes(word,"big"))
    raise Refused("unsupported event ABI type")


def parse_log(log, addresses, selectors):
    if type(log) is not dict or log.get("removed") is not False:
        raise Refused("missing or reorg-removed event log")
    address=log.get("address")
    if type(address) is not str or not ADDRESS.fullmatch(address):
        raise Refused("invalid event emitting address")
    address=address.lower()
    contract=next((name for name,addr in addresses.items()
                   if addr.lower()==address),None)
    if contract is None:
        raise Refused("nonattested event emitter")
    topics=log.get("topics")
    if type(topics) is not list or not 1<=len(topics)<=4:
        raise Refused("invalid EVM event topic count")
    topic=[hex_hash(t,"event topic") for t in topics]
    spec=selectors[contract].get(topic[0])
    if spec is None:
        raise Refused("unknown contract event topic; source ABI changed")
    name,indexed,data_fields=spec
    if len(topics)!=len(indexed)+1:
        raise Refused("wrong indexed event word count")
    data=log.get("data")
    if type(data) is not str or not HEXDATA.fullmatch(data):
        raise Refused("malformed event data ABI")
    raw=bytes.fromhex(data[2:])
    if len(raw)!=32*len(data_fields):
        raise Refused("wrong event data ABI length")
    values={}
    for i,(field,kind) in enumerate(indexed):
        values[field]=decode_word(bytes.fromhex(topic[i+1][2:]),kind)
    for i,(field,kind) in enumerate(data_fields):
        values[field]=decode_word(raw[i*32:(i+1)*32],kind)
    return {
        "contract":contract, "event":name, "fields":values,
        "blockNumber":hex_number(log.get("blockNumber"),"event block"),
        "blockHash":hex_hash(log.get("blockHash"),"event block hash"),
        "transactionHash":hex_hash(log.get("transactionHash"),"event tx hash"),
        "logIndex":hex_number(log.get("logIndex"),"event index"),
    }


def audit_events(manifest,rpc_url,*,start=None,transport=rpc,verified=None):
    if verified is None:
        verified=verify(manifest,rpc_url,transport=transport)
    deployment=verified["deploymentBlock"]
    finalized=verified["finalizedExecutionHeight"]
    if type(deployment) is not int or type(finalized) is not int or finalized<deployment:
        raise Refused("unusable finalized deployment boundary")
    if start is None:
        start=deployment
    if type(start) is not int or not deployment<=start<=finalized:
        raise Refused("requested range not finalized or precedes deployment")
    if finalized-start+1>MAX_BLOCKS:
        raise Refused("audit exceeds bounded range; pass a later --from-block")
    addresses={
        "market":manifest["market"]["address"].lower(),
        "ledger":manifest["ledger"]["address"].lower(),
    }
    selectors=specs()
    records=[]
    seen=set()
    blocks={}
    for first in range(start,finalized+1,BATCH_BLOCKS):
        last=min(finalized,first+BATCH_BLOCKS-1)
        raw=transport(rpc_url,"eth_getLogs",[{
            "address":[addresses["market"],addresses["ledger"]],
            "fromBlock":hex(first),"toBlock":hex(last)
        }])
        if type(raw) is not list or len(records)+len(raw)>MAX_EVENTS:
            raise Refused("unbounded or invalid finalized event response")
        for event in raw:
            item=parse_log(event,addresses,selectors)
            if not first<=item["blockNumber"]<=last:
                raise Refused("returned log is outside requested finalized range")
            key=(item["transactionHash"],item["logIndex"])
            if key in seen:
                raise Refused("duplicate log; RPC response inconsistent")
            seen.add(key)
            number=item["blockNumber"]
            if number not in blocks:
                block=transport(rpc_url,"eth_getBlockByNumber",[hex(number),False])
                if type(block) is not dict or hex_number(block.get("number"),"canonical height")!=number:
                    raise Refused("canonical event block missing")
                blocks[number]=hex_hash(block.get("hash"),"canonical event block hash")
            if blocks[number]!=item["blockHash"]:
                raise Refused("event hash is not canonical at finalized height")
            records.append(item)
    records.sort(key=lambda e:(e["blockNumber"],e["logIndex"],e["transactionHash"]))
    return {
        "schema":"SSE_R227_FINALIZED_V2_EVENTS_READONLY_V1",
        "chainId":31340,"fromBlock":start,"throughFinalizedBlock":finalized,
        "fullDeploymentHistoryCovered":start==deployment,
        "attestedMarket":addresses["market"],"attestedLedger":addresses["ledger"],
        "events":records,"eventCount":len(records),
        "finalizedRuntimeAndBindingsVerified":True,
        "canonicalBlockHashVerifiedPerEvent":True,
        "cryptographicEventAttributionVerified":False,
        "providerPhysicalWorkVerified":False,
        "monitorEvidenceTruthVerified":False,
        "ethereumTransactionSignedOrSubmitted":False,
        "dockerOrValidatorChanged":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--from-block",type=int)
    a=p.parse_args(argv)
    try:
        m=load_manifest(a.manifest)
        report=audit_events(m,a.rpc,start=a.from_block)
        print(json.dumps(report,sort_keys=True,indent=2))
        return 0
    except (AuditRefused,Refused,ValueError,TypeError,OSError,KeyError) as exc:
        print("R227_FINALIZED_V2_EVENT_AUDIT_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
