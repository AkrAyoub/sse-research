#!/usr/bin/env python3
"""R229: canonical finalized original-chain V2 lease/committee/epoch inspector.

A manifest must pass the R206 deployment/runtime/immutable binding audit.
All market and vote-ledger eth_call state is read at ONE finalized EL block.
This is source-only until deployed; does not prove real compute, signer
independence, SLA soundness, tx finality on a remote physical monitor,
Beacon health, or actual role authorization. No private keys or writes.
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

HEX=re.compile(r"0x(?:[0-9a-fA-F]{2})*\Z")
MARKET_LEASE=(
    ("consumer","address"),("provider","address"),
    ("profileHash","bytes32"),("policyHash","bytes32"),
    ("endpointHash","bytes32"),("snapshotRoot","bytes32"),
    ("requestId","uint256"),("epochFeeWei","uint256"),
    ("maxEpochs","uint256"),("nextEpoch","uint256"),
    ("closedEpochs","uint256"),("serviceRemainingWei","uint256"),
    ("monitorBudgetWei","uint256"),("perMonitorEpochRewardWei","uint256"),
    ("requiredFaultTolerance","uint256"),("gasBoundSeats","uint256"),
    ("eligibleCount","uint256"),("confirmationSeconds","uint64"),
    ("responseSeconds","uint64"),("monitoringSeconds","uint64"),
    ("entropyBlock","uint256"),("phase","uint8"),
    ("providerAccepted","bool"),
    ("lastProgressAt","uint64"),
)
LEDGER_COMMITTEE=(
    ("consumer","address"),("provider","address"),
    ("eligibilitySnapshotRoot","bytes32"),
    ("seats","uint256"),("quorum","uint256"),
    ("requiredFaultTolerance","uint256"),("confirmationDeadline","uint64"),
    ("initialized","bool"),("ready","bool"),("confirmationExpired","bool"),
    ("rewardPerReportWei","uint256"),("originalReportBudgetWei","uint256"),
    ("unspentReportBudgetWei","uint256"),("maxPayableEpochs","uint256"),
    ("openedEpochs","uint256"),("sealedEpochs","uint256"),
    ("reportingClosed","bool"),
)
MARKET_EPOCH=(
    ("requestHash","bytes32"),("responseHash","bytes32"),
    ("feeWei","uint256"),("nonce","uint256"),("exists","bool"),
    ("resolved","bool"),
)
LEDGER_EPOCH=(
    ("requestHash","bytes32"),("responseHash","bytes32"),
    ("responseDeadline","uint64"),("monitoringClose","uint64"),
    ("successVotes","uint256"),("failureVotes","uint256"),
    ("totalVotes","uint256"),("exists","bool"),
    ("responseAuthenticated","bool"),("monitoringSealed","bool"),
    ("outcome","uint8"),
)


class Refused(ValueError):
    pass


def read_word(value, kind):
    if len(value)!=32:
        raise Refused("wrong ABI word size")
    n=int.from_bytes(value,"big")
    if kind=="address":
        if any(value[:12]):
            raise Refused("noncanonical ABI address")
        return "0x"+value[12:].hex()
    if kind=="bytes32":
        return "0x"+value.hex()
    if kind=="bool":
        if n not in (0,1):
            raise Refused("noncanonical EVM boolean")
        return bool(n)
    if kind=="uint8" and n>255:
        raise Refused("noncanonical uint8")
    if kind=="uint64" and n>=2**64:
        raise Refused("noncanonical uint64")
    if kind in ("uint8","uint64","uint256"):
        return n
    raise Refused("unknown ABI field type")


def decode_struct(raw,schema):
    if type(raw) is not str or not HEX.fullmatch(raw):
        raise Refused("invalid hex ABI result")
    words=bytes.fromhex(raw[2:])
    if len(words)!=32*len(schema):
        raise Refused("unexpected ABI record length")
    return {name:read_word(words[i*32:(i+1)*32],kind)
            for i,(name,kind) in enumerate(schema)}


def decode_addresses(raw):
    if type(raw) is not str or not HEX.fullmatch(raw):
        raise Refused("invalid selected monitor ABI")
    data=bytes.fromhex(raw[2:])
    if len(data)<64 or len(data)%32:
        raise Refused("invalid ABI dynamic address array")
    offset=int.from_bytes(data[:32],"big")
    count=int.from_bytes(data[32:64],"big")
    if offset!=32 or count>64 or len(data)!=64+32*count:
        raise Refused("bad bounded selected monitor offset/count")
    addresses=[]
    for i in range(count):
        address=read_word(data[64+i*32:96+i*32],"address")
        if address=="0x"+"00"*20 or address in addresses:
            raise Refused("zero or duplicate committee monitor")
        addresses.append(address)
    return addresses


def query(transport,url,address,signature,args,block):
    data=keccak256(signature.encode("ascii"))[:4]+b"".join(
        a.to_bytes(32,"big") for a in args)
    raw=transport(url,"eth_call",[{"to":address,"data":"0x"+data.hex()},hex(block)])
    if type(raw) is not str or not HEX.fullmatch(raw):
        raise Refused("malformed eth_call output")
    return raw


def inspect(manifest,rpc_url,lease_id,epoch_id=None,*,transport=rpc,attestation=None):
    if type(lease_id) is not int or not 1<=lease_id<2**256:
        raise Refused("invalid lease ID")
    if epoch_id is not None and (type(epoch_id) is not int or not 0<=epoch_id<2**256):
        raise Refused("invalid epoch ID")
    proof=attestation if attestation is not None else verify(manifest,rpc_url,transport=transport)
    height=proof["finalizedExecutionHeight"]
    market=manifest["market"]["address"]
    ledger=manifest["ledger"]["address"]
    m=lambda sig,*args: query(transport,rpc_url,market,sig,args,height)
    l=lambda sig,*args: query(transport,rpc_url,ledger,sig,args,height)

    lease=decode_struct(m("lease(uint256)",lease_id),MARKET_LEASE)
    if lease["consumer"]=="0x"+"00"*20 or lease["provider"]=="0x"+"00"*20:
        raise Refused("lease does not exist at finalized execution height")
    committee=decode_struct(l("committee(uint256)",lease_id),LEDGER_COMMITTEE)
    selected=decode_addresses(l("selected(uint256)",lease_id))
    if lease["phase"]>6 or lease["nextEpoch"]>lease["maxEpochs"] or lease["closedEpochs"]>lease["nextEpoch"]:
        raise Refused("invalid finalized V2 lease lifecycle")
    if committee["initialized"]:
        if (committee["consumer"]!=lease["consumer"] or
            committee["provider"]!=lease["provider"] or
            committee["eligibilitySnapshotRoot"]!=lease["snapshotRoot"] or
            committee["requiredFaultTolerance"]!=lease["requiredFaultTolerance"] or
            committee["seats"]!=len(selected) or committee["seats"]>64 or
            committee["seats"]<3*committee["requiredFaultTolerance"]+1 or
            committee["quorum"]!=2*committee["seats"]//3+1 or
            lease["consumer"] in selected or lease["provider"] in selected):
            raise Refused("market and ledger committee conservation/policy mismatch")
    elif selected:
        raise Refused("selected seats on uninitialized committee")
    escrow=decode_struct(m("escrowAccounting()"),(
        ("balanceWei","uint256"),("outstandingWei","uint256"),("fullyCovered","bool")))
    if not escrow["fullyCovered"] or escrow["balanceWei"]<escrow["outstandingWei"]:
        raise Refused("actual finalized market escrow liabilities not covered")
    if epoch_id is not None:
        me=decode_struct(m("epoch(uint256,uint256)",lease_id,epoch_id),MARKET_EPOCH)
        le=decode_struct(l("epoch(uint256,uint256)",lease_id,epoch_id),LEDGER_EPOCH)
        if me["exists"]!=le["exists"]:
            raise Refused("market/ledger disagree on epoch existence")
        if me["exists"] and (
            me["requestHash"]!=le["requestHash"] or
            me["feeWei"]!=lease["epochFeeWei"] or
            le["outcome"]>2 or le["totalVotes"]>committee["seats"] or
            le["successVotes"]+le["failureVotes"]!=le["totalVotes"] or
            (le["responseAuthenticated"] and me["responseHash"]!=le["responseHash"])
        ):
            raise Refused("market/ledger recorded epoch discrepancy")
        epoch={"market":me,"ledger":le}
    else:
        epoch=None
    return {
        "schema":"SSE_R229_FINALIZED_V2_LEASE_READONLY_V1",
        "chainId":31340,"finalizedExecutionHeight":height,
        "market":market,"ledger":ledger,
        "leaseId":lease_id,"epochId":epoch_id,
        "lease":lease,"committee":committee,"selectedMonitors":selected,
        "epoch":epoch,"marketEscrowAccounting":escrow,
        "deploymentRuntimeAndWiringAttested":True,
        "consumerProviderAndMonitorPhysicalIndependenceVerified":False,
        "actualDockerDeliveryVerified":False,
        "onChainMonitorVotesImplyTruth":False,
        "signedOrBroadcast":False,
        "validatorOrDockerChanged":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--rpc",required=True,choices=("http://127.0.0.1:18545","http://127.0.0.1:28545"))
    p.add_argument("--lease-id",required=True,type=int)
    p.add_argument("--epoch-id",type=int)
    a=p.parse_args(argv)
    try:
        result=inspect(load_manifest(a.manifest),a.rpc,a.lease_id,a.epoch_id)
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (Refused,AuditRefused,TypeError,KeyError,ValueError,OSError) as exc:
        print("R229_FINALIZED_LEASE_SNAPSHOT_REFUSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
