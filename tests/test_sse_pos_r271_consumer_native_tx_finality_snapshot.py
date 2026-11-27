"""R271 exact real consumer funding TX status visibility, all MOCKED no-send."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r271_consumer_native_tx_finality_snapshot as r


class TestR271ReadOnlyConsumerTxFinality(unittest.TestCase):
    def rig(self,*,final_height=25500,included_height=25511,
            receipt_status=1,genesis=r.GENESIS,wrong_receipt=False,
            optimistic=False):
        txhash=r.TX
        included_hash="0x"+"df"*32
        events=[]
        tx={
            "hash":txhash,"from":r.APP,"to":r.RECIPIENTS[0][1],
            "value":hex(r.RECIPIENTS[0][2]),"nonce":"0x1",
            "gas":hex(r.GAS_LIMIT),"gasPrice":hex(r.GAS_PRICE),
            "input":"0x","chainId":hex(r.CHAIN),
        }
        receipt={
            "transactionHash":txhash,"from":r.APP,
            "to":r.RECIPIENTS[0][1],"contractAddress":None,
            "status":hex(receipt_status),
            "gasUsed":hex(r.GAS_LIMIT),
            "blockNumber":hex(included_height),"blockHash":included_hash,
        }
        if wrong_receipt:
            receipt["blockHash"]="0x"+"ed"*32

        def rpc(url,method,args):
            self.assertEqual(url,r.RPC)
            self.assertNotIn(method,("eth_sendRawTransaction","eth_sendTransaction"))
            events.append(method)
            if method=="eth_chainId":return hex(r.CHAIN)
            if method=="eth_getBlockByNumber":
                if args[0]=="0x0":return {"hash":genesis}
                if args[0]=="latest":return {"number":hex(max(final_height,included_height)+10)}
                if args[0]=="finalized":return {"number":hex(final_height)}
                if args[0]==hex(included_height):return {"hash":included_hash}
            if method=="eth_getTransactionByHash":return tx
            if method=="eth_getTransactionReceipt":return receipt
            if method=="eth_getBalance":
                self.assertEqual(args[0].lower(),r.RECIPIENTS[0][1].lower())
                return hex(r.RECIPIENTS[0][2] if args[1]=="latest" or final_height>=included_height else 0)
            raise AssertionError("unexpected RPC "+repr((method,args)))

        def beacon(endpoint):
            if endpoint=="/eth/v1/beacon/genesis":
                return {"genesis_validators_root":r.BEACON_ROOT}
            if endpoint=="/eth/v1/node/syncing":
                return {"head_slot":"30000","is_syncing":False,
                        "is_optimistic":optimistic,"el_offline":False}
            if endpoint=="/eth/v1/beacon/states/head/finality_checkpoints":
                return {"finalized":{"epoch":"935","root":"0x"+"a1"*32}}
            raise AssertionError("unexpected Beacon")
        return rpc,beacon,events

    def test_receipt_successful_canonical_but_not_final(self):
        rpc,bn,calls=self.rig()
        actual=r.observation(transport=rpc,beacon=bn)
        self.assertEqual(actual["transactionStatus"],
                         "SUCCESSFUL_CANONICAL_NOT_YET_FINALIZED")
        self.assertEqual(actual["executionRemainingBlocksUntilTxFinality"],11)
        self.assertEqual(actual["consumerFinalizedBalanceWei"],"0")
        self.assertFalse(actual["transactionsSignedOrSent"])
        self.assertEqual(actual["beaconFinalityLagEpochs"],2)
        self.assertNotIn("eth_sendRawTransaction",calls)

    def test_after_finalized_eligible_for_separate_r267_check(self):
        rpc,bn,_=self.rig(final_height=25532)
        actual=r.observation(transport=rpc,beacon=bn)
        self.assertEqual(actual["transactionStatus"],"SUCCESSFUL_CANONICAL_FINALIZED")
        self.assertEqual(actual["executionRemainingBlocksUntilTxFinality"],0)
        self.assertEqual(actual["consumerFinalizedBalanceWei"],str(r.RECIPIENTS[0][2]))

    def test_actual_reverted_funding_is_refused_not_called_pending(self):
        rpc,bn,_=self.rig(receipt_status=0)
        with self.assertRaisesRegex(r.Refused,"REVERTED"):
            r.observation(transport=rpc,beacon=bn)

    def test_noncanonical_receipt_is_refused(self):
        rpc,bn,_=self.rig(wrong_receipt=True)
        with self.assertRaisesRegex(r.Refused,"NOT on canonical"):
            r.observation(transport=rpc,beacon=bn)

    def test_genesis_or_optimistic_node_refuses(self):
        for settings in (
            {"genesis":"0x"+"ee"*32},
            {"optimistic":True},
        ):
            with self.subTest(settings=settings):
                rpc,bn,_=self.rig(**settings)
                with self.assertRaises(r.Refused):
                    r.observation(transport=rpc,beacon=bn)

if __name__=="__main__":
    unittest.main()
