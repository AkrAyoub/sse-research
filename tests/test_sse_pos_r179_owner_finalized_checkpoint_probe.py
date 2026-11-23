"""R179 owner finalized checkpoint read-only API validation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r179_owner_finalized_checkpoint_probe as m

class R179(unittest.TestCase):
    def test_existing_owner_finalized_root_and_header_must_match(self):
        root="0x"+"ab"*32
        calls=[]
        def fetch(path):
            calls.append(path)
            if path==m.PATHS["genesis"]:
                return {"data":{"genesis_validators_root":m.EXPECTED_GENESIS}}
            if path==m.PATHS["finality"]:
                return {"data":{"finalized":{"epoch":"558","root":root}}}
            return {"data":{"root":root,
                "header":{"message":{"slot":str(558*32)}}}}
        report=m.probe(fetch=fetch)
        self.assertEqual(report["finalizedEpoch"],558)
        self.assertEqual(report["finalizedBlockRoot"],root)
        self.assertFalse(report["remoteCheckpointBytesAvailableOrReachable"])
        self.assertEqual(len(calls),3)

    def test_mismatched_checkpoint_root_fails_closed(self):
        root="0x"+"ab"*32
        def fetch(path):
            if path==m.PATHS["genesis"]:
                return {"data":{"genesis_validators_root":m.EXPECTED_GENESIS}}
            if path==m.PATHS["finality"]:
                return {"data":{"finalized":{"epoch":"558","root":root}}}
            return {"data":{"root":"0x"+"cd"*32,
                "header":{"message":{"slot":"17856"}}}}
        with self.assertRaisesRegex(m.Refused,"disagrees"):
            m.probe(fetch=fetch)

if __name__=="__main__":
    unittest.main()
