"""Read-only, fail-closed inspection of deployed SSESettlement leases and epochs.

This tool DOES NOT submit transactions, prove an HTTP response was timely, or
produce signed monitoring evidence. It only binds the local view to on-chain
state at a consistent block height.

Run from the SSE project root:
  python tools/sse_chain_read.py --rpc-url http://127.0.0.1:8545 \
    --settlement 0x... --lease-id 1 --epoch-id 0
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sse_challenge import expected_response_hash, keccak256

ADDR = re.compile(r"0x[0-9a-fA-F]{40}\Z")
HEX = re.compile(r"0x[0-9a-fA-F]*\Z")
ZERO_ADDR = "0x" + "00" * 20
ZERO_HASH = "0x" + "00" * 32

LEASE_FIELDS = (
    ("consumer", "address"), ("provider", "address"), ("monitors", "address[4]"),
    ("assignmentId", "uint256"), ("serviceEndpointHash", "bytes32"),
    ("resourceProfileHash", "bytes32"), ("slaPolicyHash", "bytes32"),
    ("marketplaceRequestId", "uint256"), ("totalEscrow", "uint256"),
    ("uncommittedEscrow", "uint256"), ("refundedUnusedEscrow", "uint256"),
    ("epochFee", "uint256"), ("reservationFee", "uint256"),
    ("exposureBudget", "uint256"), ("currentExposure", "uint256"),
    ("nextEpochId", "uint256"), ("maxEpochs", "uint256"),
    ("responsePeriod", "uint64"), ("monitoringGrace", "uint64"),
    ("evidenceWindow", "uint64"), ("monitorConfirmations", "uint8"),
    ("state", "uint8"),
)
EPOCH_FIELDS = (
    ("requestHash", "bytes32"), ("responseHash", "bytes32"),
    ("fee", "uint256"), ("reservationFee", "uint256"),
    ("responseDeadline", "uint64"), ("monitoringClose", "uint64"),
    ("evidenceClose", "uint64"), ("providerCredited", "uint256"),
    ("consumerCredited", "uint256"), ("unresolvedExposure", "uint256"),
    ("successVotes", "uint8"), ("failureVotes", "uint8"),
    ("exists", "bool"), ("acknowledged", "bool"),
    ("responseAuthenticated", "bool"), ("monitoringSealed", "bool"),
    ("evidenceClosed", "bool"), ("outcome", "uint8"),
)
LEASE_STATES = ("Offered", "Accepted", "Ready", "Active", "Closed")
OUTCOMES = ("None", "Success", "Failure")


class ChainReadError(ValueError):
    """Chain mismatch, malformed RPC data, or invalid/unsafe supplied input."""


def _address(value: str) -> str:
    if not isinstance(value, str) or not ADDR.fullmatch(value):
        raise ChainReadError("settlement must be a 20-byte Ethereum address")
    return "0x" + value[2:].lower()


def _hex_integer(value: str) -> int:
    if not isinstance(value, str) or not HEX.fullmatch(value) or len(value) < 3:
        raise ChainReadError("invalid hexadecimal RPC integer")
    return int(value, 16)


def _utc(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


class LocalRPC:
    def __init__(self, url: str, timeout: float = 4.0):
        u = urlsplit(url)
        try:
            port = u.port
        except ValueError as exc:
            raise ChainReadError("invalid RPC port") from exc
        if (u.scheme != "http" or u.hostname != "127.0.0.1" or
                u.username is not None or u.password is not None or
                port is None or not 1 <= port <= 65535 or
                u.path not in ("", "/") or u.query or u.fragment):
            raise ChainReadError("only http://127.0.0.1:PORT RPC is permitted in this local patch")
        self.url = url
        self.timeout = timeout
        self._id = 0

    def request(self, method: str, params: list):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        request = Request(self.url, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ChainReadError(f"RPC HTTP status {response.status}")
                data = json.loads(response.read(1024 * 1024 + 1))
        except (OSError, TimeoutError, ValueError) as exc:
            raise ChainReadError(f"RPC request {method} failed: {exc}") from exc
        if not isinstance(data, dict) or data.get("id") != self._id or data.get("jsonrpc") != "2.0":
            raise ChainReadError(f"invalid RPC envelope for {method}")
        if data.get("error") is not None:
            raise ChainReadError(f"RPC error for {method}: {data['error']}")
        if "result" not in data:
            raise ChainReadError(f"missing RPC result for {method}")
        return data["result"]


def _words(data: str, count: int) -> list[str]:
    if not isinstance(data, str) or not HEX.fullmatch(data) or len(data) != 2 + count * 64:
        raise ChainReadError(f"unexpected ABI result size (expected {count} words)")
    return [data[2 + i * 64:2 + (i + 1) * 64].lower() for i in range(count)]


def _decode_word(word: str, field_type: str):
    val = int(word, 16)
    if field_type == "address":
        if val >> 160:
            raise ChainReadError("non-canonical ABI address")
        return "0x" + word[-40:]
    if field_type == "bytes32":
        return "0x" + word
    if field_type == "bool":
        if val not in (0, 1):
            raise ChainReadError("invalid ABI boolean")
        return bool(val)
    if field_type.startswith("uint"):
        width = int(field_type[4:])
        if val >= 2 ** width:
            raise ChainReadError(f"value exceeds {field_type}")
        return val
    raise ChainReadError(f"unsupported ABI type {field_type}")


def decode_struct(data: str, fields: tuple) -> dict:
    count = sum(4 if kind == "address[4]" else 1 for _, kind in fields)
    words = iter(_words(data, count))
    obj = {}
    for name, kind in fields:
        if kind == "address[4]":
            obj[name] = [_decode_word(next(words), "address") for _ in range(4)]
        else:
            obj[name] = _decode_word(next(words), kind)
    return obj


def _function_call(signature: str, args: tuple[int, ...] = ()) -> str:
    selector = keccak256(signature.encode("ascii"))[:4]
    return "0x" + (selector + b"".join(value.to_bytes(32, "big") for value in args)).hex()


def _call(rpc, contract: str, signature: str, args: tuple[int, ...], block: str) -> str:
    result = rpc.request("eth_call", [{"to": contract, "data": _function_call(signature, args)}, block])
    if not isinstance(result, str) or not HEX.fullmatch(result):
        raise ChainReadError(f"bad eth_call result for {signature}")
    return result


def _domain_separator(chain_id: int, contract: str) -> str:
    encoded = b"".join((
        keccak256(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
        keccak256(b"SSESettlement"), keccak256(b"1"),
        chain_id.to_bytes(32, "big"), int(contract, 16).to_bytes(32, "big"),
    ))
    return "0x" + keccak256(encoded).hex()


def inspect_chain(rpc, settlement: str, lease_id: int, epoch_id: int,
                  expected_chain_id: int = 31337, endpoint: str | None = None,
                  now: float | None = None) -> dict:
    """Inspect a single consistent block; do not produce a monitoring certificate."""
    contract = _address(settlement)
    if type(lease_id) is not int or lease_id < 1 or type(epoch_id) is not int or epoch_id < 0:
        raise ChainReadError("lease-id must be >=1 and epoch-id >=0")
    if type(expected_chain_id) is not int or expected_chain_id < 1:
        raise ChainReadError("invalid expected chain ID")
    chain_id = _hex_integer(rpc.request("eth_chainId", []))
    if chain_id != expected_chain_id:
        raise ChainReadError(f"wrong chain ID: received {chain_id}, expected {expected_chain_id}")
    block_tag = rpc.request("eth_blockNumber", [])
    block_number = _hex_integer(block_tag)
    block_tag = hex(block_number)
    block = rpc.request("eth_getBlockByNumber", [block_tag, False])
    if not isinstance(block, dict) or _hex_integer(block.get("number")) != block_number:
        raise ChainReadError("inconsistent block snapshot")
    block_timestamp = _hex_integer(block.get("timestamp"))
    code = rpc.request("eth_getCode", [contract, block_tag])
    if not isinstance(code, str) or not HEX.fullmatch(code) or len(code) < 4:
        raise ChainReadError("no deployed settlement bytecode at configured address")

    onchain_domain = _call(rpc, contract, "domainSeparator()", (), block_tag)
    if _words(onchain_domain, 1)[0] != _domain_separator(chain_id, contract)[2:]:
        raise ChainReadError("EIP-712 domain does not match SSESettlement v1, chain and address")
    next_lease_id = int(_words(_call(rpc, contract, "nextLeaseId()", (), block_tag), 1)[0], 16)
    if lease_id >= next_lease_id:
        raise ChainReadError(f"lease {lease_id} not allocated (nextLeaseId={next_lease_id})")
    lease = decode_struct(_call(rpc, contract, "getLease(uint256)", (lease_id,), block_tag), LEASE_FIELDS)
    if lease["consumer"] == ZERO_ADDR or lease["provider"] == ZERO_ADDR:
        raise ChainReadError("allocated lease has a zero consumer/provider")
    if lease["state"] >= len(LEASE_STATES) or lease["monitorConfirmations"] > 4:
        raise ChainReadError("invalid lease state or confirmation count")
    lease["stateName"] = LEASE_STATES[lease["state"]]

    if endpoint is not None:
        u = urlsplit(endpoint)
        try:
            port = u.port
        except ValueError as exc:
            raise ChainReadError("invalid provider endpoint") from exc
        if (u.scheme != "http" or u.hostname != "127.0.0.1" or
                port is None or not 1 <= port <= 65535 or u.username or u.password or
                u.query or u.fragment or u.path not in ("", "/")):
            raise ChainReadError("provider endpoint must be a localhost HTTP root URL")
        digest = "0x" + keccak256(endpoint.encode("utf-8")).hex()
        if digest != lease["serviceEndpointHash"]:
            raise ChainReadError("provider endpoint does not match on-chain serviceEndpointHash")

    if epoch_id >= lease["nextEpochId"]:
        epoch = None
        status = "NO_EPOCH_ADMITTED"
    else:
        epoch = decode_struct(_call(rpc, contract, "getEpoch(uint256,uint256)",
                                          (lease_id, epoch_id), block_tag), EPOCH_FIELDS)
        if not epoch["exists"]:
            raise ChainReadError("epoch missing despite nextEpochId indicating admission")
        if epoch["outcome"] >= len(OUTCOMES):
            raise ChainReadError("invalid epoch outcome enum")
        epoch["outcomeName"] = OUTCOMES[epoch["outcome"]]
        if (epoch["requestHash"] == ZERO_HASH or
                epoch["responseHash"] != expected_response_hash(epoch["requestHash"])):
            raise ChainReadError("on-chain epoch response hash incompatible with challenge algorithm")
        if not (epoch["responseDeadline"] < epoch["monitoringClose"] < epoch["evidenceClose"]):
            raise ChainReadError("invalid on-chain monitoring windows")
        for name in ("responseDeadline", "monitoringClose", "evidenceClose"):
            epoch[name + "Utc"] = _utc(epoch[name])
        status = "EPOCH_FOUND"

    now = time.time() if now is None else now
    return {
        "schema": "sse-onchain-inspection-v1", "status": status,
        "chainId": chain_id, "settlementAddress": contract,
        "blockNumber": block_number, "blockTimestamp": block_timestamp,
        "blockTimestampUtc": _utc(block_timestamp), "localUnixTime": now,
        "localMinusBlockSeconds": round(now - block_timestamp, 3),
        "domainSeparatorMatches": True, "nextLeaseId": next_lease_id,
        "endpointCommitmentChecked": endpoint is not None,
        "leaseId": lease_id, "lease": lease, "epochId": epoch_id, "epoch": epoch,
        "chainDeadlineRead": epoch is not None,
        "deadlineTimelinessCertified": False,
        "providerSignatureVerified": False, "monitorVoteSigned": False,
        "computeProvisioningVerified": False, "readOnly": True,
        "warning": "A chain deadline is not proof of timely HTTP response or a trusted wall clock."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only inspect deployed SSE lease and epoch")
    parser.add_argument("--rpc-url", default="http://127.0.0.1:8545")
    parser.add_argument("--settlement", required=True)
    parser.add_argument("--lease-id", type=int, required=True)
    parser.add_argument("--epoch-id", type=int, default=0)
    parser.add_argument("--expected-chain-id", type=int, default=31337)
    parser.add_argument("--endpoint", help="Optional: verify exact endpoint commitment; do not use for missing hash")
    args = parser.parse_args()
    try:
        result = inspect_chain(LocalRPC(args.rpc_url), args.settlement, args.lease_id,
                               args.epoch_id, args.expected_chain_id, args.endpoint)
    except ChainReadError as exc:
        parser.exit(2, f"SSE on-chain inspection rejected: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
