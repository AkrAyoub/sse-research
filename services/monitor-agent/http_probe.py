"""Observe real localhost HTTP responses until a local deadline.

Output is UNSIGNED, OFF-CHAIN diagnostic evidence, not an on-chain monitor vote.
Chain timestamps, lease binding, provider signature, and real compute attestations
are future integration steps.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from sse_challenge import bytes32, expected_response_hash


def _probe(endpoint: str, lease_id: int, epoch_id: int, request_hash: str, timeout: float) -> tuple[bool, str]:
    payload = json.dumps({"leaseId": lease_id, "epochId": epoch_id, "requestHash": request_hash}).encode("utf-8")
    req = Request(endpoint.rstrip("/") + "/v1/challenge", data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as reply:
            if reply.status != 200:
                return False, f"http_{reply.status}"
            claimed_size = reply.headers.get("Content-Length")
            if claimed_size is not None and int(claimed_size) > 2048:
                return False, "oversized_response"
            body = reply.read(2049)
        if len(body) > 2048:
            return False, "oversized_response"
        data = json.loads(body)
        expected = {"leaseId": lease_id, "epochId": epoch_id,
                    "requestHash": request_hash.lower(),
                    "responseHash": expected_response_hash(request_hash)}
        return (True, "valid_challenge_response") if data == expected else (False, "mismatched_response")
    except HTTPError as exc:
        return False, f"http_{exc.code}"
    except (URLError, TimeoutError, OSError):
        return False, "network_error_or_timeout"
    except (ValueError, UnicodeDecodeError):
        return False, "invalid_json_response"


def observe(endpoint: str, lease_id: int, epoch_id: int, request_hash: str,
            duration: float = 5.0, interval: float = 0.25, timeout: float = 0.5) -> dict:
    """Probe until a correct response or deadline. Return unsigned observation JSON."""
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("first-stage probe only permits http://127.0.0.1:PORT")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid port") from exc
    if port is None or not 1 <= port <= 65535:
        raise ValueError("endpoint needs a valid explicit port")
    if type(lease_id) is not int or lease_id < 1 or type(epoch_id) is not int or epoch_id < 0:
        raise ValueError("invalid lease or epoch")
    bytes32(request_hash)
    if duration <= 0 or interval <= 0 or timeout <= 0 or duration > 600:
        raise ValueError("duration, interval and timeout must be positive; duration <= 600")
    start = time.time()
    deadline = time.monotonic() + duration
    attempts = []
    outcome = "FAILURE_OBSERVED"
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        good, reason = _probe(endpoint, lease_id, epoch_id, request_hash, min(timeout, remaining))
        attempts.append({"atLocalUnixTime": time.time(), "reason": reason})
        if good and time.monotonic() <= deadline:
            outcome = "SUCCESS_OBSERVED"
            break
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    if not attempts:
        raise RuntimeError("no probes occurred: cannot report failure")
    return {"schema": "sse-http-observation-v1", "leaseId": lease_id,
            "epochId": epoch_id, "requestHash": request_hash.lower(),
            "expectedResponseHash": expected_response_hash(request_hash),
            "endpoint": endpoint, "outcome": outcome, "startedAtLocalUnixTime": start,
            "finishedAtLocalUnixTime": time.time(), "attempts": attempts,
            "signed": False, "chainLeaseVerified": False, "chainDeadlineVerified": False,
            "providerSignatureVerified": False, "clockAttested": False,
            "computeProvisioningVerified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a local SSE HTTP provider service")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8877")
    parser.add_argument("--lease-id", type=int, required=True)
    parser.add_argument("--epoch-id", type=int, required=True)
    parser.add_argument("--request-hash", required=True)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--output", help="Optional JSON result file (outside the repository recommended)")
    args = parser.parse_args()
    result = observe(args.endpoint, args.lease_id, args.epoch_id,
                     args.request_hash, duration=args.duration)
    formatted = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(formatted + "\n", encoding="utf-8")
        print(f"Saved {result['outcome']} observation to {args.output}")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
