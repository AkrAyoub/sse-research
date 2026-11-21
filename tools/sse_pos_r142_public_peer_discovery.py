#!/usr/bin/env python3
"""R142: fetch replaceable public peer hints; no fixed peer IP or admission broker.

Discovery metadata is UNTRUSTED. TLS transports bytes; an honest operator
must independently verify original genesis. Actual EL/CL protocols must
authenticate discovered peers and reject incompatible chains. This is not
cryptographic proof of origin, automatic client installation, or reachability.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import re
import sys
import urllib.parse
import urllib.request

import sse_pos_r59_native_ipv6_observer as r59

SCHEMA = "SSE_R142_CHAIN31340_PUBLIC_PEER_HINTS_V1"
EL_GENESIS = "0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
BEACON_GENESIS = "0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd"
NETWORK = "ff2328775f000000"
MAX_BYTES = 65536
MAX_PEERS_PER_FEED = 64
MAX_FEEDS = 12
FIELDS = {"schema", "chainId", "executionGenesisHash",
          "beaconGenesisValidatorsRoot", "networkId", "expiresAt", "peers"}
PEER_FIELDS = {"nodeId", "executionEnode", "beaconEnr"}
ID = re.compile(r"[a-z][a-z0-9-]{2,62}\Z")

class Refused(ValueError):
    pass

def check_source(url):
    if type(url) is not str or len(url) > 1024:
        raise Refused("invalid discovery source")
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.fragment or parts.port not in (None, 443)
            or not parts.path or parts.path == "/"):
        raise Refused("peer directory must be an HTTPS document, not an admin RPC")
    # Avoid arbitrary local/intranet source URLs and SSRF via numeric literals.
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise Refused("IP-literal discovery sources forbidden")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])?", parts.hostname):
        raise Refused("invalid discovery hostname")
    if parts.hostname == "localhost" or "." not in parts.hostname:
        raise Refused("public hostname required")
    return url

def fetch(url):
    url = check_source(url)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    # No redirect following: a redirect could bypass HTTPS/hostname checks.
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(),
                                         _NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200 or response.url != url:
                raise Refused("unexpected HTTPS source response")
            content = response.read(MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise Refused("peer directory unavailable") from exc
    if len(content) > MAX_BYTES:
        raise Refused("peer directory too large")
    return content

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def parse(blob, now=None):
    if not isinstance(blob, (bytes, bytearray)) or len(blob) > MAX_BYTES:
        raise Refused("invalid peer directory size")
    try:
        obj = json.loads(blob, object_pairs_hook=_unique_keys)
    except (UnicodeError, ValueError) as exc:
        raise Refused("invalid directory JSON or duplicate keys") from exc
    if type(obj) is not dict or set(obj) != FIELDS:
        raise Refused("unknown or missing peer directory fields")
    if (obj["schema"] != SCHEMA or type(obj["chainId"]) is not int
            or obj["chainId"] != 31340
            or obj["executionGenesisHash"] != EL_GENESIS
            or obj["beaconGenesisValidatorsRoot"] != BEACON_GENESIS
            or obj["networkId"] != NETWORK):
        raise Refused("wrong original chain31340 identity")
    now = int(datetime.now(timezone.utc).timestamp()) if now is None else now
    expires = obj["expiresAt"]
    if type(expires) is not int or not now < expires <= now + 86400:
        raise Refused("directory expired or unreasonable TTL")
    peers = obj["peers"]
    if type(peers) is not list or len(peers) > MAX_PEERS_PER_FEED:
        raise Refused("invalid peer list")
    found = []
    node_ids = set()
    enodes = set()
    for entry in peers:
        if type(entry) is not dict or set(entry) != PEER_FIELDS:
            raise Refused("invalid peer record fields")
        node = entry["nodeId"]
        el, bn = entry["executionEnode"], entry["beaconEnr"]
        if type(node) is not str or not ID.fullmatch(node):
            raise Refused("invalid peer node ID")
        try:
            good = r59.bootnodes(el, bn)
        except (r59.R59Refused, TypeError) as exc:
            raise Refused("invalid native peer record") from exc
        if not good or node in node_ids or el in enodes:
            raise Refused("duplicate or missing native peer record")
        node_ids.add(node)
        enodes.add(el)
        found.append((node, el, bn))
    return found

def _unique_keys(pairs):
    d = {}
    for key, value in pairs:
        if key in d:
            raise ValueError("duplicate key")
        d[key] = value
    return d

def discover(urls, getter=fetch, now=None, *, min_sources=2):
    if (type(urls) is not list or not 1 <= len(urls) <= MAX_FEEDS
            or len(set(urls)) != len(urls)):
        raise Refused("supply distinct public HTTPS peer directories")
    for url in urls:
        check_source(url)
    if type(min_sources) is not int or min_sources < 2:
        raise Refused("at least two independent source URLs are required")
    successful = 0
    candidates = {}
    for url in urls:
        try:
            raw = getter(url)
            entries = parse(raw, now=now)
        except (Refused, OSError, ValueError, TypeError):
            continue
        if entries:
            successful += 1
        for node, el, bn in entries:
            # A peer identity with equivocal hints must be omitted rather than
            # silently using one source's conflicting address.
            old = candidates.get(node)
            if old is None:
                candidates[node] = (el, bn)
            elif old != (el, bn):
                candidates[node] = False
    accepted = sorted((node, *data) for node, data in candidates.items() if data)
    # A network with exactly ONE reachable first-online peer must admit
    # its second node. Two independent source URLs avoid a single *directory*
    # dependency; two distinct PEER IDENTITIES are not an admission rule.
    if successful < min_sources or len(accepted) < 1:
        raise Refused("insufficient unconflicted multi-source bootstrap hints")
    return {
        "schema": "SSE_R142_PUBLIC_DISCOVERY_RESULT_V1",
        "chainId": 31340,
        "executionGenesisHash": EL_GENESIS,
        "beaconGenesisValidatorsRoot": BEACON_GENESIS,
        "validSourceCount": successful,
        "candidateNodeCount": len(accepted),
        "executionBootnodes": [p[1] for p in accepted],
        "beaconBootnodes": [p[2] for p in accepted],
        "oneTimeManualEnodeInputRequired": False,
        "actualNativePeersAuthenticated": False,
        "peerReachabilityVerified": False,
        "publisherIdentityOrIndependenceVerified": False,
        "liveDirectoryMirrorsVerified": False,
        "fullZeroTouchHostInstallationImplemented": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", action="append", required=True,
                   help="public HTTPS peer directory URL (repeat for distinct mirrors)")
    args = p.parse_args(argv)
    try:
        print(json.dumps(discover(args.source), sort_keys=True, indent=2))
        return 0
    except (Refused, OSError, ValueError, TypeError) as exc:
        print("R142_DISCOVERY_REFUSED: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
