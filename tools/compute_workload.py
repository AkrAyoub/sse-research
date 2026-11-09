"""SSE CPU exercise tied to the epoch's random requestHash.

A deterministic workload, not a cryptographic proof of CPU consumption or
trusted resource attestation. Only the expected output is authenticated by the
HTTP observation; a malicious provider can emulate it without a container.
"""
from __future__ import annotations
import hashlib
import re

ROUNDS = 8192
SCHEMA = 'sse-local-compute-result-v1'
_HASH = re.compile(r'0x[0-9a-fA-F]{64}\Z')


def compute_result(lease_id: int, epoch_id: int, request_hash: str) -> dict:
    if type(lease_id) is not int or not 1 <= lease_id < 2**256:
        raise ValueError('invalid leaseId')
    if type(epoch_id) is not int or not 0 <= epoch_id < 2**256:
        raise ValueError('invalid epochId')
    if not isinstance(request_hash, str) or not _HASH.fullmatch(request_hash):
        raise ValueError('invalid requestHash')
    seed = (b'SSE_LOCAL_COMPUTE_V1\x00' + lease_id.to_bytes(32, 'big')
            + epoch_id.to_bytes(32, 'big') + bytes.fromhex(request_hash[2:]))
    state = hashlib.sha256(seed).digest()
    for i in range(ROUNDS):
        state = hashlib.sha256(state + i.to_bytes(4, 'big')).digest()
    return {'schema': SCHEMA, 'leaseId': lease_id, 'epochId': epoch_id,
            'requestHash': request_hash.lower(), 'rounds': ROUNDS,
            'resultDigest': 'sha256:' + state.hex()}
