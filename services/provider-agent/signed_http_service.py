"""Local laboratory provider that signs V1 ProviderResponse for ONE pinned challenge.

Not a chain-verified lease provider; never bind to a remote interface or use a
funded production key. Secret is read from SSE_WP08B_PROVIDER_KEY environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'services' / 'monitor-agent'))

from sse_challenge import bytes32, expected_response_hash
from typed_evidence import Domain, typed_message

MAX_BODY = 2048


def _unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate request field')
        out[k] = v
    return out


def make_server(port: int, private_key: str, domain: Domain, lease_id: int,
                epoch_id: int, request_hash: str) -> ThreadingHTTPServer:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('invalid listening port')
    if not isinstance(domain, Domain):
        raise ValueError('expected SSESettlement EIP-712 domain')
    if type(lease_id) is not int or not 1 <= lease_id < 2**256:
        raise ValueError('invalid pinned lease ID')
    if type(epoch_id) is not int or not 0 <= epoch_id < 2**256:
        raise ValueError('invalid pinned epoch ID')
    bytes32(request_hash)
    if request_hash.lower() != request_hash:
        raise ValueError('request commitment must be canonical lowercase')
    account = Account.from_key(private_key)
    response_hash = expected_response_hash(request_hash)
    expected = {'leaseId': lease_id, 'epochId': epoch_id, 'requestHash': request_hash}
    signed_data = {**expected, 'responseHash': response_hash}
    signed = Account.sign_message(
        encode_typed_data(full_message=typed_message(domain, 'ProviderResponse', signed_data)),
        private_key=private_key)
    prepared = {**signed_data, 'providerSignature': '0x' + bytes(signed.signature).hex()}

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status, body):
            raw = json.dumps(body, sort_keys=True, separators=(',', ':')).encode('ascii')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path != '/healthz':
                return self._json(404, {'error':'not found'})
            return self._json(200, {'ok': True, 'signsProviderResponse': True,
                                    'chainLeaseVerified': False, 'experimental': True})

        def do_POST(self):
            if self.path != '/v1/challenge':
                return self._json(404, {'error':'not found'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 1 <= length <= MAX_BODY:
                    raise ValueError('bad length')
                self.connection.settimeout(5.0)  # bound incomplete local request bodies
                raw = self.rfile.read(length)
                data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs)
                if (type(data) is not dict or set(data) != set(expected) or
                        type(data['leaseId']) is not int or
                        type(data['epochId']) is not int or data != expected):
                    raise ValueError('not the pinned challenge')
            except (ValueError, UnicodeDecodeError, TypeError, OverflowError, OSError):
                return self._json(400, {'error':'invalid or unbound challenge'})
            return self._json(200, prepared)

        def log_message(self, fmt, *args):
            return  # Never log challenge material or keys by default.

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.provider_address = account.address.lower()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description='WP08B localhost-only V1 signed response provider')
    parser.add_argument('--port', type=int, default=8878)
    parser.add_argument('--chain-id', type=int, required=True)
    parser.add_argument('--settlement', required=True)
    parser.add_argument('--lease-id', type=int, required=True)
    parser.add_argument('--epoch-id', type=int, required=True)
    parser.add_argument('--request-hash', required=True)
    args = parser.parse_args()
    private_key = os.environ.get('SSE_WP08B_PROVIDER_KEY')
    if not private_key:
        parser.error('set SSE_WP08B_PROVIDER_KEY (testing key only)')
    server = make_server(args.port, private_key, Domain(args.chain_id, args.settlement),
                         args.lease_id, args.epoch_id, args.request_hash)
    print(f'WP08B signed responder on http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
