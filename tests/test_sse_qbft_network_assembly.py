"""Public-only four-host QBFT genesis and signed peer source assembly."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from sse_qbft_validator_identity import node_key_record
from sse_qbft_network_assembly import (
    AssemblyError, validate_roster, make_genesis_bundle, make_catalog,
    load_public, write_bundle,
)

PUBLIC=[node_key_record(i.to_bytes(32,"big"),f"validator-{i}",f"100.101.102.{i+100}")
        for i in range(1,5)]


class AssemblyTests(unittest.TestCase):
    def test_four_distinct_validator_public_identity_and_genesis(self):
        record=validate_roster(PUBLIC)
        self.assertEqual(len(record),4)
        bundle=make_genesis_bundle(PUBLIC)
        self.assertEqual(bundle["genesis.json"]["config"]["chainId"],31338)
        self.assertIn("extraData",bundle["genesis.json"])
        self.assertFalse(bundle["public-roster.json"]["privateKeysIncluded"])
        self.assertFalse(bundle["public-roster.json"]["independentHostsVerified"])

    def test_duplicate_key_and_overlay_refused(self):
        duplicate=[*PUBLIC[:3],PUBLIC[0]]
        with self.assertRaises(AssemblyError):
            validate_roster(duplicate)
        other={**PUBLIC[3],"overlayIPv4":PUBLIC[0]["overlayIPv4"]}
        with self.assertRaises(AssemblyError):
            validate_roster([*PUBLIC[:3],other])

    def test_signable_catalog_is_bound_to_actual_hash_and_revision(self):
        draft=make_catalog(PUBLIC,genesis_hash="0x"+"ab"*32,
                           revision="a"*40,issued=1795000000)
        self.assertEqual(draft["chainId"],31338)
        self.assertEqual(len(draft["nodes"]),4)
        self.assertEqual(draft["expiresAt"]-draft["issuedAt"],86400)
        with self.assertRaises(AssemblyError):
            make_catalog(PUBLIC,genesis_hash="0x"+"ab"*32,
                         revision="main",issued=1795000000)

    def test_source_tampering_and_output_overwrite_refused(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            source=base/"validator-1.json"
            source.write_text(json.dumps(PUBLIC[0]))
            self.assertEqual(load_public(source)["nodeId"],"validator-1")
            source.write_text(json.dumps({**PUBLIC[0],"validatorAddress":"0x"+"ab"*20}))
            with self.assertRaises(AssemblyError):
                load_public(source)
            with self.assertRaises(AssemblyError):
                write_bundle(base,{"validator-1.json":{}})
            write_bundle(base,{"genesis.json":{"kind":"fixture"}})
            with self.assertRaises(AssemblyError):
                write_bundle(base,{"genesis.json":{"kind":"overwrite"}})

if __name__=="__main__":
    unittest.main()
