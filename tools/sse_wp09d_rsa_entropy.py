"""WP09D: deterministic RSA-2048 research proof vectors (NOT a standardized VRF).

Only local laboratory use. One public/test private exponent is checked into the
repository intentionally: it is INSECURE and must never be provisioned on a
public network. The contract's verifier does not know the private exponent.
The proof operator can selectively withhold an otherwise unique answer.
"""
from __future__ import annotations

import json
from pathlib import Path

from eth_abi import encode

try:
    from sse_challenge import keccak256
except ModuleNotFoundError:
    from tools.sse_challenge import keccak256

REPRESENTATIVE_DOMAIN = keccak256(b"SSERSA2048RepresentativeV1")
RSA_ENTROPY_DOMAIN = keccak256(b"SSERSAProofEntropyV1")
RSA_MODULUS_BYTES = 256
RSA_PUBLIC_EXPONENT = 65537
LAB_KEY_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wp09d_public_lab_rsa2048.json"


def _digest(data: bytes) -> bytes:
    if type(data) is not bytes or len(data) != 32:
        raise ValueError("expected exact bytes32")
    return data


def _positive_hex_number(value: str) -> int:
    if type(value) is not str or not value.startswith("0x"):
        raise ValueError("expected hexadecimal integer")
    result = int(value[2:], 16)
    if result <= 0:
        raise ValueError("expected positive integer")
    return result


def representative(request_digest: bytes) -> bytes:
    """Bit-for-bit matching the fixed eight Keccak ABI expansion in Solidity."""
    _digest(request_digest)
    chunks = [
        keccak256(encode(["bytes32", "bytes32", "uint256"], [
            REPRESENTATIVE_DOMAIN, request_digest, i
        ]))
        for i in range(8)
    ]
    expanded = b"".join(chunks)
    return bytes([expanded[0] & 0x7f]) + expanded[1:]


def rsa_request_digest(chain_id: int, pool: str, request_id: int,
                       request_block: int, snapshot_hash: bytes) -> bytes:
    _digest(snapshot_hash)
    if type(chain_id) is not int or chain_id <= 0 or type(request_id) is not int or request_id <= 0:
        raise ValueError("invalid chain or request ID")
    if type(request_block) is not int or request_block < 0:
        raise ValueError("invalid request block")
    if type(pool) is not str or not pool.startswith("0x") or len(pool) != 42:
        raise ValueError("invalid pool address")
    return keccak256(encode(
        ["bytes32", "uint256", "address", "uint256", "uint256", "bytes32"],
        [RSA_ENTROPY_DOMAIN, chain_id, pool, request_id, request_block, snapshot_hash]
    ))


def read_lab_key() -> tuple[int, int]:
    key = json.loads(LAB_KEY_PATH.read_text(encoding="utf-8"))
    if "LAB-ONLY" not in key["_warning"]:
        raise ValueError("refusing key without explicit lab-only label")
    n = _positive_hex_number(key["modulus"])
    d = _positive_hex_number(key["private_exponent"])
    if n.bit_length() != 2048 or n % 2 == 0 or d >= n or key["public_exponent"] != RSA_PUBLIC_EXPONENT:
        raise ValueError("invalid laboratory RSA fixture")
    return n, d


def laboratory_proof(request_digest: bytes, n: int, d: int) -> bytes:
    """Test ONLY: the private key is public, so this proves no real entropy."""
    m = int.from_bytes(representative(_digest(request_digest)), "big")
    if type(n) is not int or n.bit_length() != 2048 or n % 2 == 0 or m >= n:
        raise ValueError("invalid 2048-bit RSA modulus")
    if type(d) is not int or d <= 0:
        raise ValueError("invalid exponent")
    proof = pow(m, d, n).to_bytes(RSA_MODULUS_BYTES, "big")
    if not verify_proof(request_digest, proof, n):
        raise ValueError("public test RSA modulus/exponent inconsistent")
    return proof


def verify_proof(request_digest: bytes, proof: bytes, n: int) -> bool:
    if type(proof) is not bytes or len(proof) != RSA_MODULUS_BYTES:
        return False
    if type(n) is not int or n.bit_length() != 2048 or n % 2 == 0:
        return False
    p = int.from_bytes(proof, "big")
    if p >= n:
        return False
    return pow(p, RSA_PUBLIC_EXPONENT, n) == int.from_bytes(
        representative(_digest(request_digest)), "big"
    )


def seed_from_proof(request_digest: bytes, proof: bytes) -> int:
    _digest(request_digest)
    if type(proof) is not bytes or len(proof) != RSA_MODULUS_BYTES:
        raise ValueError("expected canonical 256-byte proof")
    return int.from_bytes(keccak256(encode(
        ["bytes32", "bytes32", "bytes32"],
        [RSA_ENTROPY_DOMAIN, request_digest, keccak256(proof)]
    )), "big")
