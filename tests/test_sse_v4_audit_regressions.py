"""Static-audit regression fixtures; no live RPC or chain access."""
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sse_v4_abi as abi
import sse_v4_state as st
import sse_v4_adapters as adapters
import sse_v4_console as console
import sse_v4_provider_outputs as outputs
import sse_v4_committee_planner as planner

H = "0x" + "11" * 32
ME = "0x" + "ab" * 20
MODS = {m: "0x" + format(i+1, "040x") for i,m in enumerate(abi.MODULES)}


class AuditRegression(unittest.TestCase):
    def test_all_epochs_visible(self):
        r = st.Reader(None, {"modules": MODS})
        r.lease = lambda lid: {"phase": 4, "monitorBudgetTransferred": False, "nextEpoch": 64}
        r.accounting = lambda lid: {}
        r.assignment = lambda lid: {"phase": 0}
        r.market_epoch = r.scientific_epoch = r.ledger_epoch = lambda lid, eid: {}
        b = r.lease_bundle(1)
        self.assertEqual([e["id"] for e in b["epochs"]], list(range(64)))
        self.assertFalse(b["epochsTruncated"])

    def test_rejection_probability(self):
        space = 2**256
        attempts = min(planner.ATTEMPTS_PER_SEAT, planner.MAX_ATTEMPTS)
        self.assertEqual(planner.draw_success_probability(3, 1, 1),
                         1 - Fraction(space - space//3, space)**attempts)

    def test_manifest_method_not_shadowed(self):
        c = console.Console(None, {"modules": MODS}, "public")
        self.assertTrue(callable(c.manifest))

    def test_negative_content_length_refused(self):
        c = console.Console(None, {"modules": MODS}, "public")
        for cls in (console.make_handler(c), outputs.make_handler(None)):
            h = object.__new__(cls)
            h.path = "/"
            h.headers = {"Content-Length": "-1"}
            h._send = lambda code, *args: code
            # Neither handler may attempt reading the request body.
            self.assertEqual(h.do_POST(), 400)

    def test_missing_runtime_hashes_rejected(self):
        def ask(method, params):
            if method == "eth_chainId":
                return hex(st.CHAIN_ID)
            if method == "eth_getBlockByNumber":
                return {"number": "0x0" if params[0] == "0x0" else "0x10",
                        "hash": st.GENESIS if params[0] == "0x0" else H}
            self.fail("unexpected RPC method: " + method)
        with self.assertRaisesRegex(st.StateError, "runtime hashes"):
            st.verify_deployment(ask, {"deploymentBlock": 1, "modules": MODS})

    def test_archived_evidence_replayed_and_context_checked(self):
        approved = {"probe": "SHA256_CHAIN_8192", "failureEvidence": "conditional-quorum"}
        ph = adapters.response_hash(approved)
        policy = {"wallet": ME, "monitor": {"approvedPolicies": {ph: approved}}}
        l = {"policyHash": ph, "conditionalQuorumPolicy": True}
        v = {"exists": True, "monitoringSealed": False, "monitoringClose": 100,
             "requestHash": H, "responseHash": H, "responseAuthenticated": True}
        snap = {"leases": {1: {"members": [ME], "phase": "Active", "lease": l,
                              "epochs": [{"id": 0, "votes": v}]}}}
        with tempfile.TemporaryDirectory() as d:
            probe = adapters.make_prober(policy, None, d)
            record = {"leaseId": 1, "epochId": 0, "monitor": ME, "policyHash": ph,
                      "requestHash": H, "onchainResponseHash": H, "verdict": "success"}
            file = Path(d) / "evidence" / "1-0.json"
            st.atomic_write_json(file, record)
            with patch.object(adapters, "_post", side_effect=AssertionError("must not reprobe")):
                first = probe(snap, 10)
                self.assertEqual(first, probe(snap, 11))
                self.assertEqual(len(first), 1)
                record["requestHash"] = "0x" + "22"*32
                st.atomic_write_json(file, record)
                with self.assertRaisesRegex(st.StateError, "context mismatch"):
                    probe(snap, 12)


if __name__ == "__main__":
    unittest.main()
