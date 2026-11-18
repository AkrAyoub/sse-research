#!/usr/bin/env python3
"""Transport-independent, signed SSE role REQUEST verification, not role grants.

This layer is deliberately separate from Tailscale or QBFT bootstrap tools.
Any externally hosted machine may request observer/full_node/consumer/provider/
monitor/validator roles and prove ownership of an Ethereum role-request key.
The signed, chain/genesis-bound request is *only a request*. Its receipt does
NOT automatically enroll a Tailscale device, qualify a monitor, accept service
resources, grant a QBFT vote, or fund an account.

Current QBFT has existing-validator voting; permissionless validator selection
requires a separately specified and tested Sybil-resistant consensus system.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

SCHEMA = "SSE_ROLE_REQUEST_V1"
ROLES = ("observer", "full_node", "consumer", "provider", "monitor", "validator")
ROLE_SET = frozenset(ROLES)
TRANSPORTS = frozenset(("auto", "native-p2p", "relay", "tailscale", "existing-tailnet"))
REQ_FIELDS = frozenset((
    "schema", "chainId", "genesisHash", "nodeId", "account",
    "roles", "transportPreference", "nonce", "issuedAt", "expiresAt"
))
ENVELOPE_FIELDS = frozenset(("request", "walletSignature"))
HEX32 = re.compile(r"0x[0-9a-f]{64}\Z")
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
NODE = re.compile(r"[a-z][a-z0-9-]{7,62}\Z")


class RoleRequestError(ValueError):
    pass


def requested_roles(value):
    if type(value) is str:
        roles = value.split(",")
    elif type(value) is list:
        roles = value
    else:
        raise RoleRequestError("roles must be a list or comma-separated names")
    if (not roles or any(type(s) is not str or s not in ROLE_SET for s in roles)
            or len(set(roles)) != len(roles)):
        raise RoleRequestError("unknown, repeated or missing role")
    # A node can request combinations, including validator plus application.
    # Conflicts must be enforced against on-chain lease identities later.
    return tuple(sorted(roles, key=ROLES.index))


def canonical_request(value):
    if type(value) is not dict or set(value) != REQ_FIELDS:
        raise RoleRequestError("invalid role request schema")
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError):
        raise RoleRequestError("noncanonical role request") from None
    if len(raw) > 2048:
        raise RoleRequestError("oversized role request")
    return raw


def inspect_request(request, *, now=None, chain_id=31338, genesis_hash=None):
    canonical_request(request)
    now = int(time.time()) if now is None else now
    if (request["schema"] != SCHEMA
            or type(request["chainId"]) is not int
            or request["chainId"] != chain_id):
        raise RoleRequestError("wrong chain ID or request version")
    if (type(request["genesisHash"]) is not str
            or not HEX32.fullmatch(request["genesisHash"])
            or int(request["genesisHash"], 16) == 0
            or genesis_hash is not None and request["genesisHash"] != genesis_hash):
        raise RoleRequestError("invalid or unexpected chain genesis")
    if (type(request["nodeId"]) is not str
            or not NODE.fullmatch(request["nodeId"])
            or type(request["account"]) is not str
            or not ADDR.fullmatch(request["account"])
            or int(request["account"], 16) == 0):
        raise RoleRequestError("invalid device identity or wallet")
    assigned = requested_roles(request["roles"])
    if list(assigned) != request["roles"]:
        raise RoleRequestError("noncanonical role order")
    if (type(request["transportPreference"]) is not str
            or request["transportPreference"] not in TRANSPORTS):
        raise RoleRequestError("invalid transport preference")
    issued, expires = request["issuedAt"], request["expiresAt"]
    if (type(issued) is not int or type(expires) is not int
            or not issued <= now < expires or issued < 0
            or expires - issued > 3600 or expires - issued < 60):
        raise RoleRequestError("role request expired or outside permitted lifetime")
    if (type(request["nonce"]) is not str
            or not HEX32.fullmatch(request["nonce"])
            or int(request["nonce"], 16) == 0):
        raise RoleRequestError("nonce must be 32 random nonzero bytes")
    return assigned


def signing_message(request):
    """EIP-191 role proof: domain separation includes genesis and all fields."""
    from eth_account.messages import encode_defunct
    raw = canonical_request(request)
    return encode_defunct(text="SSE_ROLE_REQUEST_V1\n" + raw.decode("ascii"))


def verify(envelope, *, now=None, chain_id=31338, genesis_hash=None):
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise RoleRequestError("invalid signature envelope")
    request = envelope["request"]
    roles = inspect_request(request, now=now, chain_id=chain_id,
                            genesis_hash=genesis_hash)
    signature = envelope["walletSignature"]
    if (type(signature) is not str or not re.fullmatch(
            r"0x[0-9a-fA-F]{130}\Z", signature)):
        raise RoleRequestError("invalid EIP-191 wallet signature")
    from eth_account import Account
    try:
        recovered = Account.recover_message(signing_message(request),
                                            signature=signature)
    except (ValueError, TypeError):
        raise RoleRequestError("wallet signature failed verification") from None
    if recovered.lower() != request["account"].lower():
        raise RoleRequestError("wallet proof does not match claimed account")
    requirements = {}
    for role in roles:
        if role == "observer":
            requirements[role] = ["verified chain genesis", "local chain synchronization"]
        elif role == "full_node":
            requirements[role] = [
                "valid genesis and consensus headers", "node key possession",
                "P2P availability", "sufficient storage and sync"
            ]
        elif role == "consumer":
            requirements[role] = [
                "wallet ownership proven", "correct contract/chain",
                "gas and escrow funding at transaction time"
            ]
        elif role == "provider":
            requirements[role] = [
                "wallet ownership proven", "on-chain registration when required",
                "measured service resources and SLA", "required collateral"
            ]
        elif role == "monitor":
            requirements[role] = [
                "on-chain candidate bond and active status", "availability",
                "independent from lease consumer/provider", "lease-specific committee selection"
            ]
        elif role == "validator":
            requirements[role] = [
                "independent consensus node key and P2P proof",
                "synchronized verified genesis", "consensus-specific admission",
                "observed membership in active validator set"
            ]
    return {
        "kind": "SSE_ROLE_REQUEST_CRYPTOGRAPHICALLY_VERIFIED_V1",
        "nodeId": request["nodeId"],
        "account": request["account"].lower(),
        "chainId": request["chainId"],
        "genesisHash": request["genesisHash"],
        "requestedRoles": list(roles),
        "transportPreference": request["transportPreference"],
        "walletSignatureVerified": True,
        "eligibilityRequirements": requirements,
        "eligibilityVerified": False,
        "rolesActivated": [],
        "networkTransportEstablished": False,
        "validatorVoteGranted": False,
        "consumerFundsMoved": False,
        "monitorSelectedForLease": False,
        "ethereumTransactionsSent": False,
    }


def load_bounded(path, max_bytes=8192):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise RoleRequestError("unsafe or oversized request file")
    return json.loads(path.read_text("utf-8"))


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify open SSE multi-role EIP-191 request, without granting role")
    p.add_argument("--envelope", type=Path, required=True)
    p.add_argument("--chain-id", type=int, required=True)
    p.add_argument("--genesis-hash", required=True)
    a = p.parse_args(argv)
    try:
        result = verify(load_bounded(a.envelope), chain_id=a.chain_id,
                        genesis_hash=a.genesis_hash)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (RoleRequestError, OSError, ValueError, TypeError) as exc:
        print("SSE_ROLE_REQUEST_REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
