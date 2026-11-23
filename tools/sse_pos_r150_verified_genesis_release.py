#!/usr/bin/env python3
"""R150: prove and prepare the ORIGINAL public chain31340 archive for release.

Run only on an existing operator host containing the already-generated
PUBLIC archive. This tool never reads BLS/EOA/validator key directories, never
creates genesis, and never changes the original file. It emits an operator-
publishable public-only asset and immutable manifest on a separate directory.
It does NOT publish anything to GitHub or disclose local private files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

ARCHIVE_SHA = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
PREFIX = "chain31340-public/"
FILES = {
    "genesis.json": "22eb6c58288113b9c3671970967151012665137b345237b5c24060dc988b1ee8",
    "config.yaml": "3e750d7d02e3ed83747f95cc09ff3299185f56f1777dfeb1f126b17881297b6e",
    "genesis.ssz": "8a5307e81c2dd73be5f3405a722d631ad5761d53ef4771a57b81971e4fcd9e82",
    "deposit_contract_block.txt": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
}
PUBLIC_MEMBERS = frozenset(PREFIX+k for k in (*FILES, "manifest.json"))
MAX_ARCHIVE = 6_000_000
MAX_MEMBER = 3_000_000

class Refused(ValueError):
    pass

def sha(data):
    return hashlib.sha256(data).hexdigest()

def verify(blob):
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_ARCHIVE:
        raise Refused("invalid bounded original public chain archive")
    if sha(blob) != ARCHIVE_SHA:
        raise Refused("not the original R59 chain31340 archive")
    import io
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as f:
            collected = {}
            for item in f:
                if (not item.isfile() or item.name not in PUBLIC_MEMBERS
                        or item.name in collected or not 0 <= item.size <= MAX_MEMBER):
                    raise Refused("archive contains unknown/duplicate/linked member")
                stream = f.extractfile(item)
                if stream is None:
                    raise Refused("public archive member unavailable")
                value = stream.read(MAX_MEMBER+1)
                if len(value) != item.size:
                    raise Refused("truncated or oversized public member")
                collected[item.name] = value
    except (OSError, tarfile.TarError) as exc:
        raise Refused("unreadable original public archive") from exc
    if set(collected) != PUBLIC_MEMBERS:
        raise Refused("missing exact original public genesis members")
    for name, expected in FILES.items():
        if sha(collected[PREFIX+name]) != expected:
            raise Refused("original public genesis member checksum mismatch")
    if len(collected[PREFIX+"genesis.ssz"]) != 2_737_436:
        raise Refused("original Beacon genesis size differs")
    try:
        manifest=json.loads(collected[PREFIX+"manifest.json"])
        execution=json.loads(collected[PREFIX+"genesis.json"])
    except (UnicodeError,ValueError) as exc:
        raise Refused("invalid original public JSON") from exc
    if (type(manifest) is not dict or manifest.get("chainId") != 31340
            or manifest.get("filesSha256") != FILES
            or type(execution) is not dict
            or type(execution.get("config")) is not dict
            or execution["config"].get("chainId") != 31340):
        raise Refused("original public genesis identity mismatch")
    return {"sha256":ARCHIVE_SHA,"chainId":31340,
            "memberDigestsVerified":len(FILES),
            "beaconGenesisBytes":2_737_436,
            "includesOnlyPublicGenesisMembers":True,
            "validatorSecretInspectedOrCopied":False,
            "newGenesisGenerated":False}

def safe_input(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise Refused("original public archive missing or linked")
    if not 0 < path.stat().st_size <= MAX_ARCHIVE:
        raise Refused("source archive is oversized or empty")
    return path.read_bytes()

def stage(original, output):
    blob = safe_input(original)
    report = verify(blob)
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise Refused("output already exists; cannot overwrite or retry blindly")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.mkdir(mode=0o700)
    asset=output/"chain31340-public-native-observer-v1.tar.gz"
    proof=output/"verified-public-genesis.json"
    try:
        for path,payload in (
            (asset,blob),
            (proof,(json.dumps({
                "schema":"SSE_R150_VERIFIED_PUBLIC_GENESIS_ASSET_V1",
                **report,
                "assetFilename":asset.name,
                "publiclyPublished":False,
                "publicDownloadUrlVerified":False,
                "existingChainRuntimeChanged":False,
            },sort_keys=True,indent=2)+"\n").encode("utf-8"))):
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
    except BaseException:
        # Never delete or modify original source archive on failure.
        raise
    return {"assetPath":str(asset),"manifestPath":str(proof),**report}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,default=Path.home()/"chain31340-public-native-observer-v1.tar.gz")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(stage(args.archive,args.out),sort_keys=True,indent=2))
        return 0
    except (Refused,OSError,ValueError,TypeError) as exc:
        print("R150_ORIGINAL_GENESIS_RELEASE_REFUSED: "+str(exc),file=sys.stderr)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
