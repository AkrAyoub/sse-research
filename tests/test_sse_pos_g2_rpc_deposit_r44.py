"""R44: real Docker bounded multi-chunk HTTP and deposit JSON-RPC error diagnosis."""
import json
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sse_pos_g2_rpc_deposit_r44 as m
from sse_pos_deposit_predeploy import standard_reference

def http(body: bytes, *, chunks: tuple[int, ...] | None = None):
    if chunks is None:
        return (
            b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
            + b"\r\n\r\n" + body
        )
    raw = bytearray(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
    offset = 0
    for size in chunks:
        part = body[offset:offset + size]
        if not part:
            break
        raw.extend(format(len(part), "x").encode() + b"\r\n" + part + b"\r\n")
        offset += len(part)
    if offset < len(body):
        part = body[offset:]
        raw.extend(format(len(part), "x").encode() + b"\r\n" + part + b"\r\n")
    raw.extend(b"0\r\n\r\n")
    return bytes(raw)

class R44RealDepositReadOnlyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = standard_reference()["code"]
        cls.bytes = bytes.fromhex(cls.code[2:])
        cls.payload = json.dumps({"jsonrpc":"2.0","id":1,"result":cls.code}).encode()

    def test_genuine_public_reference_length_and_hash(self):
        self.assertEqual(len(self.bytes), 6358)
        self.assertEqual(m.hashlib.sha256(self.bytes).hexdigest(), m.health.CODE_SHA)

    def test_http_content_length_large_code_parses_without_truncation(self):
        meta, result = m.unpack_http(http(self.payload))
        self.assertEqual(meta["transportStatus"], "HTTP_200_JSON_OBJECT")
        self.assertFalse(meta["isChunked"])
        self.assertEqual(result["result"], self.code)

    def test_multi_chunked_large_code_reassembles_all_chunks(self):
        wire = http(self.payload, chunks=(17, 101, 4096, 2078, 3500, 800))
        meta, result = m.unpack_http(wire)
        self.assertEqual(meta["transportStatus"], "HTTP_200_JSON_OBJECT")
        self.assertTrue(meta["isChunked"])
        self.assertGreaterEqual(meta["chunkCount"], 2)
        self.assertEqual(result["result"], self.code)

    def test_incomplete_chunked_response_refused(self):
        raw = http(self.payload, chunks=(17, 109, 3000))
        raw = raw[:500]
        meta, result = m.unpack_http(raw)
        self.assertIsNone(result)
        self.assertNotEqual(meta["transportStatus"], "HTTP_200_JSON_OBJECT")

    def test_json_rpc_error_emits_numeric_code_only(self):
        response = http(json.dumps({
            "jsonrpc":"2.0","id":1,
            "error":{"code":-32601,"message":"SECRET_DO_NOT_EXPOSE"}
        }).encode())
        with patch.object(m.health.internal, "docker", return_value=response):
            report = m.code_report("latest", self.bytes)
        self.assertEqual(report["jsonRpcResultCategory"], "JSON_RPC_ERROR")
        self.assertEqual(report["jsonRpcNumericErrorCode"], -32601)
        self.assertNotIn("SECRET_DO_NOT_EXPOSE", str(report))

    def test_actual_large_multi_chunk_code_matches_pinned_bytes(self):
        response = http(self.payload, chunks=(1024, 1800, 1111, 3333, 2212))
        with patch.object(m.health.internal, "docker", return_value=response):
            report = m.code_report("earliest", self.bytes)
        self.assertEqual(report["jsonRpcResultCategory"], "BYTECODE_RESULT")
        self.assertEqual(report["publicRuntimeBytes"], 6358)
        self.assertTrue(report["matchesPinnedStandardUngatedEthereumDepositRuntime"])
        self.assertFalse(report["rawRpcBytesBytecodeOrErrorMessagesEmitted"])

    def test_empty_live_code_detected_not_misreported_as_success(self):
        response = http(b'{"jsonrpc":"2.0","id":1,"result":"0x"}')
        with patch.object(m.health.internal, "docker", return_value=response):
            report = m.code_report("latest", self.bytes)
        self.assertEqual(report["jsonRpcResultCategory"], "EMPTY_BYTECODE")
        self.assertFalse(report["matchesPinnedStandardUngatedEthereumDepositRuntime"])

    def test_only_actual_chain31340_and_stopped_original_el(self):
        with patch.object(m.health, "require_actual_source"):
            states = lambda name: {"Running": name != m.ORIGINAL}
            with patch.object(m.health.internal, "state", side_effect=states):
                with patch.object(m.health, "rpc", return_value="0x1"):
                    with self.assertRaisesRegex(m.R44ReadOnlyError, "31340"):
                        m.observe("a"*40)

    def test_source_never_starts_signer_or_changes_any_files(self):
        code = (ROOT / "tools/sse_pos_g2_rpc_deposit_r44.py").read_text("utf-8")
        for token in ('"start"', '"run"', '"restart"', '"stop"', '"rm"', '"kill"',
                      "wallet create", "mnemonic"):
            self.assertNotIn(token, code)
        self.assertIn('("earliest", "latest")', code)
        self.assertIn('["exec", EL, "/bin/bash", "-c", request]', code)

if __name__ == "__main__":
    main()
