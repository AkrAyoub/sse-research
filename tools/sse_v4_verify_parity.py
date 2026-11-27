#!/usr/bin/env python3
"""Verify V4 Foundry parity exports offline; no RPC, signing or deployment.

Owner must supply the successful isolated test's original -vv log.
This verifies encoding consistency, not log provenance or runtime correctness.
"""
import argparse
import json
import re
from pathlib import Path

from eth_abi import decode, encode
from sse_challenge import keccak256
import sse_v4_terms as t

FIELDS = {
    "TERMS": 35 * 32,
    "TERMS_HASH": 32,
    "LEDGER": 20,
    "MARKET_DOMAIN": 32,
    "LEDGER_DOMAIN": 32,
}


def parse_exports(log):
    found = {}
    for line in log.splitlines():
        if not line.strip().startswith("V4_PARITY_"):
            continue
        match = re.fullmatch(r"\s*V4_PARITY_([A-Z_]+):\s*(0x[0-9a-fA-F]+)\s*", line)
        if not match:
            raise ValueError("malformed parity export")
        name, value = match.groups()
        if name not in FIELDS or name in found:
            raise ValueError("unexpected or duplicate parity export: " + name)
        raw = bytes.fromhex(value[2:])
        if len(raw) != FIELDS[name]:
            raise ValueError("wrong parity field length: " + name)
        found[name] = raw
    if set(found) != set(FIELDS):
        raise ValueError("missing parity exports: " + ", ".join(sorted(set(FIELDS) - set(found))))
    return found


def verify_exports(log):
    f = parse_exports(log)
    # Explicit schema mirrors the contract ABI, independent of the helper's
    # tuple constants and field ordering.
    schema = [
        "uint256", "address", "uint256", "uint256",
        "(address,uint8,uint32,uint32,uint16,uint16,uint16,uint64,bytes32,bytes32,bytes32,uint256,uint256,uint256)",
        "(address,bool,uint32,uint64,uint256,bytes32,bytes32)",
        "(uint64,uint64,uint64,uint64,uint64,uint64,uint256,uint256,bool,bool)",
    ]
    chain, market, lid, bid_index, q, b, terms = decode(schema, f["TERMS"], strict=True)
    if chain != 31340 or lid <= 0 or market == "0x" + "00" * 20:
        raise ValueError("unexpected parity context")
    if encode(schema, (chain, market, lid, bid_index, q, b, terms)) != f["TERMS"]:
        raise ValueError("noncanonical terms bytes")
    ledger = "0x" + f["LEDGER"].hex()
    if ledger == market or ledger == "0x" + "00" * 20:
        raise ValueError("invalid ledger address")
    request = dict(zip(("consumer","status","fixedEpochs","maxEpochs","seats","standbys","faultTolerance",
                        "biddingClose","profileHash","policyHash","artifactCommitment","maxEpochFee",
                        "perReportReward","awardedBid"), q))
    bid = dict(zip(("provider","withdrawn","epochs","expiry","epochFee","endpointHash","offerHash"), b))
    lease_terms = dict(zip(("acceptSeconds","confirmationRoundSeconds","responseSeconds","monitoringSeconds",
                            "evidenceSeconds","idleSeconds","reservationFee","exposureBudget",
                            "conditionalQuorumPolicy","responseAdmitsReceipt"), terms))
    checks = {
        "rawTermsHash": keccak256(f["TERMS"]) == f["TERMS_HASH"],
        "reconstructedTermsHash": t.terms_hash(chain, market, lid, bid_index, request, bid, lease_terms) == f["TERMS_HASH"],
        "marketDomain": t.domain_separator(t.MARKET_NAME, chain, market) == f["MARKET_DOMAIN"],
        "ledgerDomain": t.domain_separator(t.LEDGER_NAME, chain, ledger) == f["LEDGER_DOMAIN"],
    }
    if not all(checks.values()):
        raise ValueError("parity mismatch: " + ", ".join(k for k, v in checks.items() if not v))
    return dict(chainId=chain, market=market, ledger=ledger, leaseId=lid,
                termsHash="0x" + f["TERMS_HASH"].hex(), checks=checks)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path)
    a = p.parse_args()
    try:
        result = verify_exports(a.log.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        p.exit(1, "V4_PARITY_FAILED: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    print("V4_TERMS_AND_DOMAINS_PARITY_PASSED")


if __name__ == "__main__":
    main()
