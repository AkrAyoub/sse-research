#!/usr/bin/env python3
"""R35: read-only preflight for REAL R34 artifacts, before native G2 startup.

One physically controlled VM, one real-derived BLS validator, one real SSZ.
This preflight DOES NOT create a JWT, Docker network or launch anything.
Source tests do not establish actual cryptographic BLS possession or finality.
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

from sse_pos_deposit_predeploy import validate_predeploy
from sse_pos_chain31340_inputs import DEPOSIT, verify_fork_pair, unique_object
from sse_pos_genesis_contributions import collect, read_contribution

ROOT = Path(__file__).resolve().parents[1]
EOA = "0x13fb73aace8A11Be2899D047635A757a224Ce00B"
EXPECTED_PUBLIC_FILES = {
    "genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "config.yaml": "839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13",
    "beacon-generated/genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
    "deposit_contract.txt": "8f0934aa294c16b6f45e8f40cc6dba969ad3527f458714146bf7d08178795d0f",
    "deploy_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
EXPECTED_VALIDATOR_DIGEST = "efc4d4d51c3acff8e8fa7238fb12428c6866c2d3d3d770f50ba6a98177a19140"
EXPECTED_GENESIS_TIME = 1795219212
EXPECTED_SS_BYTES = 2737436
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
MAX_BYTES = 12_000_000

class G2PreflightError(ValueError):
    pass

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(128 * 1024):
            h.update(data)
    return h.hexdigest()

def strict_file(path: Path, max_bytes: int = MAX_BYTES) -> None:
    if (path.is_symlink() or not path.is_file() or path.stat().st_size < 1
            or path.stat().st_size > max_bytes
            or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) & 0o022):
        raise G2PreflightError("unsafe or unexpected public artifact: " + path.name)

def json_file(path: Path) -> dict:
    strict_file(path, max_bytes=200_000)
    try:
        result = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError) as exc:
        raise G2PreflightError("invalid public manifest: " + path.name) from exc
    if type(result) is not dict:
        raise G2PreflightError("invalid public manifest shape")
    return result

def validate_record(prep: dict, generated: dict) -> None:
    if (prep.get("schema") != "SSE_R34_ONE_REAL_OPERATOR_PUBLIC_GENESIS_INPUTS_V1"
            or prep.get("chainId") != 31340
            or prep.get("genesisTimeUtcUnixSeconds") != EXPECTED_GENESIS_TIME
            or prep.get("initialFundingOwnerEoa", "").lower() != EOA.lower()
            or prep.get("initialFundingTestEth") != 1000000
            or prep.get("declaredIndependentOperatorFaultDomains") != 1
            or prep.get("publicValidatorsCount") != 1
            or prep.get("publicValidatorListSha256") != EXPECTED_VALIDATOR_DIGEST
            or prep.get("chainStarted") is not False
            or prep.get("trueIndependentOperatorsVerified") is not False):
        raise G2PreflightError("R34 public preparation does not match observed Step40")
    if (generated.get("schema") != "SSE_R25_GENESIS_ARTIFACT_PREPARE_V1"
            or generated.get("intendedChainId") != 31340
            or generated.get("mode") != "single-real-operator-LAB-only"
            or generated.get("consensusGenesisSszGeneratedByPinnedRealBinary") is not True
            or generated.get("genesisSszBytes") != EXPECTED_SS_BYTES
            or generated.get("genesisSszSha256") != EXPECTED_PUBLIC_FILES["beacon-generated/genesis.ssz"]
            or generated.get("elGenesisSha256") != EXPECTED_PUBLIC_FILES["genesis.json"]
            or generated.get("clConfigSha256") != EXPECTED_PUBLIC_FILES["config.yaml"]
            or generated.get("publicValidatorListSha256") != EXPECTED_VALIDATOR_DIGEST
            or generated.get("publicValidatorKeys") != 1
            or generated.get("declaredOperators") != 1
            or generated.get("actualELAndCLClientsAcceptedArtifacts") is not False
            or generated.get("networkStarted") is not False):
        raise G2PreflightError("R25 real-generator provenance does not match observed Step40")

def review(base: Path, contribution: Path, owner_validators: Path, *, expected_commit: str) -> dict:
    if not SHA_RE.fullmatch(expected_commit):
        raise G2PreflightError("exact Git SHA required")
    current = subprocess.check_output(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=ROOT, text=True, timeout=6).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT, text=True, timeout=6).strip()
    if current != expected_commit or dirty:
        raise G2PreflightError("source must be exact clean GitHub revision")
    if os.name != "posix" or os.geteuid() == 0:
        raise G2PreflightError("operator must be unprivileged POSIX account")
    if (base.is_symlink() or not base.is_dir()
            or base.stat().st_uid != os.geteuid()
            or stat.S_IMODE(base.stat().st_mode) != 0o700):
        raise G2PreflightError("R34 owner public base must exist with mode 0700")
    for parent in (base / "beacon-generated", contribution.parent, owner_validators):
        if (parent.is_symlink() or not parent.is_dir()
                or parent.stat().st_uid != os.geteuid()
                or stat.S_IMODE(parent.stat().st_mode) != 0o700):
            raise G2PreflightError("genesis/validator owner directory must be mode 0700")
    for name, expected in EXPECTED_PUBLIC_FILES.items():
        target = base / name
        strict_file(target)
        if digest(target) != expected:
            raise G2PreflightError("immutable Step40 artifact SHA256 mismatch: " + name)
    if (base / "beacon-generated/genesis.ssz").stat().st_size != EXPECTED_SS_BYTES:
        raise G2PreflightError("SSZ byte length differs from observed pinned generator")
    prep = json_file(base / "public-preparation.json")
    generated = json_file(base / "beacon-generated/public-provenance.json")
    validate_record(prep, generated)
    if (not validate_predeploy(base / "genesis.json", DEPOSIT)["depositPredeployMatchesPinnedUngatedReference"]
            or not verify_fork_pair(base / "genesis.json", base / "config.yaml")[
                "genesisExecutionForkMatchesBeaconElectraAtEpochZeroByConfiguration"]):
        raise G2PreflightError("R33 deposit authenticity/fork parity review failed")
    # Never read or print validator secret material. The contribution is public.
    operator, validator_rows = read_contribution(contribution)
    _, collected = collect([contribution], min_operators=1, min_validators=1,
                           single_operator_lab=True)
    if (operator != "operator-own-one" or len(validator_rows) != 1
            or collected["publicValidatorListSha256"] != EXPECTED_VALIDATOR_DIGEST
            or validator_rows[0][1][-40:].lower() != EOA[2:].lower()):
        raise G2PreflightError("real existing BLS public contribution mismatched")
    if (contribution.is_symlink() or contribution.stat().st_uid != os.geteuid()
            or stat.S_IMODE(contribution.stat().st_mode) != 0o600):
        raise G2PreflightError("original public contribution is not owner-protected 0600")
    keystores = list(owner_validators.glob("*/voting-keystore.json"))
    if len(keystores) != 1:
        raise G2PreflightError("expected exactly one EXISTING encrypted Lighthouse BLS keystore")
    keystore = keystores[0]
    if (keystore.parent.is_symlink() or keystore.parent.stat().st_uid != os.geteuid()
            or stat.S_IMODE(keystore.parent.stat().st_mode) != 0o700
            or keystore.is_symlink() or not keystore.is_file()
            or keystore.stat().st_uid != os.geteuid()
            or stat.S_IMODE(keystore.stat().st_mode) != 0o600):
        raise G2PreflightError("existing encrypted BLS keystore path is not owner-protected")
    # Metadata-only public key: does not decrypt nor verify actual BLS subgroup or possession.
    # Read just the public field, do not output encrypted keystore data.
    public = json_file(keystore).get("pubkey")
    if (type(public) is not str or public.lower().removeprefix("0x")
            != validator_rows[0][0].lower().removeprefix("0x")):
        raise G2PreflightError("private keystore public metadata differs from genesis contribution")
    secret_parent = owner_validators.parent / "secrets"
    if (secret_parent.is_symlink() or not secret_parent.is_dir()
            or secret_parent.stat().st_uid != os.geteuid()
            or stat.S_IMODE(secret_parent.stat().st_mode) != 0o700):
        raise G2PreflightError("original Lighthouse 0700 validator password directory absent")
    now = int(time.time())
    return {
        "schema": "SSE_R35_CHAIN31340_G2_PREFLIGHT_V1",
        "sourceExactGitSha": expected_commit,
        "verifiedStep40PublicArtifactCount": len(EXPECTED_PUBLIC_FILES),
        "verifiedActualPinnedBeaconGenesisSSZBytes": EXPECTED_SS_BYTES,
        "existingRealDerivedEncryptedBlsVotingKeys": 1,
        "privateMnemonicOrPasswordRead": False,
        "actualBlsSigningVerified": False,
        "executionGenesisAcceptedByBesu": False,
        "beaconGenesisAcceptedByLighthouse": False,
        "chainStarted": False,
        "genesisTimestampUtc": EXPECTED_GENESIS_TIME,
        "currentUtcUnixSeconds": now,
        "genesisAlreadyPassed": now >= EXPECTED_GENESIS_TIME,
        "declaredPhysicalOperatorFaultDomains": 1,
        "publicP2P": False,
    }

def main() -> int:
    p = argparse.ArgumentParser(description="Read-only exact observed R34 native G2 provenance gate")
    p.add_argument("--expected-commit", required=True)
    a = p.parse_args()
    home = Path.home()
    base = home / ".local/share/sse-r34-chain31340-public"
    contrib = home / ".local/share/sse-r27-bls-operator-private/public-validator-contribution.json"
    validators = home / ".local/share/sse-r27-bls-operator-private/validators"
    try:
        out = review(base, contrib, validators, expected_commit=a.expected_commit)
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0
    except (G2PreflightError, ValueError, OSError,
            subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        print("R35_G2_PREFLIGHT_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
