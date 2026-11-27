"""Offline parser regression fixtures, not measured chain evidence."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from eth_abi import encode
from sse_challenge import keccak256
import sse_v4_terms as t
import sse_v4_verify_parity as v


class ParityVerifierTest(unittest.TestCase):
    def fixture(self):
        market, ledger = "0x" + "ab"*20, "0x" + "cd"*20
        h = bytes.fromhex("11"*32)
        q = ("0x"+"aa"*20, 2, 3, 3, 4, 2, 1, 1000, h, h, h, 100, 10, 0)
        b = ("0x"+"bb"*20, False, 3, 2000, 100, h, h)
        terms = (86400, 600, 100, 100, 1000, 86400, 20, 150, True, False)
        raw = encode(["uint256","address","uint256","uint256",
                      t.REQUEST_TUPLE,t.BID_TUPLE,t.TERMS_TUPLE"],
                     [31340,market,1,0,q,b,terms])
        return dict(TERMS=raw, TERMS_HASH=keccak256(raw),
                    LEDGER=bytes.fromhex(ledger[2:]),
                    MARKET_DOMAIN=t.domain_separator(t.MARKET_NAME,31340,market),
                    LEDGER_DOMAIN=t.domain_separator(t.LEDGER_NAME,31340,ledger))

    @staticmethod
    def log(fields):
        return "\n".join("  V4_PARITY_"+k+": 0x"+value.hex()
                         for k,value in fields.items())

    def test_valid_fixture(self):
        result = v.verify_exports(self.log(self.fixture()))
        self.assertEqual(result["chainId"],31340)
        self.assertEqual(result["leaseId"],1)
        self.assertTrue(all(result["checks"].values()))

    def test_reject_tampered_commitments(self):
        for key in ("TERMS_HASH","MARKET_DOMAIN","LEDGER_DOMAIN","LEDGER"):
            fields = self.fixture()
            fields[key] = bytes([fields[key][0]^1])+fields[key][1:]
            with self.subTest(key=key), self.assertRaises(ValueError):
                v.verify_exports(self.log(fields))

    def test_reject_missing_duplicate_malformed_and_unknown(self):
        fields = self.fixture()
        valid = self.log(fields)
        for bad in (self.log({k:x for k,x in fields.items() if k!="LEDGER"}),
                    valid+"\n"+valid,
                    valid+"\nV4_PARITY_UNKNOWN: 0x00",
                    valid+"\nV4_PARITY_TERMS: broken",
                    self.log(dict(fields, TERMS=b"\x00"))):
            with self.assertRaises(ValueError):
                v.verify_exports(bad)


if __name__ == "__main__":
    unittest.main()
