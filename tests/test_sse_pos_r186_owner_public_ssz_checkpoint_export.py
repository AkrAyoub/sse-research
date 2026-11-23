"""R186 only simulated HTTP payloads for exporter algorithm; no chain simulation."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r186_owner_public_ssz_checkpoint_export as m

ROOT="0x"+"ab"*32
class Tests(unittest.TestCase):
    def fake(self,*,advance=False):
        counter=[0]
        def fetch(path,**kw):
            if path.endswith("/genesis"):
                return {"genesis_validators_root":m.GENESIS}
            if path.endswith("/finality_checkpoints"):
                counter[0]+=1
                return {"finalized":{"epoch":"560","root":(
                    "0x"+"cd"*32 if advance and counter[0]==2 else ROOT)}}
            if path.endswith("/states/finalized"):
                return b"s"*2857
            if path.endswith("/blocks/finalized"):
                return b"b"*1417
            if path.endswith("/headers/finalized"):
                return {"root":ROOT,"header":{"message":{"slot":"17920"}}}
            raise AssertionError(path)
        return fetch
    def test_pair_export_identical_stable_checkpoint(self):
        manifest,state,block=m.collect(get=self.fake())
        self.assertEqual(manifest["finalizedEpoch"],560)
        self.assertTrue(manifest["finalizedRootStableAcrossReads"])
        self.assertFalse(manifest["cryptographicStateRootVerifiedByThisExporter"])
        self.assertEqual(manifest["checkpointState"]["sha256"],hashlib.sha256(state).hexdigest())
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"checkpoint"
            m.persist(out,manifest,state,block)
            self.assertEqual((out/"checkpoint-state.ssz").read_bytes(),state)
            with self.assertRaisesRegex(m.Refused,"ALREADY_EXISTS"):
                m.persist(out,manifest,state,block)
    def test_checkpoint_shift_refused_and_no_output(self):
        with self.assertRaisesRegex(m.Refused,"ROOT_MOVED"):
            m.collect(get=self.fake(advance=True))
    def test_wrong_genesis_refused(self):
        with self.assertRaisesRegex(m.Refused,"GENESIS"):
            m.collect(get=lambda path,**kw:{"genesis_validators_root":"0x"+"cd"*32})
if __name__=="__main__":unittest.main()
