"""Offline R8 chain explorer checks: no external RPC, no transaction writes."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sse_chain_observer",ROOT/"tools"/"sse_chain_observer.py")
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

BOARD="0x"+"11"*20
POOL="0x"+"22"*20
HASH="0x"+"a1"*32


class FakeRPC:
    def __init__(self): self.calls=[]
    def __call__(self,method,params):
        self.calls.append((method,params))
        if method=="eth_chainId": return "0x7a69"
        if method=="eth_blockNumber": return "0x3"
        if method=="eth_getCode": return "0x6001"
        if method=="eth_getBlockByNumber":
            n=int(params[0],16)
            return {"number":hex(n),"hash":"0x"+format(n,"064x"),
                    "parentHash":"0x"+format(max(0,n-1),"064x"),
                    "timestamp":"0x6566a10a","transactions":[HASH] if n==2 else [],
                    "gasUsed":"0x5208"}
        if method=="eth_getTransactionByHash":
            return {"hash":HASH,"from":"0x"+"33"*20,"to":BOARD,
                    "value":"0xa","nonce":"0x1","input":"0x12345678",
                    "blockNumber":"0x2","blockHash":"0x"+format(2,"064x")}
        if method=="eth_getTransactionReceipt":
            return {"transactionHash":HASH,"status":"0x1",
                    "gasUsed":"0x5208","logs":[]}
        if method=="eth_getLogs":
            return [{"address":BOARD,"topics":["0x"+"ab"*32],"data":"0x",
                     "transactionHash":HASH,"blockHash":"0x"+format(2,"064x"),
                     "blockNumber":"0x2","logIndex":"0x0","removed":False}]
        raise AssertionError("forbidden RPC method "+method)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.fake=FakeRPC()
        self.o=m.Observer({"url":"http://127.0.0.1:8545","chain_id":31337,
                           "contracts":(BOARD,POOL)},transport=self.fake)

    def test_config_requirements(self):
        cfg=m.read_config({"SSE_OBSERVER_RPC_URL":"https://rpc.example.org",
                           "SSE_OBSERVER_CHAIN_ID":"31337",
                           "SSE_OBSERVER_CONTRACTS":BOARD+","+POOL})
        self.assertEqual(cfg["chain_id"],31337)
        self.assertEqual(cfg["contracts"],(BOARD,POOL))
        for url in ("http://remote.example","https://u:p@rpc.example",
                    "https://rpc.example?secret=x","file:///etc/passwd"):
            with self.subTest(url=url),self.assertRaises(m.ObserverError):
                m.read_config({"SSE_OBSERVER_RPC_URL":url,
                               "SSE_OBSERVER_CHAIN_ID":"31337",
                               "SSE_OBSERVER_CONTRACTS":BOARD})

    def test_overview_has_deployed_code_without_finality_claim(self):
        data=self.o.overview()
        self.assertEqual(data["headNumber"],3)
        self.assertEqual(len(data["contractAddresses"]),2)
        self.assertTrue(data["contractAddresses"][0]["hasCode"])
        self.assertFalse(data["rpcFinalityVerified"])
        self.assertFalse(data["ethTransactionsSent"])

    def test_recent_blocks_with_provisional_status(self):
        data=self.o.blocks(3)
        self.assertEqual([x["number"] for x in data["blocks"]],[3,2,1])
        self.assertEqual(data["blocks"][1]["transactionCount"],1)
        self.assertTrue(all(x["finality"]=="UNVERIFIED" for x in data["blocks"]))

    def test_transaction_receipt_is_not_proof_of_finality(self):
        data=self.o.transaction(HASH)
        self.assertEqual(data["confirmations"],2)
        self.assertEqual(data["receiptStatus"],1)
        self.assertEqual(data["finality"],"UNVERIFIED")
        self.assertFalse(data["transactionWasSentByObserver"])

    def test_logs_are_allowlisted_and_range_bounded(self):
        data=self.o.events(1,3)
        self.assertEqual(data["events"][0]["address"],BOARD)
        self.assertFalse(data["truncated"])
        self.assertEqual(self.fake.calls[-1][1][0]["address"],[BOARD,POOL])
        with self.assertRaises(m.ObserverError):
            self.o.events(0,256)
        with self.assertRaises(m.ObserverError):
            self.o.events(3,2)

    def test_wrong_contract_in_rpc_events_fails_closed(self):
        class BadRPC(FakeRPC):
            def __call__(self,method,params):
                if method=="eth_getLogs":
                    return [{"address":"0x"+"ee"*20}]
                return super().__call__(method,params)
        obs=m.Observer(self.o.config,transport=BadRPC())
        with self.assertRaises(m.ObserverError):
            obs.events(1,3)

    def test_reject_write_method_and_invalid_tx_hash(self):
        with self.assertRaises(m.ObserverError):
            self.o.rpc("eth_sendTransaction",[])
        with self.assertRaises(m.ObserverError):
            self.o.transaction("0xdeadbeef")
        self.assertEqual(self.fake.calls,[])

    def test_block_and_event_bounds(self):
        for limit in (0,21,-1,True):
            with self.subTest(limit=limit),self.assertRaises(m.ObserverError):
                self.o.blocks(limit)
        with self.assertRaises(m.ObserverError):
            self.o.events(0,4)

    def test_no_config_is_not_a_mock_network(self):
        with self.assertRaises(m.ObserverError):
            m.read_config({})


if __name__=="__main__":
    unittest.main()
