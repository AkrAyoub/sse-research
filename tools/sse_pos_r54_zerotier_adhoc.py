#!/usr/bin/env python3
"""R54: controllerless ZeroTier native IPv6 transport bootstrap; VM4707 FIRST.

Same REAL chain31340, no genesis/VC/EL/CL changes. A ZeroTier ad-hoc network
is accessible by ANY external participant, no controller/node authorization.
IPV6 TCP+UDP UNICAST ONLY. ZeroTier planetary roots/relays remain a real
infrastructure dependency. No public-IP or static-IPv4 requirement on peers.
Full publicly permissionless ETH native P2P remains UNPROVEN by overlay join.

OFFICIAL ID format ffSSSSEEEE000000, where S/E are destination port range.
The EXISTING live network uses S=9000 (0x2328), E=30559 (0x775f), so
only destination ports in [9000,30559] are permitted by ZeroTier.
This includes the real EL/CL P2P ports 9000, 9001, 30303 and 30404,
EXCLUDES SSH/22 and Engine API/8551. NEVER bind JSON-RPC/signer on overlay.
Network ID is globally public and not a unique isolated chain namespace.

--plan: no host/VM/daemon modifications.
--join: requires real VM4707, installed ZeroTier, TTY consent. Joins only
the fixed controllerless ad-hoc network. Does not use a ZeroTier Central API,
registration token, controller authorization, remote admin, Docker or VPN key.
--status: only prints network identity, transport state and 6plane IPv6.
This tool never launches validator, daemon, original EL, or genesis.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

NETWORK_ID = "ff2328775f000000"
MIN_PORT = 9000
MAX_PORT = 30559
ALLOWED_P2P = (9000, 9001, 30303, 30404)
ORIGINAL_SIGNER_PATH = Path.home() / ".local/share/sse-r35-chain31340-g2-private"
ORIGINAL_BLS_PATH = Path.home() / ".local/share/sse-r27-bls-operator-private"
EXIT_TIMEOUT = 12
SHA = re.compile(r"[0-9a-f]{40}\Z")

class AdhocRefused(ValueError):
    pass

def protocol_guard() -> dict:
    if not (NETWORK_ID.startswith("ff") and len(NETWORK_ID) == 16
            and NETWORK_ID[10:] == "000000"):
        raise AdhocRefused("controllerless network ID encoding changed")
    low, high = int(NETWORK_ID[2:6], 16), int(NETWORK_ID[6:10], 16)
    if low != MIN_PORT or high != MAX_PORT or not all(
        low <= p <= high for p in ALLOWED_P2P
    ) or low <= 22 or low <= 8551:
        raise AdhocRefused("ZeroTier ad-hoc port range no longer isolated")
    return {
        "controllerlessAdHocNetworkId": NETWORK_ID,
        "minInboundDestinationPort": low,
        "maxInboundDestinationPort": high,
        "ssh22ExcludedByNetwork": True,
        "engineJwtApi8551ExcludedByNetwork": True,
        "ethereumP2pTcpUdpPortsInRange": True,
        "ipv6UnicastOnly": True,
        "networkRegistrationOrPerNodeAdminApproval": False,
        "zeroTierPlanetaryInfraStillRequired": True,
    }

def command(args: list[str], timeout: int = EXIT_TIMEOUT) -> tuple[bool, str]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return proc.returncode == 0, proc.stdout.strip() if proc.returncode == 0 else ""

def refuse_owner_host() -> None:
    if (ORIGINAL_SIGNER_PATH.exists() or ORIGINAL_SIGNER_PATH.is_symlink()
            or ORIGINAL_BLS_PATH.exists() or ORIGINAL_BLS_PATH.is_symlink()):
        raise AdhocRefused("R54 first deployment MUST NOT run on owner VM4706")
    # Additional signer-container guard (without reading any BLS/JWT data).
    ok, _ = command(["sudo", "-n", "docker", "container", "inspect", "sse31340-g2-vc"])
    if ok:
        raise AdhocRefused("original signing client detected; refuse first overlay join")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise AdhocRefused("R54 first deployment requires Linux x86_64 VM4707")

def local_status() -> dict:
    installed, info_text = command(["sudo", "-n", "zerotier-cli", "-j", "info"])
    installed = bool(installed)
    online = False
    if installed:
        try:
            info = json.loads(info_text)
            online = (type(info) is dict and info.get("online") is True)
        except (ValueError, TypeError):
            online = False
    networks = []
    if installed:
        got, net_text = command(["sudo", "-n", "zerotier-cli", "-j", "listnetworks"])
        if got:
            try:
                nets = json.loads(net_text)
                if isinstance(nets, list):
                    networks = [n for n in nets if isinstance(n, dict)
                                and n.get("nwid") == NETWORK_ID]
            except (TypeError, ValueError):
                pass
    membership = networks[0] if networks else {}
    assigned = membership.get("assignedAddresses", [])
    if not isinstance(assigned, list):
        assigned = []
    sixplane = None
    for entry in assigned:
        try:
            addr = ipaddress.ip_interface(str(entry)).ip
        except ValueError:
            continue
        if addr.version == 6 and not addr.is_link_local:
            sixplane = str(addr)
            break
    return {
        "zeroTierInstalled": installed,
        "zeroTierDaemonOnline": online,
        "adhocNetworkJoinedAndOk": membership.get("status") == "OK",
        "zeroTier6planeIPv6": sixplane,
        "exactControllerlessNetworkId": NETWORK_ID,
        "realIPv6TcpUdpRemoteRoundTripsTested": False,
        "realBesuLighthouseNativeP2pOrFinalityTested": False,
    }

def plan() -> dict:
    protocol = protocol_guard()
    refuse_owner_host()
    state = local_status()
    return {
        "schema": "SSE_R54_CONTROLLERLESS_PERMISSION_FREE_IPV6_OVERLAY_READINESS_V1",
        **protocol, **state,
        "noOriginalValidatorOrEthereumClientStartedOrChanged": True,
        "noSourceSystemDockerOrNetworkChangedByPlan": True,
        "physicalOperatorIndependenceNotClaimed": True,
        "nativeEthereumPermissionlessInternetJoinVerified": False,
        "nextAction": "install_official_zerotier_one_then_operator_join_on_vm4707" if not state["zeroTierInstalled"] else "review_ad_hoc_join_on_non_signing_vm4707",
    }

def join() -> dict:
    result = plan()
    if not result["zeroTierInstalled"]:
        raise AdhocRefused("install ZeroTier One from its official signed Ubuntu repository first")
    if result["adhocNetworkJoinedAndOk"]:
        result["mode"] = "already_joined_no_change"
        return result
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise AdhocRefused("operator terminal consent mandatory")
    answer = input(
        "On NEW NON-SIGNING VM4707 only, join PUBLIC controllerless IPv6 "
        "ZeroTier network, with NO admin authorization and port range "
        "9000..30559. No blockchain process started. "
        "Type JOIN-SSE31340-ZT-ADHOC: "
    )
    if answer != "JOIN-SSE31340-ZT-ADHOC":
        raise AdhocRefused("operator did not approve ZeroTier ad hoc join")
    ok, _ = command(["sudo", "-n", "zerotier-cli", "join", NETWORK_ID], timeout=15)
    if not ok:
        raise AdhocRefused("actual ZeroTier ad-hoc join was rejected")
    result = plan()
    result["mode"] = "requested_actual_controllerless_join"
    result["zeroTierJoinCommandSubmitted"] = True
    result["actualSynchronizedNodeOverInternetVerified"] = False
    return result

def main() -> int:
    p = argparse.ArgumentParser(description="Read-only plan or explicit non-signing VM4707 ZeroTier ad-hoc join")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--join", action="store_true")
    g.add_argument("--status", action="store_true")
    args = p.parse_args()
    try:
        if args.plan:
            result = plan()
            result["mode"] = "read_only_plan"
        elif args.join:
            result = join()
        else:
            result = plan()
            result["mode"] = "read_only_status"
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (AdhocRefused, OSError, ValueError, KeyboardInterrupt):
        print("R54_ADHOC_OVERLAY_REFUSED", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
