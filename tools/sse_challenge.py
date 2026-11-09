"""Challenge response commitment matching SSESettlement.admitEpoch() (ABI bytes32 encoding)."""

import re

try:
    from Crypto.Hash import keccak
except ImportError as exc:
    raise RuntimeError("Missing pycryptodome: run python -m pip install -r requirements.txt") from exc

_HASH = re.compile(r"0x[0-9a-fA-F]{64}\Z")


def bytes32(value: str) -> bytes:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("requestHash must be exactly 0x followed by 64 hexadecimal characters")
    return bytes.fromhex(value[2:])


def keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


RESPONSE_LABEL = keccak256(b"SSE_RESPONSE")


def expected_response_hash(request_hash: str) -> str:
    """Solidity: keccak256(abi.encode(keccak256('SSE_RESPONSE'), requestHash))."""
    return "0x" + keccak256(RESPONSE_LABEL + bytes32(request_hash)).hex()
