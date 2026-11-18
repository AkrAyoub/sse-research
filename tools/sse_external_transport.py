#!/usr/bin/env python3
"""Non-destructive transport negotiation for arbitrary external SSE nodes.

A transport is a way to reach P2P peers, NOT an on-chain role. No one needs
to join the lab's Tailscale account to request consumer/provider/monitor/
full_node/validator. An existing user's Tailscale account is *never* switched,
logged out, replaced, or retagged by this planner.

Public native Besu devp2p needs reachable TCP/UDP ports or audited ingress;
a relay needs an independently deployed proxy/peer. This planner never claims
network connectivity merely because an option is selected.
"""
from __future__ import annotations
import argparse
import json
import sys

OPTIONS=frozenset(("auto","native-p2p","relay","tailscale","existing-tailnet"))


class TransportError(ValueError):
    pass


def decide(preference, *, tailscale_status):
    if type(preference) is not str or preference not in OPTIONS:
        raise TransportError("invalid requested transport")
    if type(tailscale_status) is not dict:
        raise TransportError("invalid Tailscale status")
    state=tailscale_status.get("BackendState","NotInstalled")
    if type(state) is not str:
        raise TransportError("bad Tailscale backend state")
    existing=state=="Running"
    if preference=="auto":
        selected="native-p2p-or-relay"
        action="CHECK_PUBLIC_REACHABILITY_THEN_RELAY_IF_NEEDED"
    elif preference=="native-p2p":
        selected="native-p2p"
        action="VERIFY_PUBLIC_TCP_UDP_AND_AUTHENTICATED_BOOTNODES"
    elif preference=="relay":
        selected="relay"
        action="VERIFY_TLS_RELAY_AND_PEER_KEY_PINNING"
    elif preference=="existing-tailnet":
        selected="existing-tailnet"
        action=("VERIFY_EXPLICIT_CROSS_TAILNET_SHARE_NO_REAUTH"
                if existing else "UNAVAILABLE_REQUIRES_EXISTING_TAILSCALE_SESSION")
    else:
        selected="tailscale"
        action=("PRESERVE_ACCOUNT_REQUIRE_ISOLATED_SIDECAR_OR_EXPLICIT_SHARE"
                if existing else "OPTIONAL_ONE_TIME_TAILNET_CREDENTIAL_FROM_OWNER")
    return {
        "kind":"SSE_EXTERNAL_TRANSPORT_PLAN_V1",
        "requestedTransport":preference,
        "selectedTransport":selected,
        "nextNetworkCheck":action,
        "existingTailscaleDetected":existing,
        "mustPreserveExistingTailscale":existing,
        "existingTailscaleLoggedOut":False,
        "existingTailscaleRetagged":False,
        "mayOperateWithoutTailscale":preference in ("auto","native-p2p","relay"),
        "publicP2POrRelayRequiresRuntimeVerification":True,
        "blockchainRoleEligibilityAffectedByTransport":False,
        "blockchainNodePermissionlessAdmissionGranted":False,
        "networkReachabilityVerified":False,
        "daemonStarted":False,
        "ethereumTransactionsSent":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only external node transport plan, never switches Tailscale accounts")
    p.add_argument("--preference",choices=sorted(OPTIONS),default="auto")
    p.add_argument("--tailscale-status-stdin",action="store_true")
    a=p.parse_args(argv)
    try:
        if a.tailscale_status_stdin:
            raw=sys.stdin.read(65537)
            if len(raw)>65536:
                raise TransportError("oversized Tailscale status")
            status=json.loads(raw)
        else:
            status={"BackendState":"NotInstalled"}
        report=decide(a.preference,tailscale_status=status)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (TransportError,ValueError,TypeError,UnicodeError) as exc:
        print("SSE_TRANSPORT_REFUSED: "+str(exc),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
