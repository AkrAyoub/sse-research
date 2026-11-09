"""Fail-closed remote challenge probe requiring an SSESettlement EIP-712 provider signature.

The legacy HTTP demo has no provider signature and deliberately cannot pass this
probe. Do not treat an unsigned HTTP 200 as a SUCCESS vote. A signed response
establishes attribution, NOT proof of network delivery or execution.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sse_challenge import bytes32, expected_response_hash
from typed_evidence import Domain, verify_provider_response

MAX_RESPONSE_BYTES = 4096


def validate_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str):
        raise ValueError('endpoint must be an HTTP(S) root URL')
    url = urlsplit(endpoint)
    try:
        port = url.port
    except ValueError as exc:
        raise ValueError('malformed port') from exc
    if (url.scheme not in ('http', 'https') or not url.hostname or
            port is None or not 1 <= port <= 65535 or
            url.username is not None or url.password is not None or
            url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('endpoint must be a root HTTP(S) URL with explicit port, no credentials')
    # Never silently turn the localhost-only prototype into insecure remote HTTP.
    if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('remote monitor endpoint requires HTTPS (R4 security baseline)')
    return endpoint.rstrip('/') + '/v1/challenge'


def signed_probe(endpoint: str, domain: Domain, provider: str,
                 lease_id: int, epoch_id: int, request_hash: str, timeout=2.0) -> dict:
    url = validate_endpoint(endpoint)
    bytes32(request_hash)
    if type(lease_id) is not int or lease_id < 1 or type(epoch_id) is not int or epoch_id < 0:
        raise ValueError('invalid lease or epoch ID')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    payload = {'leaseId': lease_id, 'epochId': epoch_id, 'requestHash': request_hash.lower()}
    req = Request(url, data=json.dumps(payload).encode('utf-8'),
                  headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return {'kind': 'UNAVAILABLE', 'reason': 'http_non_200'}
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                return {'kind': 'INVALID', 'reason': 'oversized_http_response'}
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return {'kind': 'INVALID', 'reason': 'oversized_http_response'}
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != (set(payload) | {'responseHash', 'providerSignature'}):
            return {'kind': 'INVALID', 'reason': 'unsigned_or_invalid_schema'}
        if (data['leaseId'] != lease_id or type(data['leaseId']) is not int or
                data['epochId'] != epoch_id or type(data['epochId']) is not int or
                not isinstance(data['requestHash'], str) or
                data['requestHash'].lower() != request_hash.lower() or
                not isinstance(data['responseHash'], str) or
                data['responseHash'].lower() != expected_response_hash(request_hash)):
            return {'kind': 'INVALID', 'reason': 'wrong_challenge_response'}
        signed = {**payload, 'responseHash': expected_response_hash(request_hash)}
        if not verify_provider_response(domain, provider, signed, data['providerSignature']):
            return {'kind': 'INVALID', 'reason': 'invalid_provider_signature'}
        return {'kind': 'SUCCESS', 'reason': 'valid_provider_signature', 'response': data}
    except HTTPError:
        return {'kind': 'UNAVAILABLE', 'reason': 'http_error'}
    except (URLError, TimeoutError, OSError):
        return {'kind': 'UNAVAILABLE', 'reason': 'network_error_or_timeout'}
    except (ValueError, UnicodeDecodeError, TypeError, OverflowError):
        return {'kind': 'INVALID', 'reason': 'invalid_http_response'}
