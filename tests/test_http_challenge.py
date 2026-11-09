"""Real localhost HTTP tests for challenge responder and unsigned monitor observations."""

import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def load(relative_path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


challenge = load("tools/sse_challenge.py", "sse_challenge")
provider = load("services/provider-agent/http_service.py", "sse_http_provider")
monitor = load("services/monitor-agent/http_probe.py", "sse_http_monitor")


class HttpChallengeTest(unittest.TestCase):
    def setUp(self):
        self.server = provider.make_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.hash = "0x" + "11" * 32

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def test_keccak_abi_matches_known_vector(self):
        self.assertEqual(challenge.RESPONSE_LABEL.hex(), "4a483b689aaab909e4ab5877380e0a40ceed6cd31474d580495aa38fa6ac5c40")
        self.assertEqual(challenge.expected_response_hash(self.hash), "0x6e8a28e946d2b94dba06a1751c03ccb0f8f002d99df49bc7dced7fea74953ad7")

    def test_real_provider_response(self):
        payload = json.dumps({"leaseId": 1, "epochId": 0, "requestHash": self.hash}).encode()
        with urlopen(Request(self.endpoint + "/v1/challenge", payload,
                             {"Content-Type": "application/json"}), timeout=3) as reply:
            body = json.load(reply)
        self.assertEqual(body["responseHash"], challenge.expected_response_hash(self.hash))
        self.assertEqual(body["leaseId"], 1)

    def test_real_monitor_detects_success(self):
        evidence = monitor.observe(self.endpoint, 1, 0, self.hash, duration=0.5)
        self.assertEqual(evidence["outcome"], "SUCCESS_OBSERVED")
        self.assertFalse(evidence["signed"])
        self.assertFalse(evidence["providerSignatureVerified"])
        self.assertGreaterEqual(len(evidence["attempts"]), 1)

    def test_invalid_challenge_rejected(self):
        payload = json.dumps({"leaseId": True, "epochId": 0,
                              "requestHash": self.hash}).encode()
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.endpoint + "/v1/challenge", payload), timeout=3)
        self.assertEqual(ctx.exception.code, 400)

    def test_monitor_reports_failures_only_after_deadline(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        evidence = monitor.observe(self.endpoint, 1, 0, self.hash,
                                   duration=0.15, interval=0.02, timeout=0.02)
        self.assertEqual(evidence["outcome"], "FAILURE_OBSERVED")
        self.assertFalse(evidence["clockAttested"])
        self.assertGreaterEqual(len(evidence["attempts"]), 1)

    def test_external_endpoint_forbidden_for_local_stage(self):
        with self.assertRaises(ValueError):
            monitor.observe("http://example.com:8877", 1, 0, self.hash)


if __name__ == "__main__":
    unittest.main()
