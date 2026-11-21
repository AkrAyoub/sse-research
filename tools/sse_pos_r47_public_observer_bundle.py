#!/usr/bin/env python3
"""R47: independently verifiable PUBLIC chain31340 artifacts for native observers.

The real live PoS chain exists on VM4706. This exports ONLY 4 fixed,
already-verified PUBLIC EL/CL inputs and a nonsecret manifest. No owner
validator BLS EIP-2335 keystore, HD mnemonic, JWT, slashing DB, password,
node identity, wallet, IP address or VM runtime directory is archived.

--plan: zero writes. --build: create one owner-only archive (0600), never
overwrite. --verify: re-open an archive on ANY independently administered
machine after exact same GitHub source checkout, without owner's VM data.
No synthetic genesis, new chain or secret keys created. Never launches P2P.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import time

import sse_pos_g2_recover_r40 as original

ROOT = Path(__file__).resolve().parents[1]
INPUT = original.RUN / "testnet"
OUTPUT_DIR = Path.home() / ".local/share/sse-r47-chain31340-public-artifacts"
OUTPUT_NAME = "chain31340-public-native-observer-v1.tar.gz"
PREFIX = "chain31340-public/"
EXPECTED = {
    "genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "config.yaml": "3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e",
    "genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
    "deposit_contract_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
SIZES = {
    "genesis.json": (100, 2_000_000),
    "config.yaml": (100, 65536),
    "genesis.ssz": (2737436, 2737436),
    "deposit_contract_block.txt": (1, 64),
}
MAX_TARBALL = 6_000_000
MAX_FILE = 3_000_000
DEPOSIT = "0x00000000219ab540356cbb839cbe05303d7705fa"
RUNTIME_SHA = "5aaa8327c5765ec883224895ca02cade2871e12dad0197bdc791efc91c7ef18d"
SCHEMA = "SSE_R47_REAL_CHAIN31340_PUBLIC_OBSERVER_FILES_V1"

class ArtifactRefused(ValueError):
    pass

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def no_dupes(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ArtifactRefused("duplicate public JSON manifest property")
        obj[k] = v
    return obj

def manifest() -> dict:
    return {
        "schema": SCHEMA,
        "chainId": 31340,
        "currency": "UNVALUED_TEST_ETH",
        "consensusClient": "Lighthouse-v8.3.3",
        "executionClient": "Besu-26.11.1",
        "secondsPerSlot": 12,
        "slotsPerEpoch": 32,
        "genesisTimeUtcUnixSeconds": original.GENESIS_TIME,
        "genesisSszIsActualRealGeneratedBeaconState": True,
        "genesisConfigIsOriginalChain31340": True,
        "depositContractAddress": DEPOSIT,
        "standardUngatedDepositRuntimeSha256": RUNTIME_SHA,
        "filesSha256": dict(EXPECTED),
        "bootstrapPeersProvided": False,
        "publicInternetP2pVerified": False,
        "independentValidatorSignaturesVerified": False,
        "ownerKeyMaterialIncluded": False,
        "artifactProvenance": "VM4706 actual verified G2 real Besu+Lighthouse EL/CL genesis and 2026-11-21 finalized epochs",
    }

def public_source() -> dict[str, bytes]:
    original.safe_dir(original.RUN)
    original.safe_dir(INPUT)
    values = {}
    for filename, sha in EXPECTED.items():
        file = INPUT / filename
        original.safe_public(file, sha)
        size = file.stat().st_size
        lo, hi = SIZES[filename]
        if not lo <= size <= hi:
            raise ArtifactRefused("unexpected original PUBLIC file size")
        values[filename] = file.read_bytes()
        if digest(values[filename]) != sha:
            raise ArtifactRefused("original PUBLIC artifact mutated during read")
    try:
        gen = json.loads(values["genesis.json"], object_pairs_hook=no_dupes)
    except (ValueError, UnicodeError) as exc:
        raise ArtifactRefused("public EL genesis invalid JSON") from exc
    if (type(gen) is not dict or
            (not isinstance(gen.get("config"), dict)) or
            gen["config"].get("chainId") != 31340):
        raise ArtifactRefused("public EL genesis must be real chain31340")
    if b"DEPOSIT_CHAIN_ID: 31340" not in values["config.yaml"]:
        raise ArtifactRefused("complete real Beacon config has wrong chain")
    if len(values["genesis.ssz"]) != 2737436:
        raise ArtifactRefused("genuine Beacon genesis SSZ expected")
    return values

def archive_stream(fileobj, contents: dict[str, bytes]) -> None:
    if set(contents) != set(EXPECTED):
        raise ArtifactRefused("only four known PUBLIC inputs may be archived")
    metadata = json.dumps(manifest(), sort_keys=True, indent=2).encode("utf-8") + b"\n"
    with tarfile.open(mode="w:gz", fileobj=fileobj, format=tarfile.PAX_FORMAT) as archive:
        for name, value in [("manifest.json", metadata), *sorted(contents.items())]:
            if name != "manifest.json":
                if digest(value) != EXPECTED[name]:
                    raise ArtifactRefused("PUBLIC file checksum mismatch before archive")
                lo, hi = SIZES[name]
                if not lo <= len(value) <= hi:
                    raise ArtifactRefused("PUBLIC file size mismatch before archive")
            info = tarfile.TarInfo(PREFIX + name)
            info.size = len(value)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(value))

def verify_bundle(path: Path, *, expected: dict | None = None) -> dict:
    expected = EXPECTED if expected is None else expected
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= MAX_TARBALL):
        raise ArtifactRefused("PUBLIC archive is missing, symlinked, empty or oversized")
    seen = {}
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive:
            if (member.name not in {PREFIX + n for n in (*EXPECTED, "manifest.json")}
                    or not member.isfile() or member.issym() or member.islnk()
                    or member.size < 0 or member.size > MAX_FILE
                    or member.name in seen):
                raise ArtifactRefused("unexpected member, symlink, duplicate or oversized archive data")
            stream = archive.extractfile(member)
            if stream is None:
                raise ArtifactRefused("PUBLIC archive member unreadable")
            value = stream.read(MAX_FILE + 1)
            if len(value) != member.size or len(value) > MAX_FILE:
                raise ArtifactRefused("PUBLIC archive member size inconsistent")
            seen[member.name] = value
    if set(seen) != {PREFIX + n for n in (*EXPECTED, "manifest.json")}:
        raise ArtifactRefused("PUBLIC archive lacks required original genesis/config")
    try:
        item = json.loads(seen[PREFIX + "manifest.json"], object_pairs_hook=no_dupes)
    except (ValueError, UnicodeError) as exc:
        raise ArtifactRefused("PUBLIC archive manifest invalid JSON") from exc
    known = manifest()
    if type(item) is not dict or set(item) != set(known):
        raise ArtifactRefused("PUBLIC manifest schema changed")
    if any(item[k] != v for k, v in known.items() if k != "filesSha256"):
        raise ArtifactRefused("PUBLIC chain/PoS or safety claims changed")
    if item["filesSha256"] != expected:
        raise ArtifactRefused("PUBLIC archive hashes do not match expected genesis")
    for name, sha in expected.items():
        data = seen[PREFIX + name]
        if digest(data) != sha:
            raise ArtifactRefused("PUBLIC archive content hash mismatch")
        lo, hi = SIZES[name]
        if not lo <= len(data) <= hi:
            raise ArtifactRefused("PUBLIC archive content size mismatch")
    return {
        "schema": "SSE_R47_PUBLIC_NATIVE_OBSERVER_BUNDLE_VERIFIED_V1",
        "originalChain31340ManifestAuthenticated": True,
        "publicGenesisFilesExact": len(expected),
        "actualBeaconSSZBytes": len(seen[PREFIX + "genesis.ssz"]),
        "archiveSha256": digest(path.read_bytes()),
        "archiveBytes": path.stat().st_size,
        "containsOnlyPublicGenesisAndConsensusFiles": True,
        "containsOwnerMnemonicKeystoreJwtSlashingDbOrPasswords": False,
        "peerBootstrapOrIndependentSignersClaimed": False,
        "archiveExtractedByVerification": False,
    }

def main() -> int:
    p = argparse.ArgumentParser(description="Real chain31340 public-only portable observer genesis bundle")
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--plan", action="store_true")
    choice.add_argument("--build", action="store_true")
    choice.add_argument("--verify", type=Path)
    p.add_argument("--expected-commit", required=True)
    args = p.parse_args()
    try:
        original.exact_git(args.expected_commit)
        if args.verify is not None:
            report = verify_bundle(args.verify)
        else:
            content = public_source()
            report = {
                "schema": "SSE_R47_OWNER_GENUINE_PUBLIC_BUNDLE_SOURCE_V1",
                "sourceExactGitSha": args.expected_commit,
                "publicOnlyFilesVerified": len(content),
                "originalRealBeaconGenesisBytes": len(content["genesis.ssz"]),
                "originalGenesisAndCanonicalLighthouseConfigPreserved": True,
                "originalSignerSecretsOrJwtRead": False,
                "archiveCreated": False,
                "ownerOnlyArchiveDirectory": str(OUTPUT_DIR),
                "archiveFilename": OUTPUT_NAME,
                "noContainersStartedOrStopped": True,
            }
            if args.build:
                if OUTPUT_DIR.exists() or OUTPUT_DIR.is_symlink():
                    raise ArtifactRefused("original PUBLIC archive output already exists; never overwrite")
                OUTPUT_DIR.mkdir(mode=0o700, parents=False)
                path = OUTPUT_DIR / OUTPUT_NAME
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as dest:
                    archive_stream(dest, content)
                    dest.flush()
                    os.fsync(dest.fileno())
                validated = verify_bundle(path)
                report.update(validated)
                report["archiveCreated"] = True
                report["archiveAbsolutePath"] = str(path)
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (ArtifactRefused, original.RecoveryRefused, OSError, ValueError, tarfile.TarError) as exc:
        print("R47_PUBLIC_ARTIFACT_BUNDLE_REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
