"""Offline four-view block sample: stable hash, period, gas and transaction counts."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_block_sample import sample_rpc,SampleError,percentile

GENESIS="0x"+"11"*32
VALIDATORS=["0x"+f"{i:02x}"*20 for i in range(1,5)]
RPCS=[f"http://127.0.0.1:{18545+i}" for i in range(4)]


def mock_rpc(url,method,params):
    if method=="eth_chainId":return hex(31338)
    if method=="eth_blockNumber":return hex(12)
    if method=="net_peerCount":return hex(3)
    if method=="qbft_getValidatorsByBlockNumber":return VALIDATORS
    if method=="eth_getBlockByNumber":
        n=int(params[0],16)
        return {"hash":GENESIS if n==0 else "0x"+f"{n:064x}",
                "number":hex(n),"timestamp":hex(1700000000+n*5),
                "gasUsed":hex(42000),"gasLimit":hex(15000000),
                "size":hex(1000+n),"transactions":["0x"+"44"*32]}
    raise AssertionError(method)

class SampleTests(unittest.TestCase):
    def test_four_views_and_measured_interval(self):
        report=sample_rpc(RPCS,chain_id=31338,genesis_hash=GENESIS,
                          expected_validators=4,blocks=5,call=mock_rpc)
        self.assertEqual(report["sampleBlocks"],5)
        self.assertEqual(report["meanBlockIntervalSeconds"],5)
        self.assertEqual(report["totalTransactionsIncluded"],5)
        self.assertEqual(report["totalGasUsed"],210000)
        self.assertFalse(report["physicalVMIndependenceProved"])
        self.assertFalse(report["proposerRewardsMeasured"])
        self.assertFalse(report["transactionsSent"])
    def test_four_nodes_required(self):
        with self.assertRaises(Exception):
            sample_rpc(RPCS[:2],chain_id=31338,genesis_hash=GENESIS,
                       expected_validators=4,blocks=5,call=mock_rpc)
    def test_fork_at_historical_height_rejected(self):
        def fork(url,method,params):
            if url==RPCS[2] and method=="eth_getBlockByNumber" and params[0]=="0xb":
                return {**mock_rpc(url,method,params),"hash":"0x"+"fe"*32}
            return mock_rpc(url,method,params)
        with self.assertRaises(SampleError):
            sample_rpc(RPCS,chain_id=31338,genesis_hash=GENESIS,
                       expected_validators=4,blocks=5,call=fork)
    def test_percentiles(self):
        self.assertIsNone(percentile([],.95))
        self.assertEqual(percentile([10,5,20,15],.5),10)

if __name__=="__main__":
    unittest.main()
