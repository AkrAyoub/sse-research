#!/usr/bin/env python3
"""R25: assemble real fresh-chain31340 Beacon Genesis from ONLY PUBLIC inputs.

The supplied EL/CL configs and real locally generated BLS public contributions
are required. Never generates a mnemonic, wallet, key or synthetic validator.
Only --build-single-operator-lab may run the pinned upstream SSZ generator.
The emitted artifacts are UNVERIFIED until real Besu+Lighthouse accept them.
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

from sse_pos_genesis_contributions import CeremonyError, collect

CHAIN_ID = 31340
PINNED_GENERATOR_SHA256 = "5ee29389cb29e8a1ace8cfc83ff30a1726409152e88cf07681764740ca9244d2"
GENERATOR_BASENAME = "eth-genesis-state-generator"
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
FORK_VERSION = re.compile(r"0x[0-9a-fA-F]{8}\Z")
SIMPLE_CONFIG_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:\s*([^#]*?)(?:\s+#.*)?$")
KEY_REJECT = frozenset({
    "privateKey", "secretKey", "mnemonic", "seed", "password",
    "validatorKeystore", "jwtSecret", "privkey", "secret_key"
})
MAX_INPUT_BYTES = 2_000_000


class GenesisBuildError(ValueError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def safe_source_file(path: Path, *, max_size: int = MAX_INPUT_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise GenesisBuildError("ordinary nonsymlink file required")
    if path.stat().st_size == 0 or path.stat().st_size > max_size:
        raise GenesisBuildError("empty or excessive input size")
    return path.read_bytes()


def unique_object(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise GenesisBuildError("duplicate JSON property")
        d[k] = v
    return d


def reject_secret_properties(value):
    if type(value) is dict:
        if KEY_REJECT.intersection(value):
            raise GenesisBuildError("secret-bearing EL genesis JSON property")
        for v in value.values():
            reject_secret_properties(v)
    elif type(value) is list:
        for v in value:
            reject_secret_properties(v)


def quantity(value) -> int:
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and (value.isdecimal() or re.fullmatch(r"0x[0-9a-fA-F]+", value)):
        return int(value, 0 if value.startswith("0x") else 10)
    raise GenesisBuildError("invalid unsigned consensus quantity")


def check_el_genesis(blob: bytes) -> dict:
    try:
        d = json.loads(blob.decode("utf-8"), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as e:
        raise GenesisBuildError("invalid execution Genesis JSON") from e
    if type(d) is not dict or type(d.get("config")) is not dict:
        raise GenesisBuildError("missing execution config")
    reject_secret_properties(d)
    cfg = d["config"]
    if quantity(cfg.get("chainId")) != CHAIN_ID:
        raise GenesisBuildError("fresh chain31340 ID is mandatory; 31339 is compromised")
    if any(name in cfg for name in ("qbft", "ibft2", "clique")):
        raise GenesisBuildError("permissioned/Pow genesis consensus not allowed")
    if quantity(cfg.get("terminalTotalDifficulty")) != 0:
        raise GenesisBuildError("post-Merge terminal total difficulty must be 0")
    if cfg.get("terminalTotalDifficultyPassed", True) is not True:
        raise GenesisBuildError("PoS genesis must start after transition")
    if quantity(d.get("difficulty")) != 0:
        raise GenesisBuildError("execution genesis difficulty must be zero")
    if quantity(d.get("gasLimit")) < 10_000_000:
        raise GenesisBuildError("execution gas limit too small for real contracts")
    if type(d.get("alloc")) is not dict:
        raise GenesisBuildError("execution Genesis alloc must be explicit")
    alloc_by_address = {}
    for a, account in d["alloc"].items():
        if type(a) is not str or not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{40}", a):
            raise GenesisBuildError("invalid genesis funded account address")
        if type(account) is not dict:
            raise GenesisBuildError("invalid genesis alloc item")
        normalized = a.lower().removeprefix("0x")
        if normalized in alloc_by_address:
            raise GenesisBuildError("duplicate genesis alloc address after canonical normalization")
        alloc_by_address[normalized] = account
        if "balance" in account:
            quantity(account["balance"])
    el_deposit = cfg.get("depositContractAddress")
    if type(el_deposit) is not str or not ADDRESS.fullmatch(el_deposit) or int(el_deposit, 16) == 0:
        raise GenesisBuildError("missing concrete EL deposit contract address")
    # A mere deposit CONTRACT ADDRESS in config is not an onchain contract.
    # Without real code at genesis, permissionless new-validator deposits
    # cannot be accepted until someone actually deploys working runtime.
    # This is a necessary shape check, NOT an authenticity/runtime proof.
    deposit_predeploy = alloc_by_address.get(el_deposit[2:].lower())
    if deposit_predeploy is None:
        raise GenesisBuildError("deposit contract address must have explicit genesis code predeploy")
    code = deposit_predeploy.get("code")
    if (type(code) is not str or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", code)
            or (len(code) - 2) // 2 > 24_576):
        raise GenesisBuildError("deposit contract predeploy must have bounded nonempty EVM runtime bytecode")
    deposit_code_sha256 = sha256_bytes(bytes.fromhex(code[2:]))
    el_fork_fields = ("shanghaiTime", "cancunTime", "pragueTime", "osakaTime")
    el_fork_times = []
    for field in el_fork_fields:
        if field not in cfg:
            raise GenesisBuildError("missing post-Merge EL fork schedule: " + field)
        timestamp = quantity(cfg[field])
        if timestamp > 2**64 - 1:
            raise GenesisBuildError("execution fork timestamp outside uint64 range")
        el_fork_times.append(timestamp)
    if el_fork_times != sorted(el_fork_times):
        raise GenesisBuildError("execution Shanghai/Cancun/Prague/Osaka fork order inconsistent")
    return {
        "chainId": CHAIN_ID,
        "depositContractAddress": el_deposit.lower(),
        "depositContractRuntimeBytecodePresent": True,
        "depositContractBytecodeHashSha256": deposit_code_sha256,
        "depositContractRuntimeAuthenticityVerified": False,
        "gasLimit": quantity(d["gasLimit"]),
        "shanghaiTime": quantity(cfg["shanghaiTime"]),
        "cancunTime": quantity(cfg["cancunTime"]),
        "pragueTime": quantity(cfg["pragueTime"]),
        "osakaTime": quantity(cfg["osakaTime"]),
    }


def check_consensus_config(blob: bytes, el_info: dict, key_count: int) -> dict:
    try:
        raw = blob.decode("utf-8")
    except UnicodeError as exc:
        raise GenesisBuildError("invalid consensus UTF-8") from exc
    seen: dict[str, str] = {}
    # Interpret only exact top-level scalar keys. The actual upstream generator
    # must still parse the complete config; we do not reimplement YAML.
    for line in raw.splitlines():
        if not line or line.lstrip().startswith("#") or line[0].isspace():
            continue
        match = SIMPLE_CONFIG_LINE.fullmatch(line)
        if match:
            k, v = match.groups()
            if k in seen:
                raise GenesisBuildError("duplicate top-level consensus YAML property")
            seen[k] = v.strip().strip("'\"")
    required = ("PRESET_BASE", "GENESIS_FORK_VERSION", "GENESIS_DELAY",
                "MIN_GENESIS_ACTIVE_VALIDATOR_COUNT", "SECONDS_PER_SLOT",
                "DEPOSIT_CHAIN_ID", "DEPOSIT_CONTRACT_ADDRESS")
    if any(k not in seen for k in required):
        raise GenesisBuildError("explicit CL genesis/fork/deposit parameters required")
    if seen["PRESET_BASE"] != "mainnet":
        raise GenesisBuildError("mainnet ETH2 type preset required; does NOT mean mainnet funds")
    if not FORK_VERSION.fullmatch(seen["GENESIS_FORK_VERSION"]):
        raise GenesisBuildError("invalid CL four-byte GENESIS_FORK_VERSION")
    if seen["GENESIS_FORK_VERSION"].lower() == "0x00000000":
        raise GenesisBuildError("do not reuse Mainnet GENESIS_FORK_VERSION")
    # The upstream pinned eth-beacon-genesis generator and Lighthouse expect
    # explicit CL fork versions/epochs. A schedule absent from config.yaml
    # is not a scientifically reproducible chain fork policy.
    names = ("ALTAIR", "BELLATRIX", "CAPELLA", "DENEB", "ELECTRA", "FULU")
    fork_epochs = []
    fork_versions = [seen["GENESIS_FORK_VERSION"].lower()]
    for name in names:
        epoch_key, version_key = name + "_FORK_EPOCH", name + "_FORK_VERSION"
        if epoch_key not in seen or version_key not in seen:
            raise GenesisBuildError("missing explicit consensus fork schedule: " + name)
        epoch = quantity(seen[epoch_key])
        version = seen[version_key].lower()
        if epoch > 2**64 - 1 or not FORK_VERSION.fullmatch(version):
            raise GenesisBuildError("invalid consensus fork epoch/version: " + name)
        fork_epochs.append(epoch)
        fork_versions.append(version)
    if fork_epochs != sorted(fork_epochs):
        raise GenesisBuildError("consensus fork epochs out of protocol order")
    if len(set(fork_versions)) != len(fork_versions):
        raise GenesisBuildError("consensus fork versions must be distinct")
    if quantity(seen["DEPOSIT_CHAIN_ID"]) != CHAIN_ID:
        raise GenesisBuildError("CL deposit chain ID mismatch")
    if seen["DEPOSIT_CONTRACT_ADDRESS"].lower() != el_info["depositContractAddress"]:
        raise GenesisBuildError("CL deposit address mismatches EL")
    target = quantity(seen["MIN_GENESIS_ACTIVE_VALIDATOR_COUNT"])
    if target < 1 or target > key_count:
        raise GenesisBuildError("CL genesis minimum inconsistent with actual contributed keys")
    if quantity(seen["SECONDS_PER_SLOT"]) != 12:
        raise GenesisBuildError("R25 baseline is protocol-mainnet 12-second slots, not arbitrary accelerated timing")
    delay = quantity(seen["GENESIS_DELAY"])
    if delay > 604800:
        raise GenesisBuildError("genesis delay exceeds 7d")
    if "TERMINAL_TOTAL_DIFFICULTY" in seen and quantity(seen["TERMINAL_TOTAL_DIFFICULTY"]) != 0:
        raise GenesisBuildError("EL/CL terminal difficulty mismatch")
    return {
        "genesisForkVersion": seen["GENESIS_FORK_VERSION"].lower(),
        "minGenesisActiveValidators": target,
        "secondsPerSlot": 12,
        "genesisDelay": delay,
        "depositChainId": CHAIN_ID,
        "depositContractAddress": seen["DEPOSIT_CONTRACT_ADDRESS"].lower(),
        "checkedConsensusForks": list(names),
        "consensusForkEpochs": {name: epoch for name, epoch in zip(names, fork_epochs)},
        "executionConsensusForkParityVerified": False,
    }


def input_review(el: Path, cl: Path, contributions: list[Path],
                 *, min_validators: int, min_operators: int,
                 single_operator_lab: bool) -> tuple[dict, str]:
    # MINIMUM operator threshold is not an exact roster size or protocol cap.
    # Accept any number of independently submitted public contributions >=
    # threshold; collect() enforces exact one file for lab-only mode.
    listing, summary = collect(
        contributions, min_operators=min_operators,
        min_validators=min_validators,
        single_operator_lab=single_operator_lab
    )
    eblob, cblob = safe_source_file(el), safe_source_file(cl)
    eli = check_el_genesis(eblob)
    cli = check_consensus_config(cblob, eli, len(listing.splitlines()))
    report = {
        "schema": "SSE_R25_GENESIS_ARTIFACT_PREPARE_V1",
        "intendedChainId": CHAIN_ID,
        "mode": "single-real-operator-LAB-only" if single_operator_lab else "multioperator-unverified",
        "elGenesisSha256": sha256_bytes(eblob),
        "clConfigSha256": sha256_bytes(cblob),
        "publicValidatorListSha256": sha256_bytes(listing.encode()),
        "publicValidatorKeys": len(listing.splitlines()),
        "declaredOperators": summary["declaredOperators"],
        "elFields": eli,
        "clFields": cli,
        "blsPubkeySubgroupAndPossessionVerified": False,
        "independentAdministratorsVerified": False,
        "actualELAndCLClientsAcceptedArtifacts": False,
        "networkStarted": False,
        "permissionlessPublicNetworkReady": False,
    }
    return report, listing


def checked_generator(path: Path) -> Path:
    if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        raise GenesisBuildError("pinned real genesis generator binary missing")
    if sha256_bytes(safe_source_file(path, max_size=200_000_000)) != PINNED_GENERATOR_SHA256:
        raise GenesisBuildError("real genesis generator SHA-256 mismatch")
    if path.name != GENERATOR_BASENAME:
        raise GenesisBuildError("unexpected generator executable name")
    return path


def build_lab(args, report: dict, listing: str) -> dict:
    if not args.single_operator_lab or args.min_operators != 1:
        raise GenesisBuildError("no public genesis build without independent BLS custody/PoP verification")
    generator = checked_generator(args.generator)
    if not args.expected_commit or not re.fullmatch(r"[0-9a-f]{40}", args.expected_commit):
        raise GenesisBuildError("exact reviewed Git SHA required for real genesis invocation")
    root = Path(__file__).resolve().parent.parent
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=6).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                    cwd=root, text=True, timeout=6).strip()
    if sha != args.expected_commit or dirty:
        raise GenesisBuildError("source revision must match reviewed clean Git checkout")
    output = args.output_dir
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise GenesisBuildError("create-only output directory required, no symlink/overwrite")
    output.mkdir(mode=0o700)
    validators = output / "validators.txt"
    validators.write_text(listing, encoding="utf-8")
    os.chmod(validators, 0o644)
    state = output / "genesis.pending.ssz"
    command = [
        str(generator), "beaconchain", "--eth1-config", str(args.eth1_genesis),
        "--config", str(args.consensus_config),
        "--additional-validators", str(validators),
        "--state-output", str(state),
        "--quiet"
    ]
    # Never execute arbitrary shell, and NEVER pass a mnemonic or seed file.
    # Any program output is suppressed; if it fails do not leak full logs.
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
    if result.returncode != 0 or not state.is_file() or state.is_symlink() or state.stat().st_size < 1024:
        raise GenesisBuildError("real generator failed/invalid output; keep local lab artifacts for private diagnosis")
    final = output / "genesis.ssz"
    state.rename(final)
    report["consensusGenesisSszGeneratedByPinnedRealBinary"] = True
    report["genesisSszSha256"] = sha256_bytes(safe_source_file(final, max_size=500_000_000))
    report["genesisSszBytes"] = final.stat().st_size
    report["pinnedGeneratorSha256"] = PINNED_GENERATOR_SHA256
    report["actualELAndCLClientsAcceptedArtifacts"] = False
    report["permissionlessPublicNetworkReady"] = False
    manifest = output / "public-provenance.json"
    manifest.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(manifest, 0o644)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect/build REAL chain31340 beacon genesis from publicly owned validator inputs")
    parser.add_argument("--eth1-genesis", type=Path, required=True)
    parser.add_argument("--consensus-config", type=Path, required=True)
    parser.add_argument("--contribution", type=Path, action="append", required=True)
    parser.add_argument("--min-operators", type=int, required=True)
    parser.add_argument("--min-validators", type=int, required=True)
    parser.add_argument("--single-operator-lab", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--build-single-operator-lab", action="store_true")
    parser.add_argument("--generator", type=Path)
    parser.add_argument("--expected-commit")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        report, listing = input_review(
            args.eth1_genesis, args.consensus_config, args.contribution,
            min_operators=args.min_operators, min_validators=args.min_validators,
            single_operator_lab=args.single_operator_lab
        )
        if args.build_single_operator_lab:
            if not args.generator or not args.output_dir:
                raise GenesisBuildError("--generator and --output-dir required for build")
            report = build_lab(args, report, listing)
        else:
            report["consensusGenesisSszGeneratedByPinnedRealBinary"] = False
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (GenesisBuildError, CeremonyError, OSError, ValueError,
            subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        print("SSE_R25_GENESIS_REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
