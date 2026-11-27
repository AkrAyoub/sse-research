"""Provider output endpoint authorization tests (fixtures only). SOURCE-ONLY: written 2026-11-27, not executed."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from eth_account import Account
from eth_account.messages import encode_defunct
import sse_v4_provider_outputs as po
from sse_v4_adapters import response_hash
import sse_v4_state as st

MARKET = "0x" + "01" * 20
REQ = "0x" + "11" * 32


class OutputsTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        os.chmod(self.d, 0o700)
        (self.d / "outputs").mkdir(mode=0o700)
        self.out = {"schema": "fixture", "resultDigest": "sha256:" + "00" * 32}
        self.h = response_hash(self.out)
        st.atomic_write_json(self.d / "outputs" / (self.h + ".json"), self.out)
        st.atomic_write_json(self.d / "v4-jobs.json", {"j": {"leaseId": 1, "epochId": 0, "requestHash": REQ,
                                                              "state": "DONE", "responseHash": self.h}})
        self.consumer = Account.create()
        self.o = po.Outputs(None, {"modules": {"market": MARKET}}, self.d)

    def sign(self, acct, exp):
        m = encode_defunct(text=po.output_message(31340, MARKET, 1, 0, exp))
        return acct.sign_message(m).signature.hex()

    def test_compute_serves_only_matching_request(self):
        self.assertEqual(self.o.compute({"leaseId": 1, "epochId": 0, "requestHash": REQ}), self.out)
        with self.assertRaises(ValueError):
            self.o.compute({"leaseId": 1, "epochId": 0, "requestHash": "0x" + "22" * 32})

    def test_output_requires_consumer_signature_and_fresh_expiry(self):
        exp = int(time.time()) + 60
        fake = {"consumer": self.consumer.address.lower()}
        with patch.object(st.Reader, "lease", return_value=fake), patch.object(st.Reader, "__init__", return_value=None):
            r = self.o.output({"leaseId": 1, "epochId": 0, "expiry": exp, "signature": self.sign(self.consumer, exp)})
            self.assertEqual(r["responseHash"], self.h)
            other = Account.create()
            with self.assertRaises(ValueError):
                self.o.output({"leaseId": 1, "epochId": 0, "expiry": exp, "signature": self.sign(other, exp)})
            with self.assertRaises(ValueError):
                late = int(time.time()) + 3600
                self.o.output({"leaseId": 1, "epochId": 0, "expiry": late, "signature": self.sign(self.consumer, late)})

    def test_corrupted_output_refused(self):
        st.atomic_write_json(self.d / "outputs" / (self.h + ".json"), {"tampered": True})
        with self.assertRaises(ValueError):
            self.o.compute({"leaseId": 1, "epochId": 0, "requestHash": REQ})


if __name__ == "__main__":
    unittest.main()
