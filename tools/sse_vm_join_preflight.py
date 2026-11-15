#!/usr/bin/env python3
"""R5/R6 read-only SSE VM join preflight. NOT automatic enrollment or a signer.

Checks an exact pinned git revision, application role config, RPC-reported
chain ID, contract existence and EIP-712 settlement domain. Can optionally
read a public wallet's native gas balance. No keys, writes, txs, provisioning
or claims of independent consensus finality.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from sse_chain_read import _domain_separator
from sse_challenge import keccak256

SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HEX = re.compile(r"0x[0-9a-fA-F]+\Z")
ROLES = frozenset(("consumer", "provider", "monitor", "observer"))


class JoinPreflightError(ValueError):
    """A configuration or externally claimed chain state was rejected."""


def require_revision(text: str) -> str:
    if type(text) is not str or not SHA.fullmatch(text):
        raise JoinPreflightError("expected immutable 40-hex-character Git commit")
    return text.lower()


def address(text: str) -> str:
    if type(text) is not str or not ADDR.fullmatch(text) or int(text, 16) == 0:
        raise JoinPreflightError("expected nonzero Ethereum address")
    return text.lower()


def roles(text: str) -> tuple[str, ...]:
    if type(text) is not str:
        raise JoinPreflightError("invalid roles")
    names = tuple(x.strip() for x in text.split(","))
    if not names or len(names) != len(set(names)) or not set(names).issubset(ROLES):
        raise JoinPreflightError("roles must be unique, nonempty: consumer/provider/monitor/observer")
    return names


def validate_rpc_url(url: str) -> str:
    """Require remote TLS or explicit loopback HTTP; never print a tokenized URL."""
    if type(url) is not str:
        raise JoinPreflightError("invalid RPC URL")
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError as exc:
        raise JoinPreflightError("invalid RPC port") from exc
    if (u.scheme not in ("http", "https") or not u.hostname
            or u.username is not None or u.password is not None
            or u.query or u.fragment):
        raise JoinPreflightError("invalid RPC URL syntax or embedded credentials")
    if u.scheme == "http" and u.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise JoinPreflightError("non-loopback RPC requires HTTPS")
    if port is not None and not 1 <= port <= 65535:
        raise JoinPreflightError("invalid RPC port")
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise JoinPreflightError("RPC redirects forbidden")


def rpc_query(url: str, method: str, params: list) -> object:
    validate_rpc_url(url)
    if method not in ("eth_chainId", "eth_getCode", "eth_call", "eth_getBalance"):
        raise JoinPreflightError("RPC method not permitted")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    request = Request(url, data=payload.encode("ascii"),
                      headers={"Content-Type": "application/json", "Accept": "application/json"},
                      method="POST")
    with build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200:
            raise JoinPreflightError("RPC returned non-200 status")
        raw = response.read(131073)
    if len(raw) > 131072:
        raise JoinPreflightError("RPC response too large")
    body = json.loads(raw)
    if (type(body) is not dict or body.get("jsonrpc") != "2.0"
            or body.get("id") != 1 or body.get("error") is not None
            or "result" not in body):
        raise JoinPreflightError("malformed or error RPC response")
    return body["result"]


def hex_integer(value: object) -> int:
    if type(value) is not str or not HEX.fullmatch(value):
        raise JoinPreflightError("invalid RPC quantity")
    return int(value, 16)


def checkout_head(path: Path) -> str:
    """Read a local checkout without switching, cleaning, or updating it."""
    try:
        command = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
            text=True, capture_output=True, timeout=8, check=True
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise JoinPreflightError("cannot verify local Git revision") from exc
    return require_revision(command.stdout.strip())


def inspect_vm(*, checkout: Path, expected_revision: str, role_names: str,
               rpc_url: str, chain_id: int, settlement: str,
               wallet: str | None = None, rpc=rpc_query,
               head=checkout_head) -> dict:
    """Read only. A passing report does NOT activate a provider/monitor role."""
    rev = require_revision(expected_revision)
    assigned = roles(role_names)
    validate_rpc_url(rpc_url)
    if type(chain_id) is not int or not 1 <= chain_id < (1 << 256):
        raise JoinPreflightError("expected chain ID must be positive integer")
    contract = address(settlement)
    wallet_addr = address(wallet) if wallet is not None else None

    actual_revision = require_revision(head(Path(checkout)))
    if actual_revision != rev:
        raise JoinPreflightError("local checkout does not match immutable expected revision")

    reported_chain = hex_integer(rpc(rpc_url, "eth_chainId", []))
    if reported_chain != chain_id:
        raise JoinPreflightError("RPC reports a different chain ID")

    code = rpc(rpc_url, "eth_getCode", [contract, "latest"])
    if (type(code) is not str or not HEX.fullmatch(code)
            or len(code) < 4 or len(code) % 2 != 0 or int(code, 16) == 0):
        raise JoinPreflightError("no deployed settlement code at expected contract")

    selector = "0x" + keccak256(b"domainSeparator()")[:4].hex()
    reported_domain = rpc(rpc_url, "eth_call",
                          [{"to": contract, "data": selector}, "latest"])
    expected_domain = _domain_separator(chain_id, contract)
    if (type(reported_domain) is not str or reported_domain.lower() != expected_domain):
        raise JoinPreflightError("settlement EIP-712 domain mismatch")

    balance = None
    if wallet_addr is not None:
        balance = hex_integer(rpc(rpc_url, "eth_getBalance", [wallet_addr, "latest"]))

    return {
        "kind": "READ_ONLY_SSE_VM_JOIN_PREFLIGHT",
        "result": "PASS",
        "revision": rev,
        "rolesConfigured": list(assigned),
        "chainId": chain_id,
        "settlement": contract,
        "walletAddress": wallet_addr,
        "walletNativeBalanceWei": balance,
        "nativeGasFundingObserved": balance is not None and balance > 0,
        "rpcReportedChainIdMatched": True,
        "contractCodePresent": True,
        "eip712DomainMatched": True,
        "networkConsensusFinalityVerified": False,
        "walletOwnershipVerified": False,
        "roleActivated": False,
        "monitorBondRegistered": False,
        "providerResourcesVerified": False,
        "publicTestnetOrMainnetInferred": False,
        "writesOrTransactionsSent": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SSE read-only VM onboarding gate (no transactions)")
    p.add_argument("--checkout", type=Path, default=Path("."))
    p.add_argument("--revision", required=True, help="Exact immutable 40-character commit SHA")
    p.add_argument("--roles", required=True, help="consumer,provider,monitor,observer (comma separated)")
    p.add_argument("--rpc-url", required=True, help="HTTPS RPC (or loopback HTTP); no URL credentials")
    p.add_argument("--chain-id", required=True, type=int)
    p.add_argument("--settlement", required=True)
    p.add_argument("--wallet", help="Optional public wallet address to inspect gas balance")
    args = p.parse_args(argv)
    try:
        result = inspect_vm(
            checkout=args.checkout, expected_revision=args.revision,
            role_names=args.roles, rpc_url=args.rpc_url,
            chain_id=args.chain_id, settlement=args.settlement,
            wallet=args.wallet,
        )
    except (JoinPreflightError, OSError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
        print("VM_JOIN_PREFLIGHT_FAILED: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
