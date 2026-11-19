#!/usr/bin/env python3
"""R13: verify a NEW small-host private Ethereum PoS genesis before launch.

No BIP39 mnemonic, wallet secret or config content is printed. Operator-
generated 0600 files are verified by their original manifest SHA256; the
upstream d3014d6 compatibility conditions are checked BEFORE Kurtosis.

Only this explicitly reviewed 1 x Besu/Lighthouse/VC, 32 genesis-validator,
no public peer publication profile is accepted. This is first-boot smoke,
NOT a permanent validator set, complete decentralization or real Sybil
resistance. An old R12 YAML must use the separate R12 repair; it is never
silently accepted as a valid new R13 configuration.
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

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM="d3014d6d23d683362025b9e23a0d69de49e77cca"
# VM4705 generated its real, owner-private genesis under this reviewed
# R13 release. Later source fixes MUST NOT force a new mnemonic or wallet.
# Only this EXACT known legacy release is accepted across clean checkouts;
# the recorded genesis SHA256 and all runtime invariants are reverified.
FIRST_R13_GENERATOR_SHA="67405e2ee36be27e91bfd77fcbc2e33935830bbf"
FAR=18446744073709551615
HEX=re.compile(r"[0-9a-f]{64}\Z")
SHA=re.compile(r"[0-9a-f]{40}\Z")
ADDRESS=re.compile(r"0x[0-9a-fA-F]{40}\Z")


class LaunchError(ValueError):
    pass


def _only_owner(file:Path,folder:Path):
    if (file.is_symlink() or not file.is_file()
            or file.stat().st_uid!=os.geteuid()
            or stat.S_IMODE(file.stat().st_mode)!=0o600
            or not 1<=file.stat().st_size<=65536):
        raise LaunchError("missing or unsafe 0600 owner-only genesis artifact")
    if (folder.is_symlink() or not folder.is_dir()
            or folder.stat().st_uid!=os.geteuid()
            or stat.S_IMODE(folder.stat().st_mode)!=0o700):
        raise LaunchError("secret parent folder must be 0700 owner-only")


def verify(directory:Path,*,git_sha:str|None=None)->dict:
    if (os.name!="posix" or os.geteuid()==0
            or not directory.is_absolute() or not directory.is_dir()
            or directory.is_symlink()):
        raise LaunchError("nonroot Linux and existing absolute private folder required")
    config=directory/"network_params.yaml"
    manifest=directory/"manifest.json"
    _only_owner(config,directory)
    _only_owner(manifest,directory)
    raw=config.read_bytes()
    try:
        obj=json.loads(manifest.read_text("utf-8"))
    except (ValueError,UnicodeError):
        raise LaunchError("unparseable or invalid network manifest") from None
    if type(obj) is not dict or obj.get("sourceConfigProfile")!="R13_PINNED_ETHEREUM_PACKAGE_SMALL_BOOTSTRAP_V1":
        raise LaunchError("not a freshly generated R13 protected PoS configuration")
    manifest_sha=obj.get("secretConfigSha256")
    source_sha=obj.get("sourceGitSha")
    if (type(manifest_sha) is not str or not HEX.fullmatch(manifest_sha)
            or type(source_sha) is not str or not SHA.fullmatch(source_sha)
            or hashlib.sha256(raw).hexdigest()!=manifest_sha):
        raise LaunchError("genesis bytes modified since the owner generated them")
    if git_sha is None:
        try:
            git_sha=subprocess.check_output(
                ["git","rev-parse","HEAD"],cwd=ROOT,text=True,timeout=5
            ).strip()
            dirty=subprocess.check_output(
                ["git","status","--porcelain","--untracked-files=no"],
                cwd=ROOT,text=True,timeout=5
            ).strip()
        except (OSError,subprocess.SubprocessError):
            raise LaunchError("approved GitHub source checkout unavailable") from None
        if dirty:
            raise LaunchError("modified tracked source refused")
    if git_sha!=source_sha and source_sha!=FIRST_R13_GENERATOR_SHA:
        raise LaunchError("genesis created by an unapproved different source revision")
    checks={
        "schema":"SSE_OWN_ETHEREUM_POS_DEVNET_PLAN_V1",
        "chainId":31339,
        "initialBootstrapValidators":32,
        "bootstrapProfile":"R13_ONE_NODE_SMALL_HOST_V1",
        "underlyingConsensus":"ETHEREUM_PROOF_OF_STAKE",
        "genesisFaucetBalanceTestEth":1_000_000,
        "publicP2PRequested":False,
        "networkConfigCreated":True,
        "upstreamCommit":UPSTREAM,
    }
    if any(obj.get(key)!=value for key,value in checks.items()):
        raise LaunchError("genesis manifest deviates from pinned research profile")
    fork_keys={"fulu_fork_epoch",*[f"bpo_{i}_epoch" for i in range(1,6)]}
    expected_lines=[
        b'  network_id: "31339"',
        b'    count: 1',
        b'    validator_count: 32',
        b'  num_validator_keys_per_node: 32',
        b'  preregistered_validator_count: 0',
        b'  genesis_gaslimit: 30000000',
        b'  network: "kurtosis"',
        b'  - el_type: besu',
        b'    cl_type: lighthouse',
        b'    vc_type: lighthouse',
        b'  prefunded_accounts: ',
        b'  preregistered_validator_keys_mnemonic: "',
        b'additional_services: []',
    ]
    lines=raw.splitlines()
    for pattern in expected_lines:
        matching=[line for line in lines if (
            line==pattern if pattern not in (
                b'  prefunded_accounts: ',
                b'  preregistered_validator_keys_mnemonic: "'
            ) else line.startswith(pattern)
        )]
        if len(matching)!=1:
            # Only static, non-secret expected keys are named in errors.
            # Never expose actual YAML lines or the mnemonic value.
            raise LaunchError("missing or repeated secure PoS parameter: "
                              +pattern.strip().decode("ascii").split(":")[0])
    for fork in fork_keys:
        if lines.count(f"  {fork}: {FAR}".encode())!=1:
            raise LaunchError("Fulu or dependent BPO epoch not disabled on small host")
    if (b'    enabled: true' in lines
            or b"  - dora" in lines
            or b"giant issue aisle success" in raw
            or b"\x00" in raw):
        raise LaunchError("public P2P, explorer, default mnemonic or invalid genesis data")
    if obj.get("expectedFuluForkEpoch")!=FAR or obj.get("expectedBpoForkEpochs")!={f"bpo_{i}_epoch":FAR for i in range(1,6)}:
        raise LaunchError("manifest fork constraints not independently confirmed")
    # Configuration is hash-attested, but the public faucet must still be
    # the one locally created by the operator, not an SSE admin fixed EOA.
    faucet=obj.get("genesisFundedFaucetAddress")
    if type(faucet) is not str or not ADDRESS.fullmatch(faucet) or int(faucet,16)==0:
        raise LaunchError("no valid locally selected faucet address")
    if faucet.encode() not in raw:
        raise LaunchError("funded faucet not present in pinned genesis config")
    return {
        "schema":"SSE_R13_SECURE_GENESIS_LAUNCH_READY_V1",
        "sourceGitSha":source_sha,
        "reviewedCurrentCheckoutSha":git_sha,
        "originalR13GenesisPreservedAcrossCodeFix":git_sha!=source_sha,
        "chainId":31339,
        "upstreamGitSha":UPSTREAM,
        "genesisConfigSha256":manifest_sha,
        "faucetPublicAddress":faucet,
        "genesisFaucetTestEth":1_000_000,
        "bootstrapClientPairs":1,
        "bootstrapValidatorKeys":32,
        "fuluAndAllBpoForksDeferred":True,
        "noDefaultPublicGenesisMnemonic":True,
        "publicP2PExposed":False,
        "proofOfIndependentValidatorAdmission":False,
        "consensusRunning":False,
        "realEthereumSpent":False,
        "privateValidatorMnemonicPrinted":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only, no-secret PoS devnet launch validation")
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--verify-only",action="store_true",required=True)
    a=p.parse_args(argv)
    try:
        report=verify(a.output_dir)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (LaunchError,OSError,ValueError,TypeError) as exc:
        print("SSE_R13_LAUNCH_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
