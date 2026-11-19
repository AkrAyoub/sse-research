#!/usr/bin/env python3
"""Fail-closed client image pins: real observations, not proof of consensus."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "config" / "pos_client_image_pins.json"
EXPECTED = {"besu": "hyperledger/besu", "lighthouse": "sigp/lighthouse"}
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class ClientPinError(ValueError):
    pass


def _no_duplicates(pairs):
    out = {}
    for key, val in pairs:
        if key in out:
            raise ClientPinError("duplicate image pin manifest property")
        out[key] = val
    return out


def load_pins(path: Path = FILE) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16384:
        raise ClientPinError("missing, symlinked or oversized pin manifest")
    try:
        record = json.loads(path.read_text("utf-8"), object_pairs_hook=_no_duplicates)
    except (ValueError, UnicodeError) as e:
        raise ClientPinError("unparseable pin manifest") from e
    if type(record) is not dict or set(record) != {
        "schema", "intendedChainId", "notes", "evidenceSourceSha",
        "artifactProvenance", "images", "verification"
    }:
        raise ClientPinError("invalid client pin manifest schema")
    if (record["schema"] != "SSE_NATIVE_POS_CLIENT_DIGEST_PINS_V1"
            or type(record["intendedChainId"]) is not int
            or record["intendedChainId"] != 31340
            or type(record["evidenceSourceSha"]) is not str
            or not COMMIT.fullmatch(record["evidenceSourceSha"])):
        raise ClientPinError("invalid chain label or observation provenance")
    if not isinstance(record["notes"], str) or not isinstance(record["artifactProvenance"], str):
        raise ClientPinError("missing provenance notes")
    images = record["images"]
    if type(images) is not dict or set(images) != set(EXPECTED):
        raise ClientPinError("exactly Besu and Lighthouse are required")
    for role, repo in EXPECTED.items():
        img = images[role]
        if type(img) is not dict or set(img) != {
            "tag", "ref", "imageId", "observedVersion"
        }:
            raise ClientPinError(f"invalid {role} image fields")
        if (type(img["tag"]) is not str or not img["tag"].startswith(repo + ":")
                or img["tag"].endswith(":latest") or
                type(img["ref"]) is not str or not img["ref"].startswith(repo + "@")
                or not SHA.fullmatch(img["ref"].split("@", 1)[-1])
                or type(img["imageId"]) is not str or not SHA.fullmatch(img["imageId"])
                or type(img["observedVersion"]) is not str or not img["observedVersion"]):
            raise ClientPinError(f"unversioned, non-digest or malformed {role} image")
    flags = record["verification"]
    if type(flags) is not dict or set(flags) != {
        "versionCommandsExecutedOnVM4706", "genesisBuilt",
        "publicP2PStarted", "validatorKeysGenerated", "realTestEthDeposited"
    } or any(type(v) is not bool for v in flags.values()):
        raise ClientPinError("invalid observed scope flags")
    if (flags["versionCommandsExecutedOnVM4706"] is not True
            or any(flags[name] for name in (
                "genesisBuilt", "publicP2PStarted",
                "validatorKeysGenerated", "realTestEthDeposited"))):
        raise ClientPinError("the client version check must not claim a live chain")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refs", action="store_true")
    parser.add_argument("--image-ids", action="store_true")
    args = parser.parse_args()
    if args.refs == args.image_ids:
        parser.error("choose exactly one of --refs or --image-ids")
    try:
        manifest = load_pins()
    except (ClientPinError, OSError) as exc:
        parser.exit(2, f"R19_CLIENT_PIN_REFUSED: {exc}\n")
    key = "ref" if args.refs else "imageId"
    for name in ("besu", "lighthouse"):
        print(manifest["images"][name][key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
