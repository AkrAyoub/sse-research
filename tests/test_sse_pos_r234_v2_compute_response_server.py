"""R234 local actual HTTP-socket server unit tests; fake worker is test-only."""
from http.server import HTTPServer
from pathlib import Path
import importlib.util
import json
import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location(
    "v2_provider_server",ROOT/"services"/"provider-agent"/"v2_compute_response_server.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from compute_workload import compute_result
import sse_pos_r231_v2_compute_wire as wire
import sse_pos_r233_public_v2_compute_terms as terms
from sse_challenge import keccak256

MARKET="0x"+"11"*20
LEDGER="0x"+"22"*20
PROVIDER="0x"+"44"*20
HASH="0x"+"ab"*32
SIG="0x"+"11"*32+"22"*32+"1b"
PROFILE={
    "schema":terms.RESOURCE_SCHEMA,
    "serviceKind":"deterministic_compute","workloadSpec":terms.WORKLOAD,
    "origin":"https://provider.example.org",
    "dockerImageId":"sha256:"+"cc"*32,
    "cpuMilli":1000,"memoryBytes":128*2**20,
}
POLICY={
    "schema":terms.POLICY_SCHEMA,"chainId":31340,"market":MARKET,
    "resourceProfileHash":terms.resource_hash(PROFILE),
    "measuredFinalitySafetySeconds":2100,"confirmationSeconds":3600,
    "responseSeconds":3600,"monitoringSeconds":3600,
    "maxObservedLatencyMs":2000,"probeIntervalMs":2000,
    "minProbeCount":4,"minCorrectBps":9000,
    "timeoutTreatment":terms.TIMEOUT,
}

def snapshot():
    return {
        "schema":"SSE_R229_FINALIZED_V2_LEASE_READONLY_V1",
        "deploymentRuntimeAndWiringAttested":True,"chainId":31340,
        "market":MARKET,"ledger":LEDGER,"leaseId":1,"epochId":0,
        "lease":{"phase":4,"providerAccepted":True,"provider":PROVIDER,
                 "profileHash":terms.resource_hash(PROFILE),
                 "policyHash":terms.policy_hash(POLICY,PROFILE),
                 "endpointHash":"0x"+keccak256(PROFILE["origin"].encode()).hex()},
        "committee":{"ready":True},
        "epoch":{"market":{"exists":True,"requestHash":HASH},
                 "ledger":{"exists":True}},
    }

def signed():
    p=wire.payload_from_result(1,0,HASH,
            terms.resource_hash(PROFILE),
            terms.policy_hash(POLICY,PROFILE),
            compute_result(1,0,HASH))
    return {**p,"responseHash":wire.response_hash(p),"providerSignature":SIG}

def ready_context():
    return {"leaseId":1,"epochId":0,"requestHash":HASH,
            "profileHash":terms.resource_hash(PROFILE),
            "policyHash":terms.policy_hash(POLICY,PROFILE)}

class TestR234SourceOnlyRealHttpUnit(unittest.TestCase):
    def test_offline_verified_config_refuses_uncommitted_profile(self):
        snap=snapshot()
        with patch.object(mod,"validate_signed_reply",return_value={
                "providerPublicSignatureVerified":True,"responseHash":signed()["responseHash"]}):
            report=mod.verify_config(PROFILE,POLICY,signed(),snap)
        self.assertTrue(report["sourceManifestAndActualLeaseAttested"])
        self.assertFalse(report["localDockerInspectedOrStarted"])
        self.assertFalse(report["transactionSignedOrSubmitted"])
        with patch.object(mod,"validate_signed_reply",return_value={
                "providerPublicSignatureVerified":True,"responseHash":signed()["responseHash"]}):
            with self.assertRaises(mod.Refused):
                mod.verify_config(PROFILE,POLICY,signed(),{
                    **snap,"lease":{**snap["lease"],"profileHash":"0x"+"ff"*32}})

    def test_actual_http_loopback_only_invokes_worker_for_exact_request(self):
        invoked=[]
        def fake_worker(lease,epoch,request):
            invoked.append((lease,epoch,request))
            return compute_result(lease,epoch,request)
        server=mod.make_server(0,ready_context(),signed(),PROFILE,fake_worker)
        self.assertEqual(server.server_address[0],"127.0.0.1")
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url=f"http://127.0.0.1:{server.server_port}/v2/challenge"
            raw=json.dumps({"leaseId":1,"epochId":0,"requestHash":HASH}).encode()
            with urlopen(Request(url,data=raw,method="POST"),timeout=5) as response:
                self.assertEqual(response.status,200)
                reply=json.loads(response.read())
            self.assertEqual(reply["responseHash"],signed()["responseHash"])
            self.assertEqual(invoked,[(1,0,HASH)])
            with self.assertRaises(HTTPError) as ctx:
                urlopen(Request(url,data=b'{"leaseId":2,"epochId":0,"requestHash":"0x0"}',
                                method="POST"),timeout=5)
            self.assertEqual(ctx.exception.code,503)
            self.assertEqual(len(invoked),1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_worker_failure_does_not_release_signed_reply(self):
        def fail_worker(*_):
            raise mod.Refused("actual worker unavailable")
        server=mod.make_server(0,ready_context(),signed(),PROFILE,fail_worker)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url=f"http://127.0.0.1:{server.server_port}/v2/challenge"
            req=Request(url,data=json.dumps({
                "leaseId":1,"epochId":0,"requestHash":HASH
            }).encode(),method="POST")
            with self.assertRaises(HTTPError) as err:
                urlopen(req,timeout=5)
            self.assertEqual(err.exception.code,503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_docker_runner_does_not_launch_any_container(self):
        with patch.object(mod,"inspect_container",return_value={
            "runtimeReportedRunning":True
        }) as inspect,patch.object(mod,"run_compute_probe",return_value={
            "workloadResultVerified":True,
            "resultDigest":compute_result(1,0,HASH)["resultDigest"],
            "rounds":8192
        }) as probe:
            worker=mod.make_docker_executor(PROFILE,
                        "http://127.0.0.1:8877","sse-compute-real1")
            result=worker(1,0,HASH)
        self.assertEqual(result["rounds"],8192)
        self.assertTrue(inspect.call_args.kwargs["strict_hardening"])
        self.assertEqual(probe.call_count,1)

    def test_bad_unauthenticated_container_or_port_refused(self):
        with self.assertRaises(mod.Refused):
            mod.make_docker_executor(PROFILE,
                        "http://127.0.0.1:8877","bad")
        with self.assertRaises(mod.ComputeError):
            mod.make_docker_executor(PROFILE,
                        "https://example.org","sse-compute-real1")

if __name__=="__main__":
    unittest.main()
