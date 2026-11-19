"""Public-release preflight unit tests. No mock data is live-network evidence."""
from __future__ import annotations

import copy
import socket
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from sse_public_network_preflight import (
    validate,probe,PublicManifestError,ROLE_RULES,
)

def fixture():
    enode1="enode://"+"12"*64+"@alpha.bootstrap.duckdns.org:30303"
    enode2="enode://"+"34"*64+"@beta.bootstrap.dynu.net:30303"
    return {
        "schema":"SSE_PUBLIC_POS_RELEASE_V1",
        "networkName":"sse-public-pos-test",
        "chainId":31340,
        "currency":"UNVALUED_TEST_ETH",
        "executionGenesisHash":"0x"+"56"*32,
        "beaconGenesisValidatorsRoot":"0x"+"78"*32,
        "secondsPerSlot":12,
        "slotsPerEpoch":32,
        "executionGenesisFile":"https://public-node.example.org/genesis.json",
        "executionGenesisSha256":"ab"*32,
        "consensusConfigFile":"https://public-node.example.org/config.yaml",
        "consensusConfigSha256":"cd"*32,
        "depositContract":"0x00000000219ab540356cBB839Cbe05303d7705Fa",
        "bootnodes":[
            {"operatorId":"operator-a","nodeId":"node-a",
             "executionEnode":enode1,"consensusENR":"enr:"+"A"*120},
            {"operatorId":"operator-b","nodeId":"node-b",
             "executionEnode":enode2,"consensusENR":"enr:"+"B"*120},
        ],
        "permissionlessRoles":ROLE_RULES,
    }

class SSEPublicNetworkTests(unittest.TestCase):
    def test_schema_with_distinct_dns_bootnodes_does_not_claim_public(self):
        review=validate(fixture())
        self.assertEqual(review["targetChainId"],31340)
        self.assertFalse(review["bootstrapRequiresStaticIP"])
        self.assertFalse(review["fullNodeAdmissionRequiresInvite"])
        self.assertFalse(review["validatorAdmissionRequiresSSEAdministrator"])
        self.assertFalse(review["permissionlessPublicNetworkReady"])
        self.assertFalse(review["independentPhysicalOperatorsVerified"])
        self.assertFalse(review["consensusDiscv5HandshakeVerified"])

    def test_existing_exposed_genesis_chain_refused(self):
        f=fixture();f["chainId"]=31339
        with self.assertRaises(PublicManifestError):validate(f)

    def test_wont_accept_overlay_lab_or_nonpublic_fqdn(self):
        for host in ("node.tailnet.ts.net","vm4705.example.org",
                     "localhost","10.50.56.13","node.local",
                     "node.example","node.internal"):
            f=fixture()
            f["bootnodes"][0]["executionEnode"]=(
                "enode://"+"12"*64+f"@{host}:30303")
            with self.subTest(host=host),self.assertRaises(PublicManifestError):
                validate(f)

    def test_same_operator_is_not_two_independent_public_seeds(self):
        f=fixture()
        f["bootnodes"][1]["operatorId"]="operator-a"
        with self.assertRaises(PublicManifestError):validate(f)
        f=fixture()
        f["bootnodes"][1]["executionEnode"]=f["bootnodes"][0]["executionEnode"]
        with self.assertRaises(PublicManifestError):validate(f)

    def test_admin_invite_is_not_eligibility_for_any_role(self):
        f=fixture()
        f["permissionlessRoles"]={**ROLE_RULES,"validator":"APPROVAL_BY_SSE_OWNER"}
        with self.assertRaises(PublicManifestError):validate(f)
        f=fixture();del f["permissionlessRoles"]["monitor"]
        with self.assertRaises(PublicManifestError):validate(f)

    def test_missing_public_artifact_digest_or_fake_urls_refused(self):
        f=fixture();f["executionGenesisSha256"]="0"*64
        with self.assertRaises(PublicManifestError):validate(f)
        f=fixture();f["executionGenesisFile"]="http://127.0.0.1:8000/genesis.json"
        with self.assertRaises(PublicManifestError):validate(f)
        f=fixture();f["consensusConfigFile"]="https://private.local/config.yaml"
        with self.assertRaises(PublicManifestError):validate(f)

    def test_real_dns_is_required_not_private_rfc1918(self):
        f=fixture()
        def private_resolver(host,port,proto):
            return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("10.50.56.13",port))]
        with self.assertRaises(PublicManifestError):
            probe(f,resolver=private_resolver)

    def test_dns_tcp_observation_is_not_ethereum_handshake_or_join(self):
        f=fixture()
        seen=[]
        def public_resolver(host,port,proto):
            return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("8.8.8.8",port))]
        class Connection:
            def close(self):seen.append("closed")
        def fake_connector(addr,timeout):
            seen.append(addr[0])
            return Connection()
        r=probe(f,resolver=public_resolver,connector=fake_connector,
                check_tcp=True)
        self.assertEqual(len(seen),4)
        self.assertTrue(r["tcpReachabilityObserved"])
        self.assertFalse(r["permissionlessPublicNetworkReady"])
        self.assertFalse(r["consensusDiscv5HandshakeVerified"])
        self.assertFalse(r["validatorDepositAndActivationVerified"])

    def test_no_static_ip_is_not_a_promise_of_nattless_reachability(self):
        f=fixture()
        r=validate(f)
        self.assertFalse(r["tcpReachabilityObserved"])
        self.assertFalse(r["independentPhysicalOperatorsVerified"])
        self.assertFalse(r["realCrossHostSLAObserved"])

if __name__=="__main__":
    unittest.main()
