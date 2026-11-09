"""Local-only HTTP challenge responder for SSE protocol integration testing.

This service performs deterministic challenge work; it does not provision compute,
verify a lease against chain state, sign messages, or prove provider identity.
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from sse_challenge import bytes32, expected_response_hash

MAX_BODY = 2048


def make_server(port: int = 8877) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise ValueError("invalid port")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, data: dict) -> None:
            payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path != "/healthz":
                return self._json(404, {"error": "not found"})
            return self._json(200, {"ok": True, "service": "sse-local-challenge", "onChainAuthenticated": False})

        def do_POST(self) -> None:
            if self.path != "/v1/challenge":
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_BODY:
                    raise ValueError("invalid body length")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {"leaseId", "epochId", "requestHash"}:
                    raise ValueError("unexpected request fields")
                if type(data["leaseId"]) is not int or data["leaseId"] < 1:
                    raise ValueError("invalid leaseId")
                if type(data["epochId"]) is not int or data["epochId"] < 0:
                    raise ValueError("invalid epochId")
                bytes32(data["requestHash"])
            except (ValueError, TypeError, UnicodeDecodeError, OverflowError):
                return self._json(400, {"error": "invalid challenge"})
            return self._json(200, {
                "leaseId": data["leaseId"],
                "epochId": data["epochId"],
                "requestHash": data["requestHash"].lower(),
                "responseHash": expected_response_hash(data["requestHash"]),
            })

        def log_message(self, format: str, *args: object) -> None:
            return  # Avoid logging request identifiers by default.

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local SSE HTTP challenge responder")
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"SSE challenge service: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
