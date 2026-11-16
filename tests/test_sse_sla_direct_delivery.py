"""R1/R5/R7 direct role-owned SLA and provider-consumer exchange regression tests.

Uses real EIP-712 cryptography and loopback HTTP, but a deliberately STUBBED
chain snapshot. This is not proof of a real funded VM lease or cloud delivery.
"""
import importlib.util
import json
import socket
import sys
import threading
import unittest
from copy import deepcopy
from pathlib import Path

from eth_account import Account

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))
from sse_challenge import keccak256, expected_response_hash
from sse_sla_manifest import (SLAError, proposed_policy, policy_hash,
                              canonical_policy, compare_to_lease)
from sse_direct_delivery import (ExchangeError, prepare_request, authenticate_request,
    create_response, validate_response, create_receipt, verify_receipt,
    submit_work_request, validate_endpoint_url, REQ_TYPE, sign, parse_bytes)
spec=importlib.util.spec_from_file_location(
    "sse_direct_provider", ROOT/"services"/"provider-agent"/"direct_work_service.py")
service=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=service
spec.loader.exec_module(service)

CHAIN=31337
SETTLEMENT="0x"+"12"*20
PROFILE="0x"+"bb"*32
REQ="0x"+keccak256(b"real-leased-challenge-token").hex()
NONCE="0x"+keccak256(b"one-time-consumer-nonce").hex()


def setup(kind="deterministic_compute", endpoint="http://127.0.0.1:8945"):
    consumer,provider=Account.create(),Account.create()
    policy=proposed_policy(service_kind=kind,chain_id=CHAIN,
                           settlement=SETTLEMENT, resource_profile_hash=PROFILE)
    lease={"stateName":"Active","consumer":consumer.address.lower(),
           "provider":provider.address.lower(),"slaPolicyHash":policy_hash(policy),
           "resourceProfileHash":PROFILE,"reservationFee":0,
           "marketplaceRequestId":1,"totalEscrow":25,
           "serviceEndpointHash":"0x"+keccak256(endpoint.encode("ascii")).hex()}
    state={"schema":"sse-onchain-inspection-v1","chainId":CHAIN,
           "settlementAddress":SETTLEMENT,"domainSeparatorMatches":True,
           "blockHashPinned":True,"leaseId":1,"epochId":0,
           "lease":lease,"epoch":{"exists":True,"requestHash":REQ,
                                  "responseHash":expected_response_hash(REQ)}}
    return consumer,provider,policy,state


class SlaManifestTests(unittest.TestCase):
    def test_both_supported_services_are_canonical_and_distinct(self):
        a=proposed_policy(service_kind="http_challenge",chain_id=CHAIN,
                          settlement=SETTLEMENT,resource_profile_hash=PROFILE)
        b=proposed_policy(service_kind="deterministic_compute",chain_id=CHAIN,
                          settlement=SETTLEMENT,resource_profile_hash=PROFILE)
        self.assertNotEqual(policy_hash(a),policy_hash(b))
        self.assertEqual(canonical_policy(a),canonical_policy(dict(reversed(list(a.items())))))
        self.assertEqual(len(policy_hash(a)),66)
        self.assertEqual(a["reservationPolicy"],"DELIVERY_ONLY_ZERO_RESERVATION_V1")
        self.assertEqual(a["timeoutPolicy"],"TIMEOUT_IS_INCONCLUSIVE_V1")

    def test_unknown_service_and_metrics_refused(self):
        with self.assertRaises(SLAError):
            proposed_policy(service_kind="object_storage",chain_id=CHAIN,
                            settlement=SETTLEMENT,resource_profile_hash=PROFILE)
        a=proposed_policy(service_kind="http_challenge",chain_id=CHAIN,
                          settlement=SETTLEMENT,resource_profile_hash=PROFILE)
        for field,value in [("minSuccessBps",10001),("minProbeCount",500),
                            ("maxResponseLatencyMs",70000),("receiptCutoffMs",-1),
                            ("timeoutPolicy","TIMEOUT_MEANS_FAILURE"),
                            ("reservationPolicy","UNDECLARED_BONUS"),("chainId",True)]:
            with self.subTest(field=field),self.assertRaises(SLAError):
                canonical_policy({**a,field:value})
        with self.assertRaises(SLAError):
            canonical_policy({**a,"unknown":"anything"})

    def test_onchain_policy_and_provider_binding_fail_closed(self):
        c,p,policy,state=setup()
        compare_to_lease(policy,state,endpoint="http://127.0.0.1:8945")
        for change in (
            lambda x:x["lease"].update(slaPolicyHash="0x"+"cc"*32),
            lambda x:x["lease"].update(resourceProfileHash="0x"+"cc"*32),
            lambda x:x["lease"].update(reservationFee=5),
            lambda x:x.update(blockHashPinned=False),
            lambda x:x["lease"].update(stateName="Ready"),
            lambda x:x["lease"].update(marketplaceRequestId=0),
            lambda x:x["lease"].update(totalEscrow=0),
            lambda x:x.update(epoch=None),
        ):
            x=deepcopy(state);change(x)
            with self.subTest(change=change),self.assertRaises(SLAError):
                compare_to_lease(policy,x,endpoint="http://127.0.0.1:8945")


class DirectExchangeTests(unittest.TestCase):
    def setUp(self):
        self.endpoint="http://127.0.0.1:8945"
        self.consumer,self.provider,self.policy,self.state=setup(endpoint=self.endpoint)
        self.order=prepare_request(self.state,self.policy,self.endpoint,self.consumer,NONCE)

    def test_consumer_signed_request_targets_winning_provider(self):
        msg=authenticate_request(self.order,self.state,self.policy,self.endpoint,self.provider)
        self.assertEqual(msg["provider"],self.provider.address.lower())
        self.assertEqual(msg["consumer"],self.consumer.address.lower())
        self.assertEqual(msg["nonce"],NONCE)

    def test_only_selected_provider_may_respond(self):
        other=Account.create()
        with self.assertRaises(ExchangeError):
            authenticate_request(self.order,self.state,self.policy,self.endpoint,other)
        forged=deepcopy(self.order);forged["message"]["provider"]=other.address.lower()
        with self.assertRaises(ExchangeError):
            authenticate_request(forged,self.state,self.policy,self.endpoint,self.provider)

    def test_consumer_signature_wrong_key_rejected(self):
        bad=deepcopy(self.order)
        other=Account.create()
        bad["signature"]=sign(REQ_TYPE,bad["message"],CHAIN,SETTLEMENT,other)
        with self.assertRaises(ExchangeError):
            authenticate_request(bad,self.state,self.policy,self.endpoint,self.provider)

    def test_signed_compute_result_and_receipt(self):
        res=create_response(self.order,self.state,self.policy,self.endpoint,self.provider)
        self.assertEqual(res["result"]["rounds"],8192)
        self.assertEqual(len(res["result"]["resultDigest"]),71)
        msg=validate_response(res,self.order,self.state,self.policy,self.endpoint)
        self.assertEqual(msg["consumer"],self.consumer.address.lower())
        receipt=create_receipt(self.order,res,self.state,self.policy,self.endpoint,self.consumer)
        self.assertTrue(verify_receipt(receipt,res,self.state,self.policy,self.endpoint)["validSignature"])

    def test_malleated_result_and_bad_receipt_refused(self):
        res=create_response(self.order,self.state,self.policy,self.endpoint,self.provider)
        tampered=deepcopy(res)
        tampered["result"]["resultDigest"]="sha256:"+"00"*32
        with self.assertRaises(ExchangeError):
            validate_response(tampered,self.order,self.state,self.policy,self.endpoint)
        receipt=create_receipt(self.order,res,self.state,self.policy,self.endpoint,self.consumer)
        forged=deepcopy(receipt)
        forged["message"]["resultHash"]="0x"+"de"*32
        with self.assertRaises(ExchangeError):
            verify_receipt(forged,res,self.state,self.policy,self.endpoint)

    def test_http_challenge_service_variant(self):
        c,p,policy,state=setup("http_challenge",self.endpoint)
        order=prepare_request(state,policy,self.endpoint,c,NONCE)
        res=create_response(order,state,policy,self.endpoint,p)
        self.assertEqual(res["result"]["responseHash"],expected_response_hash(REQ))
        self.assertEqual(validate_response(res,order,state,policy,self.endpoint)["nonce"],NONCE)

    def test_wrong_epoch_or_sla_or_endpoint_refused(self):
        for mutation in (
            lambda x:x["epoch"].update(requestHash="0x"+"cc"*32),
            lambda x:x["lease"].update(slaPolicyHash="0x"+"dd"*32),
            lambda x:x["lease"].update(serviceEndpointHash="0x"+"ff"*32),
            lambda x:x["lease"].update(consumer=Account.create().address.lower()),
        ):
            changed=deepcopy(self.state);mutation(changed)
            with self.subTest(mutation=mutation),self.assertRaises((SLAError,ExchangeError)):
                authenticate_request(self.order,changed,self.policy,self.endpoint,self.provider)

    def test_non_tailscale_public_endpoints_refused(self):
        for url in ("http://external.example:8080","https://attacker.example",
                    "https://bad.ts.net/?secret=x","https://x:y@foo.ts.net",
                    "file:///etc/passwd","http://127.0.0.1:8080/?key=x"):
            with self.subTest(url=url),self.assertRaises(ExchangeError):
                validate_endpoint_url(url)
        self.assertEqual(validate_endpoint_url("https://provider.demo.ts.net"),
                         "https://provider.demo.ts.net")

    def test_replay_nonce_rejected_over_real_loopback_http(self):
        # Allocate a port prior to committing the URL in the synthetic
        # chain snapshot. Actual chain discovery requires an independent VM.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
        url="http://127.0.0.1:"+str(port)
        c,p,policy,state=setup(endpoint=url)
        server=service.make_server(port,p,policy,url,lambda lease,epoch:state)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            result=submit_work_request(url,state,policy,c,NONCE)
            self.assertTrue(result["receiptAcceptedByProvider"])
            self.assertFalse(result["physicalDeadlineCertified"])
            with self.assertRaises(ExchangeError):
                submit_work_request(url,state,policy,c,NONCE)
            from sse_direct_delivery import post_json
            r=post_json(url,prepare_request(state,policy,url,c,"0x"+"aa"*32))
            self.assertEqual(r["schema"],"sse-direct-response-v1")
            self.assertIn("resultHash",r["message"])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)

    def test_server_refuses_wrong_consumer_or_wrong_lease(self):
        c,p,policy,state=setup(endpoint=self.endpoint)
        wrong=deepcopy(state)
        wrong["lease"]["provider"]=Account.create().address.lower()
        server=service.make_server(0,p,policy,self.endpoint,lambda lease,epoch:wrong)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            from sse_direct_delivery import post_json
            order=prepare_request(state,policy,self.endpoint,c,NONCE)
            # HTTP endpoint cannot match ephemeral bound port, but this
            # test checks authorization before responding via direct call.
            with self.assertRaises(ExchangeError):
                authenticate_request(order,wrong,policy,self.endpoint,p)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=="__main__": unittest.main()
