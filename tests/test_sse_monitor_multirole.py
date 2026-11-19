"""R4/R5: one node can have multiple roles without witnessing its own lease.

These offline tests use a simulated chain snapshot, actual EIP-712 provider
and monitor signatures and real loopback HTTP. No live on-chain vote is sent.
"""
from __future__ import annotations

import json
import sys
import socket
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from unittest.mock import patch
import tempfile
import threading
import unittest
from pathlib import Path
from copy import deepcopy

from eth_account import Account

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT/"services"/"monitor-agent"))
sys.path.insert(0,str(ROOT/"services"/"provider-agent"))

from test_sse_sla_direct_delivery import setup
from sse_node_role_policy import RolePolicyError, role_manifest, authorize_selected_monitor
from sse_monitor_challenge import signed_challenge, ChallengeError
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext, AuthenticationError
from sse_http_signed_delivery_v1 import (
    EvidenceArchive, capture_response, fetch_provider_payload)
from sse_challenge import expected_response_hash
from sse_direct_delivery import ExchangeError, post_json, submit_work_request
from typed_evidence import Domain
from direct_work_service import make_server
from sse_sla_manifest import canonical_policy
from sse_resource_profile_v2 import make_profile, canonical_profile, resource_hash
from sse_sla_manifest import proposed_policy
import monitor_capture_once


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def fixture():
    endpoint="http://127.0.0.1:"+str(port())
    consumer,provider,policy,state=setup(endpoint=endpoint)
    monitor_wallets=[Account.create() for _ in range(4)]
    lease=state["lease"]; epoch=state["epoch"]
    lease["monitors"]=[m.address.lower() for m in monitor_wallets]
    lease["monitorConfirmations"]=4
    epoch["monitoringClose"]=500
    epoch["monitoringSealed"]=False
    epoch["evidenceClosed"]=False
    state["blockTimestamp"]=100
    node={"schema":"sse-node-roles-v1","nodeId":"vm-monitor-provider",
          "roles":["provider","monitor","observer"],
          "wallets":{"provider":Account.create().address.lower(),
                     "monitor":monitor_wallets[0].address.lower()}}
    return endpoint,consumer,provider,policy,state,monitor_wallets,node


class MultiRoleMonitorTests(unittest.TestCase):
    def test_node_can_have_provider_monitor_observer_but_not_same_wallet(self):
        _,c,p,policy,state,monitors,node=fixture()
        checked=role_manifest(node)
        self.assertEqual(checked["roles"],["provider","monitor","observer"])
        self.assertTrue(authorize_selected_monitor(node,state,monitors[0].address)["selectedForLease"])
        self.assertFalse(authorize_selected_monitor(node,state,monitors[0].address)["operatorIndependenceVerified"])
        bad=deepcopy(node);bad["wallets"]["provider"]=bad["wallets"]["monitor"]
        with self.assertRaises(RolePolicyError): role_manifest(bad)

    def test_node_provider_or_consumer_role_conflict_refused(self):
        _,consumer,provider,policy,state,monitors,node=fixture()
        for role, wallet in (("provider",provider.address),("consumer",consumer.address)):
            bad=deepcopy(node)
            if role=="consumer":
                bad["roles"].append("consumer")
            bad["wallets"][role]=wallet.lower()
            with self.subTest(role=role),self.assertRaises(RolePolicyError):
                authorize_selected_monitor(bad,state,monitors[0].address)

    def test_nonselected_unconfirmed_and_closed_refused(self):
        _,consumer,provider,policy,state,monitors,node=fixture()
        for mutate in (
            lambda s:s["lease"].update(monitors=[Account.create().address.lower(),
                                                *s["lease"]["monitors"][1:]]),
            lambda s:s["lease"].update(monitorConfirmations=3),
            lambda s:s["epoch"].update(monitoringSealed=True),
            lambda s:s.update(blockHashPinned=False),
        ):
            bad=deepcopy(state);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(RolePolicyError):
                authorize_selected_monitor(node,bad,monitors[0].address)

    def test_signed_provider_challenge_scoped_to_admitted_epoch(self):
        endpoint,c,p,policy,state,monitors,node=fixture()
        request={"leaseId":1,"epochId":0,
                 "requestHash":state["epoch"]["requestHash"]}
        response=signed_challenge(request,state,policy,endpoint,p)
        self.assertEqual(response["responseHash"],
                         expected_response_hash(request["requestHash"]))
        self.assertEqual(len(response["providerSignature"]),132)
        for mutated in (
            {**request,"requestHash":"0x"+"ab"*32},
            {**request,"epochId":1},
            {**request,"extra":"invalid"},
        ):
            with self.subTest(mutated=mutated),self.assertRaises((ChallengeError,ValueError)):
                signed_challenge(mutated,state,policy,endpoint,p)
        with self.assertRaises(ChallengeError):
            signed_challenge(request,state,policy,endpoint,c)

    def test_overlay_https_transport_rejects_public_hosts_and_redirect_targets(self):
        _,c,p,policy,state,monitors,node=fixture()
        scope=EvidenceScope(policy["chainId"],policy["settlement"],1,0,
                            state["lease"]["slaPolicyHash"],
                            state["lease"]["resourceProfileHash"],
                            state["epoch"]["requestHash"])
        for origin in ("https://attacker.example.org",
                       "http://provider.mesh.ts.net",
                       "https://provider.mesh.ts.net.evil.org",
                       "https://user:pass@provider.mesh.ts.net",
                       "https://provider.mesh.ts.net:9443",
                       "https://provider.mesh.ts.net/path"):
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                fetch_provider_payload(origin,scope,allow_tailnet=True)
        class FakeResponse:
            status=200
            headers={"Content-Length":"2"}
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b"{}"
        class FakeOpener:
            def open(self,request,timeout):
                self.request=request
                return FakeResponse()
        opener=FakeOpener()
        with patch("sse_http_signed_delivery_v1.build_opener",
                   return_value=opener) as built:
            raw=fetch_provider_payload("https://provider.mesh.ts.net",scope,
                                       allow_tailnet=True)
        self.assertEqual(raw,b"{}")
        self.assertEqual(opener.request.full_url,
                         "https://provider.mesh.ts.net/v1/challenge")
        self.assertEqual(built.call_count,1)

    def test_remote_capture_requires_pinned_provenance(self):
        endpoint,c,p,policy,state,monitors,node=fixture()
        scope=EvidenceScope(policy["chainId"],policy["settlement"],1,0,
                            state["lease"]["slaPolicyHash"],
                            state["lease"]["resourceProfileHash"],
                            state["epoch"]["requestHash"])
        context=VerificationContext(scope,frozenset(state["lease"]["monitors"]))
        with tempfile.TemporaryDirectory() as td:
            archive=EvidenceArchive(Path(td)/"remote-observations.sqlite")
            with self.assertRaises(AuthenticationError):
                capture_response("https://provider.mesh.ts.net",
                    Domain(policy["chainId"],policy["settlement"]),
                    p.address.lower(),scope,
                    "0x"+bytes(monitors[0].key).hex(),context,archive,
                    allow_tailnet=True)
            self.assertEqual(archive.count(),0)

    def test_real_loopback_challenge_archives_two_authentic_signatures(self):
        endpoint,c,p,policy,state,monitors,node=fixture()
        server=make_server(int(endpoint.rsplit(":",1)[1]),p,policy,endpoint,
                           lambda lease,epoch:state)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            authorize_selected_monitor(node,state,monitors[0].address)
            challenge={"leaseId":1,"epochId":0,
                       "requestHash":state["epoch"]["requestHash"]}
            with self.assertRaises(ExchangeError):
                post_json(endpoint,challenge)  # /v1/work is not the challenge API
            import json as _json
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError
            # No provider monitor-facing signature is released before
            # a verified consumer-signed receipt exists.
            req=Request(endpoint+"/v1/challenge",
                        data=_json.dumps(challenge).encode("ascii"),
                        headers={"Content-Type":"application/json"},method="POST")
            with self.assertRaises(HTTPError) as denied:
                urlopen(req,timeout=3)
            self.assertEqual(denied.exception.code,422)
            self.assertTrue(submit_work_request(
                endpoint,state,policy,c,"0x"+"aa"*32)["receiptAcceptedByProvider"])
            scope=EvidenceScope(policy["chainId"],policy["settlement"],1,0,
                                state["lease"]["slaPolicyHash"],
                                state["lease"]["resourceProfileHash"],
                                state["epoch"]["requestHash"])
            context=VerificationContext(scope,frozenset(state["lease"]["monitors"]))
            with tempfile.TemporaryDirectory() as td:
                archive=EvidenceArchive(Path(td)/"observations.sqlite")
                response=capture_response(endpoint,
                    Domain(policy["chainId"],policy["settlement"]),
                    p.address.lower(),scope,
                    "0x"+bytes(monitors[0].key).hex(),context,archive)
                self.assertTrue(response.stored_new)
                self.assertEqual(archive.count(),1)
                env,raw=archive.load(response.evidence_id,context,
                                     Domain(policy["chainId"],policy["settlement"]),
                                     p.address.lower())
                self.assertEqual(env["signer"],monitors[0].address.lower())
                self.assertIn(b'providerSignature',raw)
                self.assertEqual(response.response_hash,
                                 expected_response_hash(scope.request_hash))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


class MonitorCLIPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.endpoint="http://127.0.0.1:8877"
        self.profile=make_profile("http_challenge",self.endpoint)
        self.policy=proposed_policy(service_kind="http_challenge",
            chain_id=31337,settlement="0x"+"12"*20,
            resource_profile_hash=resource_hash(self.profile))
        self.monitor=Account.create()
        self.roles={"schema":"sse-node-roles-v1","nodeId":"monitor-combined-node",
                    "roles":["monitor","observer"],
                    "wallets":{"monitor":self.monitor.address.lower()}}
        (self.dir/"roles.json").write_text(json.dumps(self.roles))
        (self.dir/"sla.json").write_bytes(canonical_policy(self.policy))
        (self.dir/"resource.json").write_bytes(canonical_profile(self.profile))

    def args(self):
        return ["--node-roles-file",str(self.dir/"roles.json"),
                "--policy",str(self.dir/"sla.json"),
                "--resource-profile",str(self.dir/"resource.json"),
                "--endpoint",self.endpoint,"--lease-id","1","--epoch-id","0",
                "--rpc-url","http://127.0.0.1:8545",
                "--archive",str(self.dir/"monitor-evidence.sqlite")]

    def test_default_dry_run_is_no_rpc_no_signer_no_archive(self):
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(monitor_capture_once.main(self.args()),0)
        data=json.loads(out.getvalue())
        self.assertFalse(data["probePerformed"])
        self.assertFalse(data["chainVerified"])
        self.assertFalse(data["monitorVoteSubmitted"])
        self.assertFalse((self.dir/"monitor-evidence.sqlite").exists())

    def test_node_without_monitor_role_fails_before_network(self):
        self.roles["roles"]=["observer"];self.roles["wallets"]={}
        (self.dir/"roles.json").write_text(json.dumps(self.roles))
        with redirect_stderr(StringIO()):
            self.assertEqual(monitor_capture_once.main(self.args()),1)

    def test_missing_signer_file_refused_before_rpc(self):
        with redirect_stderr(StringIO()):
            self.assertEqual(monitor_capture_once.main(self.args()+["--capture"]),1)

    def test_nonprivate_service_transport_not_activated(self):
        args=self.args();args[args.index("--endpoint")+1]="https://public.example.org"
        with redirect_stderr(StringIO()):
            self.assertEqual(monitor_capture_once.main(args+["--capture"]),1)


if __name__=="__main__":
    unittest.main()
