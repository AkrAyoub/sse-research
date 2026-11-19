#!/usr/bin/env python3
"""R20: collect PUBLIC, independently supplied genesis validator declarations.

No signing, private keys, seed phrases, fake deposits, or claimed independence.
The output is a provisional input to eth-beacon-genesis --additional-validators;
it is NOT a genesis.ssz, cryptographic proof of BLS custody, or permission to
join this permissionless chain after genesis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "SSE_R20_PUBLIC_GENESIS_VALIDATORS_V1"
OPERATOR_ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")
HEX_PUB = re.compile(r"0x[0-9a-f]{96}\Z")
HEX_WD = re.compile(r"0x01[0]{22}[0-9a-f]{40}\Z")
BALANCE_GWEI = 32_000_000_000
MAX_BYTES_PER_FILE = 65536
MAX_VALIDATORS_PER_OPERATOR = 4096
REQUIRED_KEYS = {"schema", "operatorId", "validators"}
VALIDATOR_KEYS = {"pubkey", "withdrawalCredentials", "balanceGwei"}


class CeremonyError(ValueError):
    pass


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CeremonyError("duplicate JSON property")
        result[key] = value
    return result


def read_contribution(path: Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES_PER_FILE:
        raise CeremonyError("input must be ordinary, nonsymlink JSON under 64 KiB")
    try:
        d = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_json)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CeremonyError("invalid UTF-8 JSON contribution") from exc
    if type(d) is not dict or set(d) != REQUIRED_KEYS or d["schema"] != SCHEMA:
        raise CeremonyError("invalid contribution schema or unexpected/secret property")
    op = d["operatorId"]
    if type(op) is not str or not OPERATOR_ID.fullmatch(op):
        raise CeremonyError("invalid declarative operator label")
    vals = d["validators"]
    if type(vals) is not list or not 1 <= len(vals) <= MAX_VALIDATORS_PER_OPERATOR:
        raise CeremonyError("empty or oversized validator contribution")
    result = []
    for v in vals:
        if type(v) is not dict or set(v) != VALIDATOR_KEYS:
            raise CeremonyError("validator entry has unexpected fields (no secrets)")
        pub, wd, amt = v["pubkey"], v["withdrawalCredentials"], v["balanceGwei"]
        if (type(pub) is not str or not HEX_PUB.fullmatch(pub)
                or int(pub, 16) == 0):
            raise CeremonyError("invalid nonzero 48-byte public validator BLS key")
        if (type(wd) is not str or not HEX_WD.fullmatch(wd)
                or int(wd[-40:], 16) == 0):
            raise CeremonyError("withdrawal credentials must be 0x01 + 11 zero bytes + independent 20-byte nonzero EL address")
        if type(amt) is not int or amt != BALANCE_GWEI:
            raise CeremonyError("genesis validator effective balance must be exactly 32 TEST ETH in Gwei")
        result.append((pub, wd, amt))
    return op, result


def collect(paths: list[Path], *, min_operators: int,
            min_validators: int) -> tuple[str, dict]:
    # The initiating operators explicitly publish these *genesis-snapshot*
    # safety thresholds; NO program-wide fixed operator/validator roster.
    # Future validator deposits remain permissionless and uncapped.
    if (type(min_operators) is not int or type(min_validators) is not int
            or min_operators < 2 or min_validators < 1):
        raise CeremonyError("invalid explicitly declared genesis ceremony minima")
    if len(paths) < min_operators or len(set(paths)) != len(paths):
        raise CeremonyError("too few distinct supplied contribution files")
    operators, pubkeys, withdrawal_owners = set(), set(), {}
    rows = []
    for path in paths:
        op, vals = read_contribution(path)
        if op in operators:
            raise CeremonyError("duplicate operator label; physical independence still unproven")
        operators.add(op)
        for pub, wd, amount in vals:
            if pub in pubkeys:
                raise CeremonyError("duplicate validator BLS public key")
            pubkeys.add(pub)
            owner_address = wd[-40:]
            if owner_address in withdrawal_owners and withdrawal_owners[owner_address] != op:
                raise CeremonyError("genesis operator labels share withdrawal address; do not claim independent custody")
            withdrawal_owners[owner_address] = op
            rows.append((op, pub, wd, amount))
    if len(operators) < min_operators or len(rows) < min_validators:
        raise CeremonyError("insufficient contributed validators/operators for declared initial genesis experiment")
    # Upstream eth-beacon-genesis additional validator text syntax:
    # 0x<48-byte pubkey>:<32-byte withdrawal credentials without 0x>:<gwei>
    # No mnemonic is ever collected by this process.
    output = "".join(f"{pub}:{wd[2:]}:{amt}\n" for _, pub, wd, amt in sorted(rows))
    summary = {
        "schema": "SSE_R20_GENESIS_CONTRIBUTIONS_REVIEW_V1",
        "declaredOperators": len(operators),
        "publicValidatorKeys": len(rows),
        "totalGenesisBalanceGwei": len(rows) * BALANCE_GWEI,
        "publicValidatorListSha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "genesisChainIdTarget": 31340,
        "containsPrivateKeys": False,
        "blsProofOfPossessionVerified": False,
        "operatorPhysicalIndependenceVerified": False,
        "executionGenesisVerified": False,
        "consensusGenesisSszBuilt": False,
        "beaconDepositsOrActivationExecuted": False,
        "readyToLaunch": False,
    }
    return output, summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Collect public genesis validator keys WITHOUT seeds or claim of BLS proof")
    p.add_argument("--contribution", action="append", type=Path, required=True,
                   help="a distinct independent operator's PUBLIC-only JSON contribution; repeat")
    p.add_argument("--min-operators", type=int, required=True,
                   help="documented independent fault-domain target for THIS genesis; not a membership cap")
    p.add_argument("--min-validators", type=int, required=True,
                   help="documented active-key target for THIS genesis; future deposits are open")
    p.add_argument("--output", type=Path, help="write new provisional public validators.txt, never overwrite")
    args = p.parse_args(argv)
    try:
        listing, result = collect(args.contribution,
                                  min_operators=args.min_operators,
                                  min_validators=args.min_validators)
        if args.output is not None:
            # The public metadata is safe to publish. The owner signs nothing.
            with args.output.open("x", encoding="utf-8", newline="\n") as f:
                f.write(listing)
            result["publicValidatorListWritten"] = str(args.output)
        else:
            result["publicValidatorListWritten"] = None
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (CeremonyError, OSError) as exc:
        print("SSE_R20_GENESIS_CEREMONY_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
