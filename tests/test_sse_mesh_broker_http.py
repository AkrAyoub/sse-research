"""Offline contract tests: genuine broker client shape, replay and errors; no WAN calls."""
import io
from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_mesh_broker import issue_token
from sse_mesh_broker_http import EnrollmentApp


def request(app, body, *, method="POST", content_type="application/json",
            path="/v1/mesh/enroll"):
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    status = []
    headers = []
    def start(s, h):
        status.append(s)
        headers.extend(h)
    env = {
        "PATH_INFO": path,
        "REQUEST_METHOD": method,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(data)),
        "wsgi.input": io.BytesIO(data),
    }
    result = b"".join(app(env, start))
    return status[0], dict(headers), json.loads(result)


class EnrollmentEndpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dbpath = Path(self.directory.name) / "enroll.sqlite"
        self.minted = []
        def mint(client_id, client_secret, *, tailnet):
            self.minted.append((client_id, tailnet))
            return "tskey-auth-fixture-no-network"
        self.app = EnrollmentApp(self.dbpath, "id", "private", "-", mint=mint)
        with closing(sqlite3.connect(self.dbpath, isolation_level=None)) as db:
            self.token = issue_token(db, "provider-a", "provider,monitor")
        self.valid = {"node_id": "provider-a", "roles": "provider,monitor",
                      "enrollment_token": self.token}

    def test_redeem_exact_client_contract_once(self):
        code, headers, body = request(self.app, self.valid)
        self.assertEqual(code, "200 OK")
        self.assertEqual(body["rolesConfigured"], ["provider", "monitor"])
        self.assertEqual(body["nodeId"], "provider-a")
        self.assertEqual(body["expiresInSeconds"], 300)
        self.assertEqual(self.minted, [("id", "-")])
        self.assertEqual(headers["Cache-Control"], "no-store")
        code, _, body = request(self.app, self.valid)
        self.assertEqual(code, "403 Forbidden")
        self.assertNotIn(self.token, str(body))
        self.assertEqual(len(self.minted), 1)

    def test_wrong_node_and_role_do_not_consume(self):
        wrong = {**self.valid, "node_id": "provider-b"}
        self.assertEqual(request(self.app, wrong)[0], "403 Forbidden")
        wrong = {**self.valid, "roles": "monitor,provider"}
        self.assertEqual(request(self.app, wrong)[0], "403 Forbidden")
        self.assertEqual(request(self.app, self.valid)[0], "200 OK")

    def test_bad_input_fails_without_mint(self):
        for data in [
            b'{"node_id":"x","node_id":"y","roles":"provider","enrollment_token":"z"}',
            b'[]', b'{}', b'{',
            {**self.valid, "secret": "unexpected"},
            {**self.valid, "enrollment_token": 7},
        ]:
            with self.subTest(body=data):
                self.assertEqual(request(self.app, data)[0], "403 Forbidden")
        self.assertEqual(self.minted, [])

    def test_cannot_read_without_post_or_path(self):
        self.assertEqual(request(self.app, self.valid, method="GET")[0], "405 Method Not Allowed")
        self.assertEqual(request(self.app, self.valid, path="/admin")[0], "404 Not Found")
        self.assertEqual(request(self.app, self.valid, content_type="text/plain")[0],
                         "415 Unsupported Media Type")
        self.assertEqual(self.minted, [])

    def test_health_never_activates_wallet(self):
        status, _, result = request(self.app, {}, method="GET", path="/healthz")
        self.assertEqual(status, "200 OK")
        self.assertFalse(result["ethereumTransactionsSent"])

    def test_upstream_failure_burns_token(self):
        def down(*a, **k):
            raise ValueError("upstream failure")
        self.app.mint = down
        self.assertEqual(request(self.app, self.valid)[0], "403 Forbidden")
        self.assertEqual(request(self.app, self.valid)[0], "403 Forbidden")


if __name__ == "__main__":
    unittest.main()
