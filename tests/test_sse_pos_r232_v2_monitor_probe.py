"""R232 genuine local HTTP-socket probe tests; NOT physical SLA verification."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r232_v2_monitor_probe as m
import sse_pos_r231_v2_compute_wire as wire
from compute_workload import compute_result
from sse_challenge import keccak256

MONITOR="0x"+"33"*20
PROVIDER="0x"+"44"*20
MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
HASH="0x"+"ab"*32
PROFILE="0x"+"cd"*32
POLICY="0x"+"ef"*32
SIG="0x"+"11"*32+"22"*32+"1b"

def snapshot(origin):
    return {
        "schema":"SSE_R229_FINALIZED_V2_LEASE_READONLY_V1",
        "deploymentRuntimeAndWiringAttested":True,
        "chainId":31340,"market":MARKET,"ledger":LEDGER,
        "leaseId":1,"epochId":0,
        "finalizedExecutionHeight":101,
        "lease":{"consumer":"0x"+"55"*20,"provider":PROVIDER,
                 "profileHash":PROFILE,"policyHash":POLICY,
                 "providerAccepted":True,"phase":4,
                 "endpointHash":"0x"+keccak256(origin.encode()).hex()},
        "committee":{"ready":True},
        "selectedMonitors":[MONITOR],
        "epoch":{"market":{"exists":True,"requestHash":HASH},
                 "ledger":{"exists":True,"monitoringSealed":False}},
    }

def signed_response():
    p=wire.payload_from_result(1,0,HASH,PROFILE,POLICY,compute_result(1,0,HASH))
    return {**p,"responseHash":wire.response_hash(p),"providerSignature":SIG}

class TestR232ActualBoundedMonitorTransport(unittest.TestCase):
    def test_reject_wrong_uncommitted_or_http_internet_origin(self):
        for bad in ("http://example.org","https://example.org/path",
                    "https://user:pass@example.org","https://EXAMPLE.org",
                    "https://example.org/","https://example.org?x=1"):
            with self.subTest(bad=bad),self.assertRaises(m.Refused):
                m.canonical_origin(bad)
        self.assertEqual(m.canonical_origin("https://provider.example.org"),
                         "https://provider.example.org")
        self.assertEqual(m.canonical_origin("http://127.0.0.1:8877"),
                         "http://127.0.0.1:8877")
        with self.assertRaises(m.Refused):
            m.prepared_monitor(snapshot("https://provider.example.org"),
                               MONITOR,"https://evil.example.org")

    def test_selected_monitor_must_be_confirmed_on_chain(self):
        origin="https://provider.example.org"
        s=snapshot(origin)
        fake=lambda url,method,args:"0x"+(1).to_bytes(32,"big").hex()
        with patch.object(m,"eth_call",side_effect=lambda *a,**kw:fake(*a)):
            context=m.prepared_monitor(s,MONITOR,origin,
                         rpc_url="http://127.0.0.1:28545")
        self.assertTrue(context["confirmedMonitorAtFinalized"])
        with patch.object(m,"eth_call",return_value="0x"+"00"*32):
            with self.assertRaises(m.Refused):
                m.prepared_monitor(s,MONITOR,origin,
                         rpc_url="http://127.0.0.1:28545")
        with self.assertRaises(m.Refused):
            m.prepared_monitor(s,PROVIDER,origin)

    def test_actual_local_http_request_reads_bounded_signed_response(self):
        original=signed_response()
        raw=json.dumps(original,sort_keys=True).encode()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.received_path=self.path
                incoming=self.rfile.read(int(self.headers["Content-Length"]))
                self.server.received=json.loads(incoming)
                self.send_response(200)
                self.send_header("Content-Length",str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self,*a):
                pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            origin="http://127.0.0.1:"+str(server.server_port)
            s=snapshot(origin)
            context=m.prepared_monitor(s,MONITOR,origin)
            result=m.http_probe(origin,{k:context[k] for k in (
                "leaseId","epochId","requestHash")})
            self.assertEqual(result["transportStatus"],"HTTP_RESPONSE_OBSERVED")
            self.assertEqual(server.received_path,"/v2/challenge")
            self.assertEqual(server.received,{
                "leaseId":1,"epochId":0,"requestHash":HASH})
            with patch.object(wire,"verify_public_signer",return_value=True):
                observed=m.inspect_response(result,s,context)
            self.assertTrue(observed["providerSignatureVerified"])
            self.assertFalse(observed["physicalSlaTruthVerified"])
            self.assertFalse(observed["onChainVoteOrFailureVerdict"])
            self.assertRegex(observed["provisionalMonitorEvidenceHash"],
                             r"^0x[0-9a-f]{64}$")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_transport_unavailable_does_not_become_sla_failure(self):
        origin="http://127.0.0.1:8899"
        s=snapshot(origin)
        context=m.prepared_monitor(s,MONITOR,origin)
        observation={"body":None,"transportStatus":"UNAVAILABLE_OR_ERROR",
                     "httpStatus":None,"elapsedMs":10}
        summary=m.inspect_response(observation,s,context)
        self.assertFalse(summary["providerSignatureVerified"])
        self.assertFalse(summary["onChainVoteOrFailureVerdict"])
        self.assertTrue(summary["provisionalOnly"])

    def test_incorrect_public_signature_and_malformed_body_refused(self):
        origin="https://provider.example.org"
        s=snapshot(origin)
        context=m.prepared_monitor(s,MONITOR,origin)
        result={"body":json.dumps(signed_response()).encode(),
                "transportStatus":"HTTP_RESPONSE_OBSERVED",
                "httpStatus":200,"elapsedMs":10}
        with patch.object(wire,"verify_public_signer",return_value=False):
            with self.assertRaises(wire.Refused):
                m.inspect_response(result,s,context)
        result["body"]=b'{"a":1,"a":2}'
        with self.assertRaises(m.Refused):
            m.inspect_response(result,s,context)

    def test_private_evidence_file_create_only(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"proof.json"
            m.write_create_only(str(path),{"test":1})
            self.assertEqual(json.loads(path.read_text()),{"test":1})
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaises(m.Refused):
                m.write_create_only(str(path),{"test":2})

if __name__=="__main__":
    unittest.main()
