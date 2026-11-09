"""Canonical compute resource profile and hash.

The consumer and provider agree to the exact bytes of this record before
createLease. The contract stores only its Keccak commitment. The monitor verifies
that the local descriptor matches the on-chain commitment and endpoint. This is
an integrity/identity binding, not attestation that Docker honored the limits.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from sse_challenge import keccak256

SCHEMA = 'sse-compute-resource-profile-v1'
SLA = 'TWO_HONEST_MONITORS_TIMELY_VALID_RESPONSE_V1'
RESERVATION = 'CONTRACTUALLY_AGREED_RESERVATION_OPTION_V1'
PREFIX = b'SSE_COMPUTE_PROFILE_V1\x00'
EXPECTED_KEYS = frozenset({
    'schema', 'imageId', 'cpuMilli', 'memoryBytes', 'endpoint',
    'slaMetric', 'reservationBasis'
})
IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')


def validate_profile(profile: dict) -> dict:
    if not isinstance(profile, dict) or set(profile) != EXPECTED_KEYS:
        raise ValueError('profile fields must match schema exactly (no extras or omissions)')
    if profile['schema'] != SCHEMA:
        raise ValueError('unexpected compute profile schema')
    if not isinstance(profile['imageId'], str) or not IMAGE_ID.fullmatch(profile['imageId']):
        raise ValueError('imageId must be an immutable sha256 image ID')
    cpu, mem = profile['cpuMilli'], profile['memoryBytes']
    if type(cpu) is not int or not 1 <= cpu <= 64000:
        raise ValueError('cpuMilli must be a positive integer <= 64000')
    if type(mem) is not int or not (64 * 2**20 <= mem <= 512 * 2**30):
        raise ValueError('memoryBytes outside supported range')
    endpoint = profile['endpoint']
    if not isinstance(endpoint, str):
        raise ValueError('endpoint must be a string')
    url = urlparse(endpoint)
    try:
        port = url.port
    except ValueError as error:
        raise ValueError('malformed endpoint port') from error
    if url.scheme not in ('http', 'https') or not url.hostname or port is None or port <= 0:
        raise ValueError('endpoint must include an explicit HTTP(S) port')
    if url.username is not None or url.password is not None or url.path or url.params or url.query or url.fragment:
        raise ValueError('endpoint must be a root URL without credentials, path, or query')
    if url.geturl() != endpoint:
        raise ValueError('endpoint normalization mismatch')
    if profile['slaMetric'] != SLA:
        raise ValueError('unrecognized monitoring SLA semantics')
    if profile['reservationBasis'] != RESERVATION:
        raise ValueError('unrecognized reservation entitlement semantics')
    return profile


def canonical_profile(profile: dict) -> bytes:
    validate_profile(profile)
    return json.dumps(profile, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def profile_hash(profile: dict) -> str:
    return '0x' + keccak256(PREFIX + canonical_profile(profile)).hex()


def endpoint_hash(endpoint: str) -> str:
    return '0x' + keccak256(endpoint.encode('utf-8')).hex()


def load_profile(path: str | Path) -> dict:
    with open(path, encoding='utf-8') as f:
        profile = json.load(f)
    validate_profile(profile)
    return profile


def verify_lease_profile(profile: dict, lease: dict, endpoint: str) -> str:
    """Fail closed before a monitor produces a certificate for the wrong lease."""
    digest = profile_hash(profile)
    if lease.get('resourceProfileHash', '').lower() != digest:
        raise ValueError('resource profile does not match the on-chain lease commitment')
    if profile['endpoint'] != endpoint or lease.get('serviceEndpointHash', '').lower() != endpoint_hash(endpoint):
        raise ValueError('endpoint does not match both the profile and on-chain lease')
    return digest


def example_profile(image_id: str, endpoint: str, cpu_milli=500, memory_bytes=512 * 2**20) -> dict:
    profile = {
        'schema': SCHEMA,
        'imageId': image_id,
        'cpuMilli': cpu_milli,
        'memoryBytes': memory_bytes,
        'endpoint': endpoint,
        'slaMetric': SLA,
        'reservationBasis': RESERVATION,
    }
    return validate_profile(profile)


def cli() -> None:
    parser = argparse.ArgumentParser(description='Generate and hash an immutable resource profile')
    parser.add_argument('--image-id', required=True, help='docker image inspect --format {{.Id}} IMAGE')
    parser.add_argument('--endpoint', required=True, help='Root monitor-visible HTTP endpoint, including port')
    parser.add_argument('--cpu-milli', type=int, default=500)
    parser.add_argument('--memory-bytes', type=int, default=512 * 2**20)
    parser.add_argument('--output', required=True, help='Save canonical profile JSON to this path')
    args = parser.parse_args()
    profile = example_profile(args.image_id, args.endpoint, args.cpu_milli, args.memory_bytes)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_profile(profile) + b'\n')
    print(json.dumps({
        'resourceProfileHash': profile_hash(profile),
        'serviceEndpointHash': endpoint_hash(args.endpoint),
        'manifest': str(path), 'imageId': profile['imageId'],
    }, indent=2))


if __name__ == '__main__':
    cli()
