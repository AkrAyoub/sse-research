#!/usr/bin/env python3
"""R34: actual chain31340 EL+CL GENESIS INPUT FILES from one REAL public key.

Writes PUBLIC artifacts only. The operator's encrypted R20/R27/R32 secrets
are not needed or accessed. Does NOT sign, start clients, or open ports.
One-host single-validator smoke is NOT decentralization or public readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from sse_pos_genesis_contributions import collect, read_contribution
from sse_pos_deposit_predeploy import standard_reference, validate_predeploy
from sse_pos_genesis_build import check_consensus_config, check_el_genesis

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_REF = ROOT / "reference" / "standard_pos_system_predeploys_r34.json"
UPSTREAM_COMMIT = "0b518636eec53e41e6d261f46ae07147d546a456"
CHAIN_ID = 31340
DEPOSIT = "0x00000000219ab540356cBB839Cbe05303d7705Fa"
MAX_UINT64 = 2**64 - 1
SECONDS_PER_SLOT = 12
GAS_LIMIT = 30_000_000
EOA_RE = re.compile(r"0x[0-9a-fA-F]{40}\\Z")
COMMIT_RE = re.compile(r"[a-f0-9]{40}\\Z")
FORK_NAMES = ("ALTAIR", "BELLATRIX", "CAPELLA", "DENEB", "ELECTRA", "FULU", "GLOAS", "HEZE")
EXPECTED_SYSTEM = {
    "eip4788": "0x000F3df6D732807Ef1319fB7B8bB8522d0Beac02",
    "eip2935": "0x0000F90827F1C53a10cb7A02335B175320002935",
    "eip7002": "0x00000961Ef480Eb55e80D19ad83579A64c007002",
    "eip7251": "0x0000BBdDc7CE488642fb579F8B00f3a590007251",
}


class Chain31340InputError(ValueError):
    pass


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Chain31340InputError("duplicate public JSON property")
        result[key] = value
    return result


def system_predeploys() -> dict:
    if SYSTEM_REF.is_symlink() or not SYSTEM_REF.is_file() or SYSTEM_REF.stat().st_size > 18000:
        raise Chain31340InputError("missing or oversized pinned PUBLIC system-contract reference")
    try:
        ref = json.loads(SYSTEM_REF.read_text("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError) as exc:
        raise Chain31340InputError("malformed pinned system-contract reference") from exc
    if (type(ref) is not dict or set(ref) != {"schema", "provenance", "entries"}
            or ref["schema"] != "SSE_R34_PINNED_POST_MERGE_SYSTEM_PREDEPLOYS_V1"
            or ref["provenance"] != {
                "repository": "ethpandaops/ethereum-genesis-generator",
                "commit": UPSTREAM_COMMIT,
                "path": "apps/el-gen/system-contracts.yaml",
                "forkScope": "Cancun/Prague at genesis; Osaka/Fulu deferred",
            } or type(ref["entries"]) is not dict
            or set(ref["entries"]) != set(EXPECTED_SYSTEM)):
        raise Chain31340InputError("pinned source/version/system-contract set mismatch")
    out = {}
    for name, expected_address in EXPECTED_SYSTEM.items():
        row = ref["entries"][name]
        if (type(row) is not dict or set(row) != {"address", "account"}
                or row["address"].lower() != expected_address.lower()
                or type(row["account"]) is not dict):
            raise Chain31340InputError("system-contract address/account mismatch: " + name)
        account = row["account"]
        if (not {"balance", "nonce", "code"}.issubset(account)
                or account["balance"] != "0" or account["nonce"] != "1"
                or type(account["code"]) is not str
                or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", account["code"])
                or len(account["code"]) > 49154
                or any(key not in {"balance", "nonce", "code", "storage"} for key in account)):
            raise Chain31340InputError("invalid pinned system-contract runtime: " + name)
        if "storage" in account:
            storage = account["storage"]
            if (type(storage) is not dict or len(storage) > 4 or any(
                    type(k) is not str or type(v) is not str
                    or not re.fullmatch(r"0x[0-9a-fA-F]{64}", k)
                    or not re.fullmatch(r"0x[0-9a-fA-F]{64}", v)
                    for k, v in storage.items())):
                raise Chain31340InputError("invalid pinned system-contract storage: " + name)
        out[expected_address] = account
    return out


def consensus_lines(*, genesis_time: int, count: int) -> str:
    if type(genesis_time) is not int or genesis_time < 1_700_000_000 or genesis_time >= MAX_UINT64:
        raise Chain31340InputError("genesis time must be a valid future UTC unix second")
    if type(count) is not int or count < 1 or count > 4096:
        raise Chain31340InputError("single input batch count must be 1..4096, not a network validator cap")
    lines = [
        "# R34 PUBLIC configuration for a genuine single-owner native PoS smoke.",
        "# It is NOT a security claim about independent validators.",
        'PRESET_BASE: "mainnet"',
        'CONFIG_NAME: "sse31340"',
        f"MIN_GENESIS_TIME: {genesis_time}",
        "GENESIS_DELAY: 0",
        f"MIN_GENESIS_ACTIVE_VALIDATOR_COUNT: {count}",
        "SECONDS_PER_SLOT: 12",
        'GENESIS_FORK_VERSION: "0xa3400001"',
    ]
    for i, name in enumerate(FORK_NAMES, start=2):
        lines += [
            f'{name}_FORK_VERSION: "0xa340{i:04x}"',
            f"{name}_FORK_EPOCH: {0 if name in FORK_NAMES[:5] else MAX_UINT64}",
        ]
    lines += [
        "TERMINAL_TOTAL_DIFFICULTY: 0",
        "TERMINAL_BLOCK_HASH: \"0x" + "00" * 32 + "\"",
        "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH: 0",
        f"DEPOSIT_CHAIN_ID: {CHAIN_ID}",
        f"DEPOSIT_NETWORK_ID: {CHAIN_ID}",
        f'DEPOSIT_CONTRACT_ADDRESS: "{DEPOSIT}"',
        "DEPOSIT_CONTRACT_DEPLOY_BLOCK: 0",
        "# Standard mainnet Ethereum timing; no accelerated or synthetic epochs.",
        "",
    ]
    return "\n".join(lines)


def render_public_inputs(*, public_contribution: Path, owner_eoa: str,
                         genesis_time: int, initial_supply_test_eth: int) -> tuple[dict, str, dict]:
    if (type(owner_eoa) is not str or not EOA_RE.fullmatch(owner_eoa)
            or int(owner_eoa, 16) == 0):
        raise Chain31340InputError("verified, nonzero TEST-only owner EOA required")
    if (type(initial_supply_test_eth) is not int or not 1 <= initial_supply_test_eth <= 10_000_000):
        raise Chain31340InputError("explicit finite initial TEST ETH supply must be 1..10m; NOT issuance cap")
    operator, validators = read_contribution(public_contribution)
    if operator != "operator-own-one":
        raise Chain31340InputError("first real single-owner VM4706 contribution label mismatch")
    for _, credentials, _ in validators:
        if credentials[-40:].lower() != owner_eoa[2:].lower():
            raise Chain31340InputError("public withdrawal credentials mismatch existing owner TEST EOA")
    listing, collector = collect([public_contribution], min_operators=1,
                                 min_validators=1, single_operator_lab=True)
    if len(validators) != collector["publicValidatorKeys"]:
        raise Chain31340InputError("collector disagrees with the one real public contribution")
    alloc = {DEPOSIT: standard_reference(), **system_predeploys()}
    addresses = {address.lower() for address in alloc}
    if owner_eoa.lower() in addresses:
        raise Chain31340InputError("owner EOA aliases a system/deposit contract")
    alloc[owner_eoa] = {"balance": str(initial_supply_test_eth * 10**18)}
    config = {
        "chainId": CHAIN_ID,
        "homesteadBlock": 0, "eip150Block": 0, "eip155Block": 0,
        "eip158Block": 0, "byzantiumBlock": 0,
        "constantinopleBlock": 0, "petersburgBlock": 0,
        "istanbulBlock": 0, "berlinBlock": 0, "londonBlock": 0,
        "terminalTotalDifficulty": 0,
        "terminalTotalDifficultyPassed": True,
        "shanghaiTime": 0, "cancunTime": 0, "pragueTime": 0,
        # No Osaka timestamp: Fulu is explicitly deferred FAR_FUTURE in CL.
        "depositContractAddress": DEPOSIT,
        "withdrawalRequestContractAddress": EXPECTED_SYSTEM["eip7002"],
        "consolidationRequestContractAddress": EXPECTED_SYSTEM["eip7251"],
        "blobSchedule": {
            "cancun": {"target": 3, "max": 6, "baseFeeUpdateFraction": 3338477},
            "prague": {"target": 6, "max": 9, "baseFeeUpdateFraction": 5007716},
        },
    }
    zero = "0x" + "00" * 32
    el = {
        "config": config,
        "alloc": alloc,
        "coinbase": "0x" + "00" * 20,
        "difficulty": "0x0",
        "extraData": "0x",
        "gasLimit": hex(GAS_LIMIT),
        "nonce": "0x0",
        "mixHash": zero,
        "parentHash": zero,
        "timestamp": "0x0",
        "baseFeePerGas": "0x3b9aca00",
        "blobGasUsed": "0x0",
        "excessBlobGas": "0x0",
        "parentBeaconBlockRoot": zero,
    }
    cl = consensus_lines(genesis_time=genesis_time, count=len(validators))
    manifest = {
        "schema": "SSE_R34_ONE_REAL_OPERATOR_PUBLIC_GENESIS_INPUTS_V1",
        "chainId": CHAIN_ID, "initialFundingTestEth": initial_supply_test_eth,
        "initialFundingOwnerEoa": owner_eoa,
        "publicValidatorsCount": len(validators),
        "declaredIndependentOperatorFaultDomains": 1,
        "genesisTimeUtcUnixSeconds": genesis_time,
        "executionGenesisTimestamp": 0,
        "slotsPerEpoch": 32, "secondsPerSlot": SECONDS_PER_SLOT,
        "genesisFork": "Electra/Prague at epoch zero; Fulu/Osaka not scheduled",
        "authenticDepositContractExecutionVerified": False,
        "blsPublicSubgroupVerified": False,
        "livePoSFinalityVerified": False,
        "publicOutsidePeerVerified": False,
        "trueIndependentOperatorsVerified": False,
        "nativeTestEthPreallocatedOnly": True,
        "faucetDeployed": False, "chainStarted": False,
        "publicValidatorListSha256": collector["publicValidatorListSha256"],
    }
    return el, cl, manifest


def verify_fork_pair(el: Path, cl: Path) -> dict:
    # Only for the REAL R34 builder path; --inspect retains old parser fixtures.
    try:
        execution = json.loads(el.read_text("utf-8"), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as exc:
        raise Chain31340InputError("malformed execution genesis for fork-pair gate") from exc
    cfg = execution.get("config", {})
    from sse_pos_genesis_build import SIMPLE_CONFIG_LINE, quantity
    values = {}
    for line in cl.read_text("utf-8").splitlines():
        if line.startswith("#") or not line or line[0].isspace():
            continue
        match = SIMPLE_CONFIG_LINE.fullmatch(line)
        if match:
            key, val = match.groups()
            if key in values:
                raise Chain31340InputError("duplicate CL fork-pair config key")
            values[key] = val.strip().strip("\'\"")
    if (not isinstance(cfg, dict)
            or any(quantity(cfg.get(name)) != 0 for name in ("shanghaiTime", "cancunTime", "pragueTime"))
            or cfg.get("osakaTime") is not None
            or any(quantity(values.get(name + "_FORK_EPOCH")) != 0
                   for name in ("ALTAIR", "BELLATRIX", "CAPELLA", "DENEB", "ELECTRA"))
            or any(quantity(values.get(name + "_FORK_EPOCH")) != MAX_UINT64
                   for name in ("FULU", "GLOAS", "HEZE"))
            or quantity(values.get("SECONDS_PER_SLOT")) != SECONDS_PER_SLOT
            or quantity(values.get("MIN_GENESIS_TIME")) < 1_700_000_000
            or quantity(values.get("GENESIS_DELAY")) != 0):
        raise Chain31340InputError("EL/CL fork pair not approved Electra/Prague genesis with Fulu/Osaka deferred")
    return {
        "genesisExecutionForkMatchesBeaconElectraAtEpochZeroByConfiguration": True,
        "osakaAndFuluNotScheduled": True,
        "actualELCLClientCompatibilityVerified": False,
    }


def prepare(*, contribution: Path, owner_eoa: str, genesis_in_seconds: int,
            initial_supply_test_eth: int, output_dir: Path, expected_commit: str) -> dict:
    if not COMMIT_RE.fullmatch(expected_commit):
        raise Chain31340InputError("exact pinned Git SHA required")
    actual = subprocess.check_output(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=ROOT, text=True, timeout=5).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True, timeout=5).strip()
    if actual != expected_commit or dirty:
        raise Chain31340InputError("pinned Git source mismatch or tracked changes")
    if not 600 <= genesis_in_seconds <= 14400:
        raise Chain31340InputError("allow 10m..4h for honest client startup; no instant retroactive genesis")
    if (os.geteuid() == 0 or not output_dir.is_absolute()
            or not output_dir.parent.is_dir() or output_dir.parent.is_symlink()
            or output_dir.parent.stat().st_uid != os.geteuid()
            or output_dir.exists() or output_dir.is_symlink()):
        raise Chain31340InputError("output must be new owner-controlled absolute directory, not symlink")
    # Pin to an upcoming 12-second boundary; genesis EL timestamp remains zero.
    genesis_time = ((int(time.time()) + genesis_in_seconds + 11)//12)*12
    el, cl, manifest = render_public_inputs(
        public_contribution=contribution, owner_eoa=owner_eoa,
        genesis_time=genesis_time, initial_supply_test_eth=initial_supply_test_eth)
    # Pure input checks before ANY writes. This does not run a client or validate deposits.
    eli = check_el_genesis((json.dumps(el) + "\n").encode())
    check_consensus_config(cl.encode(), eli, manifest["publicValidatorsCount"])
    output_dir.mkdir(mode=0o700)
    artifacts = {
        "genesis.json": (json.dumps(el, sort_keys=True, indent=2) + "\n").encode(),
        "config.yaml": cl.encode(),
        "deposit_contract.txt": (DEPOSIT + "\n").encode(),
        "deploy_block.txt": b"0\n",
    }
    for name, content in artifacts.items():
        with (output_dir / name).open("xb") as f:
            f.write(content)
        os.chmod(output_dir / name, 0o644)
        manifest[name + "Sha256"] = sha256(content)
    manifest["depositPredeployPublicReferenceReview"] = validate_predeploy(
        output_dir / "genesis.json", DEPOSIT)
    manifest["genesisConfigurationForkPairReview"] = verify_fork_pair(
        output_dir / "genesis.json", output_dir / "config.yaml")
    with (output_dir / "public-preparation.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
        f.write("\n")
    os.chmod(output_dir / "public-preparation.json", 0o644)
    return manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prepare PUBLIC only EL+CL inputs for actual one-owner chain31340 PoS")
    p.add_argument("--contribution", type=Path, required=True)
    p.add_argument("--owner-test-eoa", required=True)
    p.add_argument("--genesis-in-seconds", type=int, required=True)
    p.add_argument("--initial-supply-test-eth", type=int, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--prepare", action="store_true", required=True)
    a = p.parse_args(argv)
    try:
        result = prepare(
            contribution=a.contribution, owner_eoa=a.owner_test_eoa,
            genesis_in_seconds=a.genesis_in_seconds,
            initial_supply_test_eth=a.initial_supply_test_eth,
            output_dir=a.output_dir, expected_commit=a.expected_commit)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (Chain31340InputError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print("R34_PUBLIC_GENESIS_INPUT_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
