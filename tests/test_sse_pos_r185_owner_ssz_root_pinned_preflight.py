"""R185: pure mocked endpoint-selection tests. Never real network."""
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r185_owner_ssz_root_pinned_preflight as m

ROOT="0x"+"ab"*32
class TestR185(unittest.TestCase):
    def test_finalized_root_pins_both_state_and_block(self):
        calls=[]
        def fetch(path,**kw):
            calls.append(path)
            if path.endswith("/genesis"):
                return {"genesis_validators_root":m.EXPECTED_GENESIS}
            if path.endswith("/finality_checkpoints"):
                return {"finalized":{"epoch":"560","root":ROOT}}
            if path=="/eth/v2/debug/beacon/states/"+ROOT:
                self.assertTrue(kw.get("binary"))
                return 2857456
            if path=="/eth/v2/beacon/blocks/"+ROOT:
                self.assertTrue(kw.get("binary"))
                return 1417
            raise AssertionError("Unexpected URL: "+path)
        result=m.probe(fetch=fetch)
        self.assertEqual(result["finalizedBlockRoot"],ROOT)
        self.assertTrue(result["sameImmutableBlockRootRequestedForBoth"])
        self.assertFalse(result["githubReleaseCreated"])
        self.assertFalse(result["anyHostOrChainMutation"])
        self.assertEqual(len(calls),4)
        self.assertNotIn("/eth/v2/debug/beacon/states/finalized",calls)
    def test_wrong_genesis_refused_before_ssz(self):
        calls=[]
        def fetch(path,**kw):
            calls.append(path)
            return {"genesis_validators_root":"0x"+"de"*32}
        with self.assertRaisesRegex(m.Refused,"genesis"):
            m.probe(fetch=fetch)
        self.assertEqual(len(calls),1)
    def test_no_genesis_only_checkpoint(self):
        def fetch(path,**kw):
            if path.endswith("/genesis"):
                return {"genesis_validators_root":m.EXPECTED_GENESIS}
            return {"finalized":{"epoch":"0","root":ROOT}}
        with self.assertRaisesRegex(m.Refused,"checkpoint"):
            m.probe(fetch=fetch)

if __name__=="__main__":
    unittest.main()
