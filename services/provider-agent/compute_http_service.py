"""Local Docker CPU worker: SSE challenge + actual deterministic CPU workload.

Runs in an isolated, resource-limited Docker container, but this HTTP result
is NOT a trusted cloud-hardware or performance attestation.
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from sse_challenge import bytes32, expected_response_hash
from compute_workload import compute_result

MAX_BODY = 2048


def make_server(port: int = 8877) -> ThreadingHTTPServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('invalid port')

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict):
            data = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != '/healthz':
                return self._json(404, {'error': 'not found'})
            return self._json(200, {'ok': True, 'service': 'sse-local-challenge',
                                   'onChainAuthenticated': False, 'localComputeWorker': True})

        def do_POST(self):
            if self.path not in ('/v1/challenge', '/v1/compute'):
                return self._json(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= MAX_BODY:
                    raise ValueError('invalid length')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {'leaseId','epochId','requestHash'}:
                    raise ValueError('invalid fields')
                lease_id, epoch_id, challenge = data['leaseId'], data['epochId'], data['requestHash']
                if type(lease_id) is not int or not 1 <= lease_id < 2**256:
                    raise ValueError('invalid leaseId')
                if type(epoch_id) is not int or not 0 <= epoch_id < 2**256:
                    raise ValueError('invalid epochId')
                bytes32(challenge)
                if self.path == '/v1/compute':
                    return self._json(200, compute_result(lease_id, epoch_id, challenge))
                return self._json(200, {'leaseId': lease_id, 'epochId': epoch_id,
                                        'requestHash': challenge.lower(),
                                        'responseHash': expected_response_hash(challenge)})
            except (ValueError, OverflowError, TypeError, UnicodeDecodeError):
                return self._json(400, {'error': 'invalid request'})

        def log_message(self, fmt, *args):
            return

    return ThreadingHTTPServer(('0.0.0.0', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Run SSE local Docker CPU worker')
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'SSE compute worker ready on :{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
