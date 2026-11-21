#!/usr/bin/env python3
"""R33 G1: public-only guard for a standard, initialized Beacon deposit predeploy.

Reference agreement is NOT proof of real EVM execution, consensus deposits,
validator activation, signing-key custody or EL/CL fork compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference" / "standard_deposit_predeploy_r33.json"
UPSTREAM_COMMIT = "0b518636eec53e41e6d261f46ae07147d546a456"
ADDR = re.compile(r"(?:0x)?[a-fA-F0-9]{40}")
HEX32 = re.compile(r"0x[a-fA-F0-9]{64}")
BYTECODE = re.compile(r"0x(?:[a-fA-F0-9]{2})+")


class DepositPredeployError(ValueError):
    pass


def unique_pairs(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise DepositPredeployError("duplicate JSON property")
        obj[k] = v
    return obj


def read_public_json(path: Path, max_size: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= max_size:
        raise DepositPredeployError("bounded regular public JSON file required")
    try:
        obj = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError) as exc:
        raise DepositPredeployError("invalid unique-key public JSON") from exc
    if type(obj) is not dict:
        raise DepositPredeployError("public JSON object required")
    return obj


def zero_hash_storage() -> dict[str, str]:
    # Solidity layout: branch slots 0..31; deposit_count slot 32;
    # zero_hashes[0] slot 33 (zero); zero_hashes[1..31] slots 34..64.
    previous = bytes(32)
    result = {}
    for index in range(1, 32):
        previous = hashlib.sha256(previous + previous).digest()
        result[f"0x{33 + index:064x}"] = "0x" + previous.hex()
    return result


def standard_reference() -> dict:
    ref = read_public_json(REF, 100_000)
    src = ref.get("source")
    expected_source = {
        "repository": "ethpandaops/ethereum-genesis-generator",
        "commit": UPSTREAM_COMMIT,
        "path": "apps/el-gen/system-contracts.yaml",
        "variant": "standard-ungated-deposit",
    }
    acc = ref.get("account")
    if (set(ref) != {"schema", "source", "account"}
            or ref["schema"] != "SSE_R33_STANDARD_ETHEREUM_DEPOSIT_PREDEPLOY_V1"
            or src != expected_source or type(acc) is not dict
            or set(acc) != {"code", "balance", "storage"}
            or acc["balance"] != "0"
            or type(acc["code"]) is not str
            or not BYTECODE.fullmatch(acc["code"])
            or not 5000 <= len(acc["code"]) <= 2 + 2 * 24576
            or acc["storage"] != zero_hash_storage()):
        raise DepositPredeployError("pinned ungated deposit runtime/storage reference invalid")
    return acc


def validate_predeploy(genesis_path: Path, deposit_address: str) -> dict:
    if type(deposit_address) is not str or not ADDR.fullmatch(deposit_address) or int(deposit_address, 16) == 0:
        raise DepositPredeployError("valid nonzero deposit address required")
    expected = standard_reference()
    genesis = read_public_json(genesis_path, 2_000_000)
    alloc = genesis.get("alloc")
    if type(alloc) is not dict:
        raise DepositPredeployError("public EL genesis alloc required")
    matches = []
    for k, v in alloc.items():
        if type(k) is not str or not ADDR.fullmatch(k):
            raise DepositPredeployError("malformed EL genesis allocation address")
        if k.lower().removeprefix("0x") == deposit_address.lower().removeprefix("0x"):
            matches.append(v)
    if len(matches) != 1 or type(matches[0]) is not dict:
        raise DepositPredeployError("exactly one non-aliased deposit account required")
    actual = matches[0]
    code = actual.get("code")
    if type(code) is not str or code.lower() != expected["code"].lower():
        raise DepositPredeployError("deposit bytecode differs from pinned STANDARD ungated runtime (REVERT/gated code refused)")
    storage = actual.get("storage")
    if type(storage) is not dict or len(storage) != 31:
        raise DepositPredeployError("deposit constructor zero-hash storage missing/extra")
    normalized = {}
    for k, v in storage.items():
        if type(k) is not str or not HEX32.fullmatch(k) or type(v) is not str or not HEX32.fullmatch(v):
            raise DepositPredeployError("deposit storage slots/values must be full 32-byte hex")
        if k.lower() in normalized:
            raise DepositPredeployError("duplicate normalized deposit constructor storage slot")
        normalized[k.lower()] = v.lower()
    if normalized != expected["storage"]:
        raise DepositPredeployError("deposit zero-hash constructor state does NOT match pinned reference")
    balance = actual.get("balance", "0")
    if type(balance) is not str or balance not in ("0", "0x0", "0x00"):
        raise DepositPredeployError("nonzero initial deposit contract balance prohibited")
    return {
        "depositPredeployMatchesPinnedUngatedReference": True,
        "depositConstructorZeroHashesVerified": True,
        "upstreamDepositReferenceCommit": UPSTREAM_COMMIT,
        "depositRuntimeSha256": hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),
        "actualDepositContractExecutionVerified": False,
        "elClForkParityVerified": False,
        "newValidatorDepositActivationVerified": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Inspect public standard Ethereum deposit genesis runtime and constructor storage")
    p.add_argument("--eth1-genesis", type=Path, required=True)
    p.add_argument("--deposit-address", required=True)
    a = p.parse_args(argv)
    try:
        print(json.dumps(validate_predeploy(a.eth1_genesis, a.deposit_address), sort_keys=True, indent=2))
        return 0
    except (DepositPredeployError, OSError) as exc:
        print("R33_DEPOSIT_PREDEPLOY_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
