"""R9 actual-client canary has a separately approved P2P-disabled boundary."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_r9_canary_lab as c
from sse_qbft_lab_config import genesis

SHA="a"*40

class CanaryRealGateTests(unittest.TestCase):
    def test_plan_does_not_pull_docker_or_claim_four_host_network(self):
        p=c.check("hyperledger/besu:26.11.1",SHA,"vm4704-test1")
        self.assertEqual(p["mode"],"DRY_RUN")
        self.assertFalse(p["p2pEnabled"])
        self.assertFalse(p["discoveryEnabled"])
        self.assertTrue(p["experimentalImageDigestNotYetVerified"])
        self.assertFalse(p["besuContainersStarted"])
        self.assertFalse(p["historicalAnvilTouched"])

    def test_reject_vulnerable_and_mutable_tag(self):
        for version in (
            "hyperledger/besu:latest","hyperledger/besu:26.8.0", "hyperledger/besu:26.11.0",
            "hyperledger/besu:26.7.1","evil/besu:26.11.1",
            "hyperledger/besu:26.11.1-rc1",
        ):
            with self.subTest(version=version),self.assertRaises(c.CanaryError):
                c.check(version,SHA,"vm4704-test1")
        with self.assertRaises(c.CanaryError):
            c.check("hyperledger/besu:26.11.1",SHA,"../../danger")

    def test_canary_uses_only_synthetic_public_addresses(self):
        self.assertEqual(len(c.SYNTHETIC_ADDRS),4)
        self.assertEqual(len(set(c.SYNTHETIC_ADDRS)),4)
        g=genesis(c.SYNTHETIC_ADDRS,chain_id=31338,block_period=5,
                  gas_limit=15_000_000,reward_wei=0)
        self.assertEqual(g["config"]["qbft"]["blockreward"],"0")
        self.assertEqual(g["config"]["chainId"],31338)
        self.assertFalse(g["alloc"])

    def test_actual_block0_and_client_version_probed(self):
        calls=[]
        def valid(method,params):
            calls.append((method,params))
            if method=="eth_chainId":return "0x7a6a"
            if method=="eth_getBlockByNumber":
                return {"number":"0x0","hash":"0x"+"be"*32}
            if method=="web3_clientVersion":return "besu/26.11.1/linux"
            raise AssertionError("unknown RPC")
        result=c.probe(read_rpc=valid,retries=1,sleep=lambda _:None)
        self.assertEqual(result["observedBlock0Hash"],"0x"+"be"*32)
        self.assertTrue(result["genesisHashIsNotFileSha256"])
        self.assertFalse(result["startedValidator"])
        self.assertEqual(len(calls),3)
        self.assertTrue(all(method in ("eth_chainId","eth_getBlockByNumber",
                                       "web3_clientVersion") for method,_ in calls))

    def test_wrong_genesis_wrong_chain_and_wrong_client_fail_closed(self):
        for kind in ("wrongChain","missingBlock","badClient"):
            def bad(method,params):
                if method=="eth_chainId":
                    return "0x7a69" if kind=="wrongChain" else "0x7a6a"
                if method=="eth_getBlockByNumber":
                    return None if kind=="missingBlock" else {"number":"0x0","hash":"0x"+"aa"*32}
                return "not-besu" if kind=="badClient" else "besu/26.11.1"
            # "not-besu" includes 'besu'; choose an unequivocal wrong client.
            if kind=="badClient":
                def bad(method,params):
                    if method=="eth_chainId":return "0x7a6a"
                    if method=="eth_getBlockByNumber":
                        return {"number":"0x0","hash":"0x"+"aa"*32}
                    return "unknown-jvm-client"
            with self.subTest(kind=kind),self.assertRaises(c.CanaryError):
                c.probe(read_rpc=bad,retries=1,sleep=lambda _:None)

    def test_operator_run_never_silently_repulls_or_waits_for_sudo(self):
        source=(ROOT/"tools"/"sse_r9_canary_lab.py").read_text()
        self.assertIn('["sudo","-n","docker","info"',source)
        self.assertIn('["sudo","-n","docker","pull",version]',source)
        self.assertIn('base+["up","-d","--pull","never"]',source)
        self.assertIn('SSE_R9_CANARY_STAGE=',source)
        self.assertNotIn('["sudo","docker","pull"',source)

    def test_approved_compose_template_has_no_p2p_or_secrets(self):
        text=(ROOT/"infra"/"qbft-multivm"/"genesis-canary.compose.yaml").read_text()
        self.assertIn("--p2p-enabled=false",text)
        self.assertIn("--discovery-enabled=false",text)
        self.assertIn("--rpc-http-host=127.0.0.1",text)
        self.assertIn("restart: \"no\"",text)
        self.assertNotIn("node.key",text.lower())
        self.assertNotIn("18545",text)

if __name__=="__main__":
    unittest.main()
