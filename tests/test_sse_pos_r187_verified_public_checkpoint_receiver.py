"""R187 isolated public checkpoint integrity tests: no network or Docker."""
from pathlib import Path
import json,sys,tempfile,hashlib,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r187_verified_public_checkpoint_receiver as m

class TestReceiver(unittest.TestCase):
    def sample(self):
        manifest={"schema":"SSE_R186_ORIGINAL_CHAIN31340_PUBLIC_SSZ_CHECKPOINT_V1",
          "chainId":31340,"genesisValidatorsRoot":m.GENESIS,
          "finalizedEpoch":565,"finalizedSlot":18080,"finalizedBlockRoot":m.ROOT,
          "finalizedRootStableAcrossReads":True,"containsWalletOrEngineJwt":False}
        for name,field in (("checkpoint-state.ssz","checkpointState"),
                           ("checkpoint-block.ssz","checkpointBlock")):
            size,digest=m.FILES[name]
            manifest[field]={"filename":name,"bytes":size,"sha256":digest}
        return manifest
    def test_actual_owner_manifest_pins_and_no_data_read(self):
        m.verify_manifest(json.dumps(self.sample()))
        a=self.sample()
        a["finalizedBlockRoot"]="0x"+"00"*32
        with self.assertRaises(m.Refused):
            m.verify_manifest(json.dumps(a))
    def test_tampered_asset_refused_before_creating_output(self):
        manifest=json.dumps(self.sample()).encode()
        with tempfile.TemporaryDirectory() as td:
            destination=Path(td)/"verified-checkpoint"
            def fake(url,*,max_bytes):
                if url.endswith("checkpoint-manifest.json"):return manifest
                return b"tampER"
            with self.assertRaisesRegex(m.Refused,"mismatch"):
                m.stage(destination,getter=fake)
            self.assertFalse(destination.exists())
    def test_destination_already_exists_refused_before_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(m.Refused,"destination"):
                m.stage(Path(td),getter=lambda **kwargs:None)
if __name__=="__main__":unittest.main()
