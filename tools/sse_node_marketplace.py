#!/usr/bin/env python3
"""SSE R5 node-owned marketplace transaction CLI.

This tool is run on the participant's own Ubuntu VM, never from the
independent global dashboard. Default mode constructs a read-only calldata
plan. Explicit --execute requires a protected local signer file, live chain
and contract preflight, transaction gas budget and a successful receipt.

Scope: request, bid, funded bid selection, provider acceptance, bonded
monitor enrollment/confirmation and consumer epoch admission. It does not
claim provider workload delivery, monitor SLA truth or contract finality.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sse_challenge import keccak256

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HASH32 = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEX = re.compile(r"0x[0-9a-fA-F]+\Z")
ACTIONS = {
    "request": ("consumer", "board", "requestResource(bytes32,bytes32,uint256,uint64)"),
    "bid": ("provider", "board", "placeBid(uint256,uint256)"),
    "fund": ("consumer", "board", "chooseBidAndFundLease(uint256,uint256,address,(bytes32,uint256,uint256,uint256,uint64,uint64,uint64))"),
    "accept": ("provider", "settlement", "acceptLease(uint256)"),
    "monitor-register": ("monitor", "pool", "register()"),
    "monitor-confirm": ("monitor", "settlement", "confirmMonitorAssignment(uint256)"),
    "admit-epoch": ("consumer", "settlement", "admitEpoch(uint256,bytes32)"),
}
MAX_GAS = 9_000_000


class NodeTxError(ValueError):
    pass


def uint(v, name: str, bits: int = 256, *, minimum: int = 0) -> int:
    if type(v) is not int or not minimum <= v < 2**bits:
        raise NodeTxError(name + " outside unsigned integer range")
    return v


def address(v, name="address") -> str:
    if type(v) is not str or not ADDRESS.fullmatch(v) or int(v, 16) == 0:
        raise NodeTxError("invalid " + name)
    return v.lower()


def hash32(v, name="digest") -> str:
    if type(v) is not str or not HASH32.fullmatch(v) or int(v, 16) == 0:
        raise NodeTxError("invalid nonzero " + name)
    return v.lower()


def rpc_origin(raw: str) -> str:
    if type(raw) is not str or any(c.isspace() for c in raw):
        raise NodeTxError("invalid RPC URL")
    u = urlsplit(raw)
    try:
        port = u.port
    except ValueError:
        raise NodeTxError("invalid RPC port") from None
    if (u.scheme not in ("https", "http") or not u.hostname or
            u.username is not None or u.password is not None or
            u.path not in ("", "/") or u.query or u.fragment or
            (u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1", "::1")) or
            (port is not None and not 1 <= port <= 65535)):
        raise NodeTxError("RPC requires HTTPS or loopback HTTP, without embedded secrets")
    return raw.rstrip("/")


def _word(value, kind: str) -> bytes:
    if kind == "address":
        value = int(address(value), 16)
    elif kind == "bytes32":
        value = int(hash32(value), 16)
    elif kind == "uint64":
        value = uint(value, "uint64", 64)
    else:
        value = uint(value, "uint256")
    return value.to_bytes(32, "big")


@dataclass(frozen=True)
class Plan:
    action: str
    role: str
    chain_id: int
    target: str
    data: str
    value: int
    board: str
    settlement: str
    pool: str

    def public(self) -> dict:
        return {
            "kind": "SSE_NODE_TRANSACTION_PLAN",
            "action": self.action,
            "role": self.role,
            "chainId": self.chain_id,
            "to": self.target,
            "calldata": self.data,
            "valueWei": self.value,
            "signerRequired": True,
            "requiresRoleLocalApproval": True,
            "ethereumTransactionsSent": False,
            "physicalServiceVerified": False,
        }


def make_plan(action: str, role: str, *, chain_id: int, board: str,
              settlement: str, pool: str, params: dict) -> Plan:
    if action not in ACTIONS or role != ACTIONS[action][0]:
        raise NodeTxError("action requires the owning SSE participant role")
    if type(params) is not dict:
        raise NodeTxError("action arguments must be a JSON object")
    chain_id = uint(chain_id, "chain ID", minimum=1)
    board, settlement, pool = (address(board, "board"), address(settlement, "settlement"),
                               address(pool, "committee pool"))
    op_role, target_kind, sig = ACTIONS[action]
    specs = {
        "request": (("profileHash", "bytes32"), ("policyHash", "bytes32"),
                    ("maxEpochFeeWei", "uint256"), ("biddingClose", "uint64")),
        "bid": (("requestId", "uint256"), ("epochFeeWei", "uint256")),
        "fund": (("requestId", "uint256"), ("bidIndex", "uint256"),
                 ("settlement", "address"), ("endpointHash", "bytes32"),
                 ("reservationFeeWei", "uint256"), ("exposureBudgetWei", "uint256"),
                 ("maxEpochs", "uint256"), ("responsePeriodSeconds", "uint64"),
                 ("monitorGraceSeconds", "uint64"), ("evidenceWindowSeconds", "uint64")),
        "accept": (("leaseId", "uint256"),),
        "monitor-register": tuple(),
        "monitor-confirm": (("leaseId", "uint256"),),
        "admit-epoch": (("leaseId", "uint256"), ("requestHash", "bytes32")),
    }
    expected = {key for key, _ in specs[action]}
    if action == "fund":
        expected |= {"selectedEpochFeeWei"}
    if action == "monitor-register":
        expected |= {"bondWei"}
    if set(params) != expected:
        raise NodeTxError("action arguments do not match expected schema")
    values = dict(params)
    if action == "fund":
        # Settlement is authoritative, not caller-selected. Pricing must be
        # checked against the actual selected on-chain bid before execution.
        values["settlement"] = settlement
        max_epochs = uint(params["maxEpochs"], "maxEpochs", minimum=1)
        selected_fee = uint(params["selectedEpochFeeWei"], "selectedEpochFeeWei", minimum=1)
        if max_epochs > 64 or uint(params["reservationFeeWei"], "reservationFeeWei") > selected_fee:
            raise NodeTxError("invalid funded lease economics")
        if uint(params["exposureBudgetWei"], "exposureBudgetWei") < selected_fee:
            raise NodeTxError("exposure budget below epoch fee")
        if any(params[n] == 0 for n in ("responsePeriodSeconds", "monitorGraceSeconds", "evidenceWindowSeconds")):
            raise NodeTxError("lease timing windows must be positive")
        value = max_epochs * selected_fee
        uint(value, "total escrow")
    elif action == "monitor-register":
        value = uint(params["bondWei"], "bondWei", minimum=1)
    else:
        value = 0
    for field in ("maxEpochFeeWei", "epochFeeWei"):
        if field in params:
            uint(params[field], field, minimum=1)
    for field in ("requestId", "leaseId"):
        if field in params:
            uint(params[field], field, minimum=1)
    if action == "request" and params["biddingClose"] == 0:
        raise NodeTxError("bidding close must be positive")
    selector = keccak256(sig.encode("ascii"))[:4]
    payload = selector + b"".join(_word(values[key], kind) for key, kind in specs[action])
    dest = {"board": board, "settlement": settlement, "pool": pool}[target_kind]
    return Plan(action, role, chain_id, dest, "0x" + payload.hex(), value,
                board, settlement, pool)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NodeTxError("RPC redirect forbidden")


class RPC:
    def __init__(self, url: str):
        self.url = rpc_origin(url)
        self._counter = 0

    def request(self, method: str, params: list):
        self._counter += 1
        req = Request(self.url, data=json.dumps(
            {"jsonrpc": "2.0", "id": self._counter, "method": method, "params": params}
        ).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(req, timeout=8) as resp:
                if resp.status != 200:
                    raise NodeTxError("unexpected RPC status")
                raw = resp.read(1_048_577)
        except OSError:
            raise NodeTxError("RPC unavailable") from None
        if len(raw) > 1_048_576:
            raise NodeTxError("RPC response too large")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise NodeTxError("malformed RPC response") from None
        if (type(result) is not dict or result.get("jsonrpc") != "2.0" or
                result.get("id") != self._counter or result.get("error") is not None or
                "result" not in result):
            raise NodeTxError("RPC request failed or invalid response: " + method)
        return result["result"]


def _hex_int(v):
    if type(v) is not str or not HEX.fullmatch(v):
        raise NodeTxError("malformed RPC hex integer")
    return int(v, 16)


def _read_word(data: str, index: int):
    if type(data) is not str or not data.startswith("0x"):
        raise NodeTxError("invalid ABI contract response")
    try:
        raw = bytes.fromhex(data[2:])
    except ValueError:
        raise NodeTxError("invalid ABI contract response") from None
    pos = index * 32
    if len(raw) < pos + 32:
        raise NodeTxError("short ABI contract response")
    return int.from_bytes(raw[pos:pos + 32], "big")


def _eth_call(rpc, target: str, signature: str, *args: int) -> str:
    data = "0x" + (keccak256(signature.encode("ascii"))[:4] +
                   b"".join(_word(a, "uint256") for a in args)).hex()
    return rpc.request("eth_call", [{"to": target, "data": data}, "latest"])


def preflight(rpc, plan: Plan, *, signer: str | None = None,
              expected_selected_fee: int | None = None):
    if _hex_int(rpc.request("eth_chainId", [])) != plan.chain_id:
        raise NodeTxError("wrong blockchain chain ID")
    for target in {plan.target, plan.settlement, plan.board, plan.pool}:
        code = rpc.request("eth_getCode", [target, "latest"])
        if type(code) is not str or not HEX.fullmatch(code) or int(code, 16) == 0:
            raise NodeTxError("missing expected deployed contract code")
    if plan.action == "fund":
        approved = _read_word(_eth_call(rpc, plan.board, "approvedSettlement()"), 0)
        backref = _read_word(_eth_call(rpc, plan.settlement, "resourceBoard()"), 0)
        if approved != int(plan.settlement, 16) or backref != int(plan.board, 16):
            raise NodeTxError("resource board and settlement binding mismatch")
        if expected_selected_fee is None:
            raise NodeTxError("missing expected selected bid fee")
        # requestId, bidIndex are the first two static argument words.
        request_id = _read_word(plan.data, 0) if False else int(plan.data[10:74], 16)
        bid_index = int(plan.data[74:138], 16)
        bid = _eth_call(rpc, plan.board, "getBid(uint256,uint256)", request_id, bid_index)
        provider = _read_word(bid, 0)
        fee = _read_word(bid, 1)
        if provider == 0 or (signer is not None and provider == int(signer, 16)):
            raise NodeTxError("provider bid identity invalid")
        if fee != expected_selected_fee:
            raise NodeTxError("selected bid fee changed since transaction plan")
        max_epochs = int(plan.data[10 + 64 * 6:10 + 64 * 7], 16)
        if plan.value != fee * max_epochs:
            raise NodeTxError("escrow no longer matches selected bid")


def _load_signer(path_str: str):
    from eth_account import Account

    path = Path(path_str)
    if (os.name != "posix" or not path.is_absolute() or path.is_symlink() or
            ".." in path.parts or not str(path).startswith("/run/sse/")):
        raise NodeTxError("signing file requires a local Ubuntu /run/sse/ path")
    st, parent = path.stat(), path.parent.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
            stat.S_IMODE(st.st_mode) != 0o600 or
            parent.st_uid != os.geteuid() or parent.st_mode & 0o022 or
            not 64 <= st.st_size <= 67):
        raise NodeTxError("unsafe signer file ownership or mode")
    raw = path.read_text(encoding="ascii").strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        raise NodeTxError("invalid local signer material")
    return Account.from_key(bytes.fromhex(raw))


def execute(rpc, plan: Plan, signer, *, max_total_wei: int,
            selected_bid_fee: int | None = None):
    uint(max_total_wei, "max total spend", minimum=1)
    owner = signer.address
    preflight(rpc, plan, signer=owner, expected_selected_fee=selected_bid_fee)
    # eth_estimateGas uses the actual signer and exact calldata/value, so
    # authorization and state-dependent reverts are checked before signing.
    call = {"from": owner, "to": plan.target, "data": plan.data,
            "value": hex(plan.value)}
    estimate = _hex_int(rpc.request("eth_estimateGas", [call]))
    gas = min(MAX_GAS, estimate * 12 // 10 + 4000)
    if estimate == 0 or gas <= estimate or gas > MAX_GAS:
        raise NodeTxError("transaction gas budget outside safe bounds")
    price = _hex_int(rpc.request("eth_gasPrice", []))
    uint(price, "gas price", minimum=1)
    if plan.value + gas * price > max_total_wei:
        raise NodeTxError("transaction exceeds local maximum total spend")
    nonce = _hex_int(rpc.request("eth_getTransactionCount", [owner, "pending"]))
    tx = {"chainId": plan.chain_id, "nonce": nonce, "gas": gas,
          "gasPrice": price, "to": plan.target,
          "value": plan.value, "data": plan.data}
    try:
        signed = signer.sign_transaction(tx)
    except (ValueError, TypeError):
        raise NodeTxError("local signing failed") from None
    own_hash = "0x" + signed.hash.hex()
    emitted_hash = rpc.request("eth_sendRawTransaction", [
        "0x" + signed.raw_transaction.hex()])
    if type(emitted_hash) is not str or emitted_hash.lower() != own_hash.lower():
        raise NodeTxError("RPC returned unexpected signed transaction hash")
    for _ in range(30):
        receipt = rpc.request("eth_getTransactionReceipt", [emitted_hash])
        if receipt is not None:
            if type(receipt) is not dict or receipt.get("transactionHash", "").lower() != own_hash.lower():
                raise NodeTxError("invalid transaction receipt identity")
            if _hex_int(receipt.get("status")) != 1:
                raise NodeTxError("transaction reverted: " + own_hash)
            return {"transactionHash": own_hash, "status": "MINED_UNFINALIZED",
                    "blockNumber": _hex_int(receipt.get("blockNumber")),
                    "gasUsed": _hex_int(receipt.get("gasUsed")),
                    "role": plan.role, "action": plan.action,
                    "serviceVerified": False, "evidenceQualified": False}
        time.sleep(0.5)
    return {"transactionHash": own_hash, "status": "SUBMITTED_RECEIPT_NOT_YET_SEEN",
            "role": plan.role, "action": plan.action}


def main(argv=None):
    p = argparse.ArgumentParser(description="SSE role-owned Ethereum transactions; dry-run default")
    p.add_argument("--role", required=True, choices=("consumer", "provider", "monitor"))
    p.add_argument("--action", required=True, choices=sorted(ACTIONS))
    p.add_argument("--params-json", required=True,
                   help="JSON object with public action parameters; NEVER keys")
    p.add_argument("--chain-id", required=True, type=int)
    p.add_argument("--board", required=True)
    p.add_argument("--settlement", required=True)
    p.add_argument("--pool", required=True)
    p.add_argument("--rpc-url", help="required for explicit execution")
    p.add_argument("--signer-file", help="owner-only /run/sse/ key file; execute only")
    p.add_argument("--max-total-wei", type=int, help="upper bound including gas; execute only")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args(argv)
    try:
        params = json.loads(args.params_json)
        plan = make_plan(args.action, args.role, chain_id=args.chain_id,
                         board=args.board, settlement=args.settlement,
                         pool=args.pool, params=params)
        if not args.execute:
            print(json.dumps(plan.public(), indent=2, sort_keys=True))
            return 0
        if not args.rpc_url or not args.signer_file or args.max_total_wei is None:
            raise NodeTxError("execution requires RPC URL, local signer file and spend cap")
        signer = _load_signer(args.signer_file)
        result = execute(RPC(args.rpc_url), plan, signer,
                         max_total_wei=args.max_total_wei,
                         selected_bid_fee=params.get("selectedEpochFeeWei"))
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (NodeTxError, OSError, ValueError, UnicodeError, KeyError) as exc:
        print("SSE_NODE_TX_FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
