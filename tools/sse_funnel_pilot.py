#!/usr/bin/env python3
"""Explicitly configured Tailscale Funnel for the SSE private enrollment broker.

No owned DNS name is needed: Tailscale assigns a *.ts.net HTTPS name.
SAFE DEFAULT: dry-run only. --apply requires explicit exposure approval,
an online Tailscale client, and a live loopback broker. No wallet/network
transaction, repo secret, OAuth credential or tailnet auth key is handled here.
"""
from __future__ import annotations

import argparse
import json
import shutil
import http.client
import subprocess
import sys

BROKER_PORT = 18781
HTTPS_PORT = 443


class FunnelError(ValueError):
    pass


def plan(*, broker_port=BROKER_PORT, https_port=HTTPS_PORT):
    if type(broker_port) is not int or broker_port != BROKER_PORT:
        raise FunnelError("only the reviewed loopback enrollment broker port is permitted")
    if type(https_port) is not int or https_port != HTTPS_PORT:
        raise FunnelError("only standard public HTTPS on 443 is permitted")
    return {
        "kind": "SSE_DOMAINLESS_FUNNEL_PLAN_V1",
        "mode": "DRY_RUN",
        "requiresOwnerTailnetAndOneTimeFunnelApproval": True,
        "requiresLocalBrokerReachable": True,
        "publicExposure": True,
        "publicEndpoint": "https://<THIS-MACHINE>.<YOUR-TAILNET>.ts.net/v1/mesh/enroll",
        "command": ["tailscale", "funnel", "--bg", "--https=443", str(BROKER_PORT)],
        "sourceReleaseStillRequiresSignedArtifact": True,
        "blockchainTransactionsSent": False,
    }


def _run(args, *, timeout=15):
    try:
        p = subprocess.run(args, check=True, capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        raise FunnelError("Tailscale command failed; inspect local admin status") from None
    return p.stdout


def enable(plan_doc: dict, *, explicit_approval=False, run=_run,
           probe=None) -> dict:
    expected = plan()
    if plan_doc != expected:
        raise FunnelError("unexpected or altered Funnel plan")
    if not explicit_approval:
        raise FunnelError("public admission endpoint requires explicit operator approval")
    if shutil.which("tailscale") is None and run is _run:
        raise FunnelError("Tailscale client is not installed")
    # Verify a running authenticated tailnet member before modifying Funnel.
    try:
        status = json.loads(run(["tailscale", "status", "--json"]))
    except (TypeError, ValueError):
        raise FunnelError("Tailscale status JSON invalid") from None
    own = status.get("Self") if type(status) is dict else None
    if (type(status) is not dict or status.get("BackendState") != "Running"
            or type(own) is not dict or own.get("Online") is not True):
        raise FunnelError("Funnel host is not online in its tailnet")
    name = own.get("DNSName")
    if (type(name) is not str or not name.endswith(".ts.net.")
            or len(name) > 253):
        raise FunnelError("missing trusted tailnet MagicDNS FQDN")
    if probe is None:
        connection = http.client.HTTPConnection("127.0.0.1", BROKER_PORT, timeout=3)
        try:
            connection.request("GET", "/healthz")
            reply = connection.getresponse()
            raw = reply.read(4097)
            if reply.status != 200 or len(raw) > 4096:
                raise FunnelError("localhost broker health response invalid")
            check = json.loads(raw)
            if (type(check) is not dict or check.get("status") != "ready"
                    or check.get("ethereumTransactionsSent") is not False):
                raise FunnelError("wrong service on SSE broker port")
        except (OSError, ValueError, http.client.HTTPException):
            raise FunnelError("localhost enrollment broker unavailable") from None
        finally:
            connection.close()
    elif not probe("127.0.0.1", BROKER_PORT):
        raise FunnelError("localhost enrollment broker unavailable")
    # Real public exposure MUST be opt-in; the owner may have to approve Funnel
    # once in the Tailscale admin UI. Never use --yes for silent permission.
    run(expected["command"])
    return {
        "kind": "SSE_DOMAINLESS_FUNNEL_ACTIVE",
        "httpsOrigin": "https://" + name.rstrip("."),
        "enrollmentURL": "https://" + name.rstrip(".") + "/v1/mesh/enroll",
        "operatorApproved": True,
        "chainTransactionsSent": False,
        "nodeRolesRegistered": False,
        "note": "Public Funnel is operator-managed; apply external rate limiting and monitoring",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Domainless Tailscale SSE enrollment planning")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--i-accept-public-credential-endpoint", action="store_true")
    args = parser.parse_args(argv)
    try:
        prepared = plan()
        result = enable(prepared, explicit_approval=args.i_accept_public_credential_endpoint) if args.apply else prepared
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except FunnelError as exc:
        print("SSE_FUNNEL_NOT_ENABLED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
