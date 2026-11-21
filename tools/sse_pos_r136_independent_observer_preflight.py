#!/usr/bin/env python3
"""R136 read-only preflight for an independently operated chain31340 observer.

No Docker changes, validator operations, new genesis, fixed VM addresses, or
claims of native Ethereum peering. This is an operator-neutral admission CHECK,
not a deployer. Actual cross-host admission remains an acceptance requirement.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys

SCHEMA = "SSE_R136_INDEPENDENT_OBSERVER_V1"
NETWORK_ID = "ff2328775f000000"
ARCHIVE_SHA = "1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
FIELDS = {"schema", "chainId", "nodeId", "role", "networkId", "archiveSha256"}
NODE_ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")

class Refused(ValueError):
    pass

def validate_manifest(obj):
    if type(obj) is not dict or set(obj) != FIELDS:
        raise Refused("unexpected/missing manifest fields, including keys or IPs")
    if (obj["schema"] != SCHEMA or type(obj["chainId"]) is not int
            or obj["chainId"] != 31340 or obj["role"] != "observer"
            or obj["networkId"] != NETWORK_ID
            or obj["archiveSha256"] != ARCHIVE_SHA):
        raise Refused("original chain31340 nonsigning identity mismatch")
    if type(obj["nodeId"]) is not str or not NODE_ID.fullmatch(obj["nodeId"]):
        raise Refused("invalid independent node ID")
    return obj

def load_manifest(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise Refused("manifest missing, symlinked or oversized")
    return validate_manifest(json.loads(path.read_text("utf-8")))

def verify_archive(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 6_000_000:
        raise Refused("original chain archive missing, symlinked or oversized")
    digest = hashlib.sha256()
    with path.open("rb") as src:
        while chunk := src.read(65536):
            digest.update(chunk)
    if digest.hexdigest() != ARCHIVE_SHA:
        raise Refused("original chain archive hash mismatch; never replace genesis")
    return path.stat().st_size

def run(command):
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused("live local networking cannot be observed") from exc
    if p.returncode:
        raise Refused("live local networking check failed")
    return p.stdout

def observed_overlay(run_command=run):
    try:
        networks = json.loads(run_command(["zerotier-cli", "-j", "listnetworks"]))
    except (ValueError, TypeError) as exc:
        raise Refused("invalid ZeroTier metadata") from exc
    if type(networks) is not list:
        raise Refused("invalid ZeroTier network list")
    matched = [n for n in networks if type(n) is dict and n.get("nwid") == NETWORK_ID]
    if len(matched) != 1 or matched[0].get("status") != "OK" or matched[0].get("type") != "PUBLIC":
        raise Refused("live controllerless PUBLIC overlay membership not established")
    node = matched[0]
    iface = node.get("portDeviceName")
    if type(iface) is not str or not re.fullmatch(r"zt[a-zA-Z0-9]{4,15}", iface):
        raise Refused("invalid ZeroTier interface")
    addresses = node.get("assignedAddresses")
    if type(addresses) is not list:
        raise Refused("overlay addresses missing")
    ips = set()
    for address in addresses:
        if type(address) is not str:
            raise Refused("invalid overlay address")
        try:
            value = ipaddress.ip_interface(address)
        except ValueError:
            continue
        if (value.version == 6 and value.network.prefixlen == 40
                and value.ip in ipaddress.ip_network("fca0::/16")):
            ips.add(str(value.ip))
    if len(ips) != 1:
        raise Refused("expected exactly one assigned 6plane IPv6")
    ip = next(iter(ips))
    try:
        links = json.loads(run_command(["ip", "-j", "-6", "addr", "show", "dev", iface]))
    except ValueError as exc:
        raise Refused("invalid actual interface metadata") from exc
    if (type(links) is not list or len(links) != 1 or links[0].get("ifname") != iface
            or not any(a.get("local") == ip and a.get("prefixlen") == 40
                       for a in links[0].get("addr_info", []) if type(a) is dict)):
        raise Refused("assigned IPv6 not present on host interface")
    return iface, ip

def report(obj, size, iface, ip):
    return {
        "schema": "SSE_R136_OBSERVER_PREFLIGHT_REPORT_V1",
        "nodeId": obj["nodeId"], "chainId": 31340,
        "originalArchiveSha256Verified": True, "archiveBytes": size,
        "observedOverlayInterface": iface, "observedOverlayIpv6": ip,
        "liveControllerlessOverlayMembership": True,
        "fixedHostIpRequiredByManifest": False,
        "validatorCreatedOrStarted": False, "genesisRecreated": False,
        "dockerResourcesChanged": False,
        "nativeElPeerHandshakeVerified": False,
        "nativeClPeerHandshakeVerified": False,
        "canonicalChainSyncVerified": False,
        "independentPublicInternetReachabilityVerified": False,
        "permissionlessOnboardingEndToEndVerified": False,
        "status": "PREFLIGHT_ONLY_NOT_DEPLOYED"
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--archive", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        obj = load_manifest(args.manifest)
        size = verify_archive(args.archive)
        iface, ip = observed_overlay()
        print(json.dumps(report(obj, size, iface, ip), sort_keys=True, indent=2))
        return 0
    except (Refused, ValueError, OSError, TypeError, UnicodeError) as exc:
        print("R136_OBSERVER_PREFLIGHT_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
