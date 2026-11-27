"""Unit tests for storage and observation handling; no live network claims."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_native_reward_collector as c

def observation(slot):
    return {"observedUnixNs":slot,"headSlot":slot,"gapBeforeStart":False,
            "checkpoints":{"data":{"finalized":{"epoch":"1"}}},
            "attestationRewards":{"1":{"available":True,"response":{"finalized":False,
                "data":{"ideal_rewards":[{"unused":1}],"total_rewards":[
                    {"validator_index":"2","head":"5","source":"-3","target":"7","inactivity":"-2"}]}}},
                "0":{"available":False,"httpStatus":404}},
            "recentBlockRewards":{"30":{"available":True,"response":{"finalized":False,
                "data":{"proposer_index":"2","total":"0"}}},
                "31":{"available":False,"httpStatus":404}}}

class CollectorTests(unittest.TestCase):
    def test_unknown_not_zero(self):
        d=c.summarize(observation(32))
        self.assertEqual(d["attestationRewards"][0]["netGwei"],7)
        self.assertFalse(d["attestationRewards"][0]["apiFinalized"])
        self.assertFalse(d["attestationRewards"][1]["available"])
        self.assertEqual(d["blockRewards"][0]["totalGwei"],"0")
        self.assertFalse(d["blockRewards"][1]["available"])

    def test_compact(self):
        d=c.compact(observation(32))
        self.assertNotIn("ideal_rewards",d["attestationRewards"]["1"]["response"]["data"])
        self.assertEqual(c.summarize(d)["attestationRewards"][0]["netGwei"],7)

    def test_http_error(self):
        def missing():
            raise HTTPError("http://localhost",404,"missing",{},None)
        self.assertEqual(c.optional(missing),{"available":False,"httpStatus":404})

    def test_cursor_retention_and_original_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=root/"native-1.json"
            original.write_text("original")
            for slot in range(32,50):
                with patch.object(c,"collect",return_value=observation(slot)) as f:
                    c.tick(root,16)
                    f.assert_called_once_with(None if slot==32 else slot-1)
            self.assertEqual(len(list(root.glob("sample-*.json"))),16)
            self.assertEqual(original.read_text(),"original")
            self.assertEqual(json.loads((root/"cursor.json").read_text())["headSlot"],49)
            self.assertEqual(json.loads((root/"latest.json").read_text())["headSlot"],49)
            self.assertFalse((root/"sample-32.json").exists())

    def test_failed_collection_preserves_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(c,"collect",return_value=observation(32)):
                c.tick(root,16)
            before=(root/"latest.json").read_bytes()
            with patch.object(c,"collect",side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    c.tick(root,16)
            self.assertEqual((root/"latest.json").read_bytes(),before)
            self.assertEqual(json.loads((root/"cursor.json").read_text())["headSlot"],32)

    def test_invalid_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                c.tick(Path(tmp),15)

if __name__=="__main__":
    unittest.main()
