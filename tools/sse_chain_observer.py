#!/usr/bin/env python3
"""SSE R8 independent READ-ONLY EVM explorer: blocks, receipts, and contract logs.

No wallet keys, signing, transaction submission, machine controls or settlement
decisions. Any explorer data from a single configured RPC is provisional and
must not be labeled a verified finality proof or physical SLA observation.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
TX = re.compile(r"0x[0-9a-fA-F]{64}\Z")
HEX = re.compile(r"0x(?:[0-9a-fA-F]{2})*\Z")
HEXNUM = re.compile(r"0x[0-9a-fA-F]+\Z")
RPC_METHODS = frozenset({
    "eth_chainId", "eth_blockNumber", "eth_getBlockByNumber", "eth_getCode",
    "eth_getTransactionByHash", "eth_getTransactionReceipt", "eth_getLogs",
})


class ObserverError(ValueError):
    pass


def _qty(value, field):
    if type(value) is not str or not HEXNUM.fullmatch(value):
        raise ObserverError("malformed chain quantity: " + field)
    return int(value, 16)


def read_config(environ=None):
    env = os.environ if environ is None else environ
    url = env.get("SSE_OBSERVER_RPC_URL", "")
    chain_id = env.get("SSE_OBSERVER_CHAIN_ID", "")
    raw = env.get("SSE_OBSERVER_CONTRACTS", "")
    if not (url and chain_id and raw):
        raise ObserverError("observer RPC, chain ID and allowed contracts are required")
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError:
        raise ObserverError("invalid observer RPC port") from None
    if (u.scheme not in ("https", "http") or not u.hostname or
            u.username or u.password or u.query or u.fragment or
            u.path not in ("", "/") or
            (u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1", "::1")) or
            (port is not None and not 1 <= port <= 65535)):
        raise ObserverError("observer requires HTTPS or loopback HTTP RPC")
    if not chain_id.isdecimal() or int(chain_id) < 1 or int(chain_id) >= 2**256:
        raise ObserverError("invalid observer chain ID")
    contracts = tuple(v.strip().lower() for v in raw.split(","))
    if (not 1 <= len(contracts) <= 12 or len(set(contracts)) != len(contracts)
            or any(not ADDR.fullmatch(a) or int(a,16) == 0 for a in contracts)):
        raise ObserverError("invalid observer allowlisted contracts")
    return {"url": url.rstrip("/"), "chain_id": int(chain_id),
            "contracts": contracts}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObserverError("RPC redirect forbidden")


class Observer:
    def __init__(self, config, transport=None):
        self.config = config
        self.counter = 0
        self.transport = transport or self._request

    def _request(self, method, params):
        url = self.config["url"]
        self.counter += 1
        envelope = {"jsonrpc": "2.0", "id": self.counter,
                    "method": method, "params": params}
        req = Request(url, data=json.dumps(envelope).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(req, timeout=8) as resp:
                if resp.status != 200:
                    raise ObserverError("unexpected observer RPC status")
                raw = resp.read(1_048_577)
        except OSError:
            raise ObserverError("observer RPC unavailable") from None
        if len(raw) > 1_048_576:
            raise ObserverError("observer RPC response too large")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ObserverError("invalid observer RPC response") from None
        if (type(payload) is not dict or payload.get("jsonrpc") != "2.0" or
                payload.get("id") != self.counter or payload.get("error") is not None or
                "result" not in payload):
            raise ObserverError("unexpected observer RPC response")
        return payload["result"]

    def rpc(self, method, params):
        if method not in RPC_METHODS or type(params) is not list:
            raise ObserverError("unsupported read-only chain method")
        return self.transport(method, params)

    def head(self):
        actual = _qty(self.rpc("eth_chainId", []), "chainId")
        if actual != self.config["chain_id"]:
            raise ObserverError("RPC chain ID mismatch")
        return _qty(self.rpc("eth_blockNumber", []), "blockNumber")

    def overview(self):
        head = self.head()
        block = self.rpc("eth_getBlockByNumber", [hex(head), False])
        if type(block) is not dict:
            raise ObserverError("chain head block unavailable")
        if _qty(block.get("number"), "block number") != head:
            raise ObserverError("chain head number mismatch")
        deployed = []
        for contract in self.config["contracts"]:
            code = self.rpc("eth_getCode", [contract, hex(head)])
            if type(code) is not str or not HEX.fullmatch(code):
                raise ObserverError("invalid contract bytecode response")
            deployed.append({"address": contract, "hasCode": bool(int(code, 16))
                             if code != "0x" else False})
        return {"chainId": self.config["chain_id"], "headNumber": head,
                "headHash": block.get("hash"),
                "contractAddresses": deployed, "rpcFinalityVerified": False,
                "ethTransactionsSent": False, "networkAuthority": "READ_ONLY"}

    def blocks(self, limit: int = 10):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ObserverError("block history limit out of bounds")
        head = self.head()
        rows = []
        for number in range(head, max(-1, head - limit), -1):
            block = self.rpc("eth_getBlockByNumber", [hex(number), False])
            if type(block) is not dict or _qty(block.get("number"), "block number") != number:
                raise ObserverError("block unavailable or inconsistent")
            transactions = block.get("transactions")
            if type(transactions) is not list:
                raise ObserverError("invalid block transaction list")
            rows.append({"number": number, "hash": block.get("hash"),
                         "parentHash": block.get("parentHash"),
                         "timestamp": _qty(block.get("timestamp"), "timestamp"),
                         "transactionCount": len(transactions),
                         "transactionHashes": transactions[:50],
                         "gasUsed": _qty(block.get("gasUsed"), "gasUsed"),
                         "finality": "UNVERIFIED"})
        return {"chainId": self.config["chain_id"], "headNumber": head,
                "blocks": rows, "readOnly": True}

    def transaction(self, tx_hash: str):
        if type(tx_hash) is not str or not TX.fullmatch(tx_hash):
            raise ObserverError("invalid transaction hash")
        head = self.head()
        tx = self.rpc("eth_getTransactionByHash", [tx_hash])
        if tx is None:
            return {"found": False, "hash": tx_hash, "chainId": self.config["chain_id"]}
        if (type(tx) is not dict or type(tx.get("hash")) is not str or
                tx["hash"].lower() != tx_hash.lower()):
            raise ObserverError("transaction identity mismatch")
        receipt = self.rpc("eth_getTransactionReceipt", [tx_hash])
        if (receipt is not None and
                (type(receipt) is not dict or
                 type(receipt.get("transactionHash")) is not str or
                 receipt["transactionHash"].lower() != tx_hash.lower())):
            raise ObserverError("receipt identity mismatch")
        block_number = tx.get("blockNumber")
        included = block_number is not None
        height = _qty(block_number, "transaction block") if included else None
        if included and (receipt is None or height > head):
            raise ObserverError("inconsistent transaction inclusion/receipt")
        logs = receipt.get("logs", []) if receipt is not None else []
        if type(logs) is not list:
            raise ObserverError("invalid receipt logs")
        return {"found": True, "hash": tx_hash, "chainId": self.config["chain_id"],
                "from": tx.get("from"), "to": tx.get("to"),
                "valueWei": _qty(tx.get("value"), "value"),
                "nonce": _qty(tx.get("nonce"), "nonce"),
                "inputSelector": (tx.get("input") or "0x")[:10],
                "blockNumber": height, "blockHash": tx.get("blockHash"),
                "confirmations": head - height + 1 if included else 0,
                "receiptStatus": (_qty(receipt.get("status"), "receipt status")
                                  if receipt is not None else None),
                "gasUsed": (_qty(receipt.get("gasUsed"), "gasUsed")
                            if receipt is not None else None),
                "logs": [self._log(x) for x in logs[:100]],
                "logsTruncated": len(logs) > 100,
                "finality": "UNVERIFIED", "transactionWasSentByObserver": False}

    @staticmethod
    def _log(item):
        if type(item) is not dict:
            raise ObserverError("invalid contract event log")
        return {k: item.get(k) for k in ("address", "topics", "data", "blockNumber",
                                         "blockHash", "transactionHash", "logIndex",
                                         "removed")}

    def events(self, start: int, end: int):
        if (type(start) is not int or type(end) is not int or start < 0 or
                end < start or end - start > 255):
            raise ObserverError("contract event range must be <= 256 blocks")
        head = self.head()
        if end > head:
            raise ObserverError("event range is beyond latest chain head")
        raw = self.rpc("eth_getLogs", [{
            "fromBlock": hex(start), "toBlock": hex(end),
            "address": list(self.config["contracts"])}])
        if type(raw) is not list:
            raise ObserverError("invalid contract event list")
        allowed = set(self.config["contracts"])
        results = []
        for item in raw[:501]:
            event = self._log(item)
            if type(event["address"]) is not str or event["address"].lower() not in allowed:
                raise ObserverError("nonallowlisted contract in RPC response")
            results.append(event)
        return {"chainId": self.config["chain_id"], "startBlock": start,
                "endBlock": end, "events": results[:500],
                "truncated": len(raw) > 500, "finality": "UNVERIFIED",
                "readOnly": True}
