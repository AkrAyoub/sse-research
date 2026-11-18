#!/usr/bin/env python3
"""Read-only four-RPC QBFT block experiment sampler.

Records observed block periods, bytes, gas, transactions and hash agreement.
Block header "miner" is NOT assumed to identify the QBFT proposer or reward
recipient; inspect consensus signatures and balances separately. A manifest
never proves four independent physical operators.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys

from sse_qbft_readiness import (rpc, inspect_many, QBFTReadinessError)
from sse_network_peers import verify, _read, MAX_MANIFEST_BYTES, PeerCatalogError


class SampleError(ValueError):
    pass


def quantity(value, *, field: str) -> int:
    if (type(value) is not str or not value.startswith("0x")
            or not 1 < len(value) <= 66):
        raise SampleError("invalid quantity: " + field)
    try:
        n = int(value[2:], 16)
    except ValueError:
        raise SampleError("non-hex quantity: " + field) from None
    if n < 0:
        raise SampleError("negative quantity")
    return n


def percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    i = max(0, min(len(s)-1, math.ceil(q * len(s))-1))
    return float(s[i])


def sample_rpc(urls: list[str], *, chain_id: int, genesis_hash: str,
               expected_validators: int, blocks: int = 40, call=rpc) -> dict:
    if type(blocks) is not int or not 2 <= blocks <= 600:
        raise SampleError("sample 2-600 final blocks only")
    gate = inspect_many(urls, chain_id=chain_id, genesis_hash=genesis_hash,
                        expected_validators=expected_validators, call=call,
                        require_four=True)
    head = gate["commonBlockNumber"]
    if head < blocks:
        raise SampleError("chain not old enough for requested sample window")
    start = head - blocks + 1
    observations = []
    for n in range(start, head+1):
        items=[]
        for url in urls:
            block = call(url, "eth_getBlockByNumber", [hex(n), False])
            if type(block) is not dict:
                raise SampleError("missing canonical block")
            items.append(block)
        hashes = [x.get("hash") for x in items]
        if (any(type(h) is not str or len(h) != 66 for h in hashes)
                or len({h.lower() for h in hashes}) != 1):
            raise SampleError("historical fork or inconsistent block at height " + str(n))
        b = items[0]
        if quantity(b.get("number"), field="number") != n:
            raise SampleError("block number disagreement")
        transactions = b.get("transactions")
        if type(transactions) is not list:
            raise SampleError("missing transactions")
        gas = quantity(b.get("gasUsed"), field="gasUsed")
        limit = quantity(b.get("gasLimit"), field="gasLimit")
        if gas > limit or limit < 1000000:
            raise SampleError("nonsensical gas use")
        obs = {
            "number": n, "hash": hashes[0].lower(),
            "timestamp": quantity(b.get("timestamp"), field="timestamp"),
            "gasUsed": gas, "gasLimit": limit,
            "blockSizeBytes": quantity(b.get("size"), field="size"),
            "transactionCount": len(transactions),
        }
        observations.append(obs)
    gaps = [observations[i]["timestamp"]-observations[i-1]["timestamp"]
            for i in range(1,len(observations))]
    if any(x < 0 or x > 3600 for x in gaps):
        raise SampleError("invalid or non-monotonic block timestamps")
    transactions = sum(x["transactionCount"] for x in observations)
    elapsed = observations[-1]["timestamp"]-observations[0]["timestamp"]
    return {
        "kind": "SSE_QBFT_OBSERVED_BLOCKS_V1",
        "chainId": chain_id, "genesisHash": genesis_hash.lower(),
        "rpcNodes": len(urls), "sampleBlocks": len(observations),
        "firstBlock": start, "lastBlock": head,
        "meanBlockIntervalSeconds": statistics.mean(gaps),
        "p50IntervalSeconds": percentile(gaps, .5),
        "p95IntervalSeconds": percentile(gaps, .95),
        "maxIntervalSeconds": max(gaps),
        "totalTransactionsIncluded": transactions,
        "measuredTransactionsPerSecond": transactions / elapsed if elapsed > 0 else None,
        "meanBlockSizeBytes": statistics.mean(b["blockSizeBytes"] for b in observations),
        "meanGasUsed": statistics.mean(b["gasUsed"] for b in observations),
        "totalGasUsed": sum(b["gasUsed"] for b in observations),
        "blocks": observations,
        "readiness": gate,
        "observedFromRPC": True,
        "proposerRewardsMeasured": False,
        "physicalVMIndependenceProved": False,
        "externalParticipantsTested": False,
        "transactionsSent": False,
    }


def _write_new(path: Path, value: dict):
    if not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise SampleError("experiment result must be a NEW file in an existing directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2)+"\n")


def main(argv=None):
    p=argparse.ArgumentParser(description="Measure observed QBFT headers without submitting tx")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    p.add_argument("--genesis-hash", required=True)
    p.add_argument("--rpc-url", action="append", required=True)
    p.add_argument("--blocks", type=int, default=40)
    p.add_argument("--output", type=Path, required=True)
    a=p.parse_args(argv)
    try:
        envelope=json.loads(_read(a.manifest,MAX_MANIFEST_BYTES))
        trusted=verify(envelope,_read(a.public_key,8192),
                       chain_id=31338,genesis_hash=a.genesis_hash)
        result=sample_rpc(a.rpc_url,chain_id=31338,
                          genesis_hash=trusted["genesisHash"],
                          expected_validators=trusted["validators"],blocks=a.blocks)
        _write_new(a.output,result)
        print(json.dumps({k:v for k,v in result.items()
                          if k not in ("blocks","readiness")},indent=2,sort_keys=True))
        return 0
    except (SampleError,QBFTReadinessError,PeerCatalogError,OSError,
            ValueError,TypeError) as exc:
        print("SSE_QBFT_SAMPLE_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
