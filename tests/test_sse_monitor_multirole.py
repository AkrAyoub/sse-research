"""R4/R5: one node can have multiple roles without witnessing its own lease.

These offline tests use a simulated chain snapshot, actual EIP-712 provider
and monitor signatures and real loopback HTTP. No live on-chain vote is sent.
"""
from __future__ import annotations

import sys
import socket
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
from sse_evidence_wire_v1 import EvidenceScope, VerificationContext
from sse_http_signed_delivery_v1 import EvidenceArchive, capture_response
from sse_challenge import expected_response_hash
from sse_direct_delivery import post_json
from typed_evidence import Domain
from direct_work_service import make_server


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

    def test_real_loopback_challenge_archives_two_authentic_signatures(self):
        endpoint,c,p,policy,state,monitors,node=fixture()
        server=make_server(int(endpoint.rsplit(":",1)[1]),p,policy,endpoint,
                           lambda lease,epoch:state)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            authorize_selected_monitor(node,state,monitors[0].address)
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


if __name__=="__main__":
    unittest.main()
