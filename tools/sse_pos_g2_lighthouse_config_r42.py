#!/usr/bin/env python3
"""R42: fix observed Lighthouse v8.3.3 config parse rejection in EXISTING G2.

Official pinned mainnet baseline is from sigp/lighthouse tag v8.3.3 at
common/eth2_network_config/built_in_network_configs/mainnet/config.yaml
Git blob d19a5eefb9d428343cb44c45c59803239e0cc787, stored verbatim in GitHub.
R34 config.yaml ONLY lists overridden chain31340 fields and omits many non-default
fields required by Lighthouse serde Config (SECONDS_PER_ETH1_BLOCK, etc).
Generate complete YAML using original public R34 explicit values + upstream
mainnet-only defaults. Clear upstream mainnet BLOB_SCHEDULE; network Fulu is
deferred by R34. Preserve original YAML as a separate PUBLIC hardlink. Replace
only existing G2 testnet/config.yaml atomically. DO NOT modify R34 or regenerate
SSZ, wallet, JWT, keystore, validator DB, Docker clients or network.
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

import sse_pos_g2_recover_r40 as r40

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "reference/lighthouse_v8_3_3_mainnet_config.yaml"
BASELINE_GIT_BLOB = "d19a5eefb9d428343cb44c45c59803239e0cc787"
PUBLIC_ROOT = Path.home() / ".local/share/sse-r34-chain31340-public"
PUBLIC_HASH = "839072fe3d4b2092b4867010ad01254145872969d89f66ecc86610700f381b13"
TARGET = r40.RUN / "testnet/config.yaml"
BACKUP = r40.RUN / "testnet/config.r34-source.yaml"
TEMP = r40.RUN / "testnet/config.lighthouse-v8.3.3-full.next.yaml"
KEY = re.compile(r"^([A-Z][A-Z0-9_]*):[ \t]*(.*)$")
SCALAR = re.compile(r"^[^\s#][^#\r\n]*$")

# Strict: exactly the original R34 public fields, not guessing arbitrary
# params or silently changing genesis-significant chain settings.
ORIGINAL_KEYS = frozenset((
    "PRESET_BASE", "CONFIG_NAME", "MIN_GENESIS_TIME", "GENESIS_DELAY",
    "MIN_GENESIS_ACTIVE_VALIDATOR_COUNT", "SECONDS_PER_SLOT",
    "GENESIS_FORK_VERSION",
    "ALTAIR_FORK_VERSION", "ALTAIR_FORK_EPOCH",
    "BELLATRIX_FORK_VERSION", "BELLATRIX_FORK_EPOCH",
    "CAPELLA_FORK_VERSION", "CAPELLA_FORK_EPOCH",
    "DENEB_FORK_VERSION", "DENEB_FORK_EPOCH",
    "ELECTRA_FORK_VERSION", "ELECTRA_FORK_EPOCH",
    "FULU_FORK_VERSION", "FULU_FORK_EPOCH",
    "GLOAS_FORK_VERSION", "GLOAS_FORK_EPOCH",
    "HEZE_FORK_VERSION", "HEZE_FORK_EPOCH",
    "TERMINAL_TOTAL_DIFFICULTY", "TERMINAL_BLOCK_HASH",
    "TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH",
    "DEPOSIT_CHAIN_ID", "DEPOSIT_NETWORK_ID",
    "DEPOSIT_CONTRACT_ADDRESS", "DEPOSIT_CONTRACT_DEPLOY_BLOCK",
))
EXTRA_R34_KEYS = frozenset(("DEPOSIT_CONTRACT_DEPLOY_BLOCK",))

class ConfigRefused(ValueError):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            h.update(chunk)
    return h.hexdigest()

def upstream_git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def get_keys(text: str, *, allow_inline_comments: bool) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = KEY.fullmatch(line)
        if m is None:
            continue
        key, value = m.groups()
        if key in out:
            raise ConfigRefused("duplicate top-level public CL YAML key")
        if not allow_inline_comments and not SCALAR.fullmatch(value):
            raise ConfigRefused("unsafe multiline or ambiguous R34 public YAML scalar")
        out[key] = value
    return out

def synthesize(baseline: str, original: str) -> tuple[str, dict]:
    source = get_keys(original, allow_inline_comments=False)
    if set(source) != ORIGINAL_KEYS:
        raise ConfigRefused("R34 public CL override keys differ from observed builder")
    if not (source.get("PRESET_BASE") == '"mainnet"'
            and source.get("CONFIG_NAME") == '"sse31340"'
            and source.get("DEPOSIT_CHAIN_ID") == "31340"
            and source.get("DEPOSIT_NETWORK_ID") == "31340"
            and source.get("MIN_GENESIS_ACTIVE_VALIDATOR_COUNT") == "1"
            and source.get("MIN_GENESIS_TIME") == "1795219212"
            and source.get("ELECTRA_FORK_EPOCH") == "0"
            and source.get("FULU_FORK_EPOCH") == str(2**64 - 1)):
        raise ConfigRefused("R34 chain31340 genesis/fork input mismatch")
    official = get_keys(baseline, allow_inline_comments=True)
    if "BLOB_SCHEDULE" not in official or "SECONDS_PER_ETH1_BLOCK" not in official:
        raise ConfigRefused("official pinned Lighthouse baseline missing mandatory config")
    if set(source) - set(official) != EXTRA_R34_KEYS:
        raise ConfigRefused("original CL keys not covered by official pinned Lighthouse")
    lines = baseline.splitlines(keepends=True)
    out = []
    in_blob_schedule = False
    replaced = set()
    for line in lines:
        m = KEY.match(line)
        if m:
            key = m.group(1)
            if in_blob_schedule:
                in_blob_schedule = False
            if key == "BLOB_SCHEDULE":
                # Mainnet's Fulu-era blob schedule does not apply to the R34
                # Electra-at-genesis, Fulu-disabled chain31340.
                out.append("BLOB_SCHEDULE: []\n")
                in_blob_schedule = True
                continue
            if key in source:
                out.append(key + ": " + source[key] + "\n")
                replaced.add(key)
                continue
        if in_blob_schedule:
            continue
        out.append(line)
    if replaced != set(source) - EXTRA_R34_KEYS:
        raise ConfigRefused("did not replace every original R34 CL override")
    out.append("\n# R34 public deposit deployment marker; deploy-block file remains 0.\n")
    out.append("DEPOSIT_CONTRACT_DEPLOY_BLOCK: " + source["DEPOSIT_CONTRACT_DEPLOY_BLOCK"] + "\n")
    rendered = "".join(out)
    rebuilt = get_keys(rendered, allow_inline_comments=True)
    if (not ORIGINAL_KEYS.issubset(rebuilt)
            or any(rebuilt[k] != v for k, v in source.items())
            or rebuilt["BLOB_SCHEDULE"] != "[]"
            or not all(k in rebuilt for k in (
                "SECONDS_PER_ETH1_BLOCK", "MIN_VALIDATOR_WITHDRAWABILITY_DELAY",
                "SHARD_COMMITTEE_PERIOD", "ETH1_FOLLOW_DISTANCE",
                "MIN_PER_EPOCH_CHURN_LIMIT", "EJECTION_BALANCE"
            ))):
        raise ConfigRefused("complete pinned CL config lacks required Lighthouse fields")
    return rendered, {
        "exactOriginalR34OverridesPreserved": len(source),
        "officialBaselineTopLevelKeys": len(official),
        "newFullConfigTopLevelKeys": len(rebuilt),
        "unsetFuluMainnetOnlyBlobSchedule": True,
        "originalElectraAtGenesisRetained": True,
    }

def inspect_container_state(name: str) -> dict:
    try:
        r = subprocess.run(
            ["sudo", "-n", "docker", "inspect", "--format", "{{json .State}}", name],
            capture_output=True, check=False, timeout=10, text=True,
        )
        if r.returncode:
            raise ConfigRefused("original G2 Docker container missing")
        value = json.loads(r.stdout)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        raise ConfigRefused("unable to verify original existing Docker state") from exc
    if type(value) is not dict:
        raise ConfigRefused("invalid existing Docker state")
    return value

def review(commit: str) -> tuple[bytes, dict]:
    r40.exact_git(commit)
    r40.safe_dir(r40.RUN)
    for name in ("testnet", "el", "beacon", "vc"):
        r40.safe_dir(r40.RUN / name)
    for path, digest in r40.EXPECTED.items():
        r40.safe_public(r40.RUN / path, digest)
    r40.safe_public(PUBLIC_ROOT / "config.yaml", PUBLIC_HASH)
    if TARGET.is_symlink() or sha256(TARGET) != PUBLIC_HASH:
        raise ConfigRefused("R35 copied config.yaml differs from original R34")
    if (BACKUP.exists() or BACKUP.is_symlink()
            or TEMP.exists() or TEMP.is_symlink()):
        raise ConfigRefused("prior config repair attempt exists; do not overwrite")
    for name, should_run in (
        (r40.ORIGINAL_EL, False), (r40.REPLACEMENT_EL, True),
        (r40.BEACON, False), (r40.VC, False),
    ):
        state = inspect_container_state(name)
        if state.get("Running") is not should_run:
            raise ConfigRefused("existing original/replacement client process status changed")
    data = BASELINE.read_bytes()
    if upstream_git_blob(data) != BASELINE_GIT_BLOB:
        raise ConfigRefused("exact upstream Lighthouse official git blob changed")
    raw = TARGET.read_text("utf-8")
    rendered, report = synthesize(data.decode("utf-8"), raw)
    # Check original R34 untouched, real CL genesis SSZ still byte-identical.
    if sha256(r40.RUN / "testnet/genesis.ssz") != r40.EXPECTED["testnet/genesis.ssz"]:
        raise ConfigRefused("real SSZ changed")
    report.update({
        "schema": "SSE_R42_EXACT_PINNED_LIGHTHOUSE_FULL_CONFIG_REPAIR_V1",
        "sourceExactGitSha": commit,
        "upstreamLighthouseTag": "v8.3.3",
        "upstreamOfficialGitBlob": BASELINE_GIT_BLOB,
        "originalPublicConfigSha256": PUBLIC_HASH,
        "renderedFullConfigSha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "originalR34ConfigAndBeaconGenesisSSZUnmodified": True,
        "existingBesuRunningAndOriginalBeaconAndVCStopped": True,
        "secretJWTOrValidatorKeysRead": False,
        "noDockerServiceStartedByThisProgram": True,
    })
    return rendered.encode("utf-8"), report

def apply_repair(content: bytes) -> None:
    # A create-only ORIGINAL public backup; hardlink keeps original inode and
    # sha256 even as config.yaml path is atomically swapped to complete config.
    os.link(TARGET, BACKUP)
    if sha256(BACKUP) != PUBLIC_HASH:
        raise ConfigRefused("original R34 public config hardlink backup changed")
    fd = os.open(TEMP, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    if hashlib.sha256(content).hexdigest() != sha256(TEMP):
        raise ConfigRefused("written FULL public Lighthouse config checksum mismatch")
    os.replace(TEMP, TARGET)
    if sha256(BACKUP) != PUBLIC_HASH or sha256(TARGET) != hashlib.sha256(content).hexdigest():
        raise ConfigRefused("post-swap exact public backup/full config verification failed")

def main() -> int:
    p = argparse.ArgumentParser(description="R42 pinned full Lighthouse config for existing G2")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        payload, result = review(args.expected_commit)
        result["mode"] = "read_only_plan" if args.plan else "public_config_only_apply"
        if args.apply:
            apply_repair(payload)
            result["fullLighthouseConfigInstalledInOriginalG2"] = True
            result["originalR34CLConfigBackupCreatedPublicOnly"] = True
        else:
            result["fullLighthouseConfigInstalledInOriginalG2"] = False
            result["originalR34CLConfigBackupCreatedPublicOnly"] = False
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ConfigRefused, r40.RecoveryRefused, OSError, UnicodeError, ValueError) as exc:
        print("R42_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
