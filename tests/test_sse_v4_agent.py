"""V4 ABI/agent/console unit tests with synthetic snapshots (TEST FIXTURES ONLY).
SOURCE-ONLY: written 2026-11-27, not executed."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from eth_abi import encode
import sse_v4_abi as abi
import sse_v4_agent as agent
import sse_v4_console as console

ME = "0x" + "ab" * 20
OTHER = "0x" + "cd" * 20
H = "0x" + "11" * 32
MODS = {m: "0x" + format(i + 1, "040x") for i, m in enumerate(abi.MODULES)}


def lease(**kw):
    l = {f: 0 for f, _ in abi.LEASE_FIELDS}
    l.update(consumer=OTHER, provider=ME, providerAccepted=False, offerHash=H, termsHash=H, entropyBlock=100,
             acceptDeadline=1000, idleSeconds=600, lastProgressAt=0, maxEpochs=3, epochFee=100,
             profileHash=H, artifactCommitment=H)
    l.update(kw)
    return l


def bundle(phase, l, epochs=(), assignment=None, **kw):
    b = {"lease": l, "phase": phase, "epochs": list(epochs),
         "accounting": {"exposure": 0, "budget": 150}}
    if assignment:
        b["assignment"] = assignment
    b.update(kw)
    return b


def epoch(i, accounted=False, monitoring_close=500, response_deadline=400, evidence_closed=False, evidence_close=900):
    return {"id": i, "market": {"exists": True, "accounted": accounted, "requestHash": H, "evidenceClose": evidence_close},
            "votes": {"monitoringClose": monitoring_close, "responseDeadline": response_deadline},
            "science": {"evidenceClosed": evidence_closed}}


class AbiTest(unittest.TestCase):
    def test_event_roundtrip(self):
        name = "EpochStarted"
        sig = abi.event_signature(name)
        topic0 = [t for t, n in abi.TOPICS.items() if n == name][0]
        log = {"address": MODS["market"], "topics": [topic0, "0x" + encode(["uint256"], [7]).hex(),
               "0x" + encode(["uint256"], [2]).hex()],
               "data": "0x" + encode(["bytes32", "uint64", "uint64", "uint64"], [bytes(32), 1, 2, 3]).hex(),
               "blockNumber": "0x10", "blockHash": H, "transactionHash": H, "logIndex": "0x0"}
        ev = abi.decode_log(log, MODS)
        self.assertEqual((ev["leaseId"], ev["epochId"], ev["evidenceClose"]), (7, 2, 3))
        self.assertIn("EpochStarted(", sig)
        log["address"] = MODS["board"]
        self.assertIsNone(abi.decode_log(log, MODS))  # wrong emitter is ignored

    def test_award_value_from_chain_data(self):
        terms = {f: 1 for f, _ in abi.TERMS_FIELDS}
        terms.update(conditionalQuorumPolicy=True, responseAdmitsReceipt=False)
        _, _, v = abi.award_and_fund(1, 0, terms, {"seats": 4, "perReportReward": 10}, {"epochFee": 100, "epochs": 3})
        self.assertEqual(v, 420)

    def test_struct_range_checks(self):
        r = {f: 0 for f, _ in abi.REQUEST_INPUT_FIELDS}
        r.update(profileHash=H, policyHash=H, artifactCommitment=H, seats=70000)
        with self.assertRaises(ValueError):
            abi.create_request(r)


class PlannerTest(unittest.TestCase):
    def test_keeper_draw_and_expiry(self):
        snap = {"market": MODS["market"], "leases": {1: bundle("PendingDraw", lease())}}
        acts = agent.plan_keeper(snap, now=10, head=101)
        self.assertTrue(any("drawCommittee" in a["reason"] or a["reason"] == "entropy available" for a in acts))
        acts = agent.plan_keeper(snap, now=10, head=400)
        self.assertEqual(acts[0]["reason"], "entropy expired")

    def test_keeper_advance_keyed_by_round(self):
        a = {"phaseName": "Confirming", "deadline": 50, "primary": [], "standby": []}
        snap = {"market": MODS["market"], "leases": {1: bundle("Forming", lease(), assignment=a)}}
        acts = [x for x in agent.plan_keeper(snap, now=60, head=0) if x["module"] == "standby"]
        self.assertEqual(acts[0]["key"], "50")

    def test_provider_never_accepts_unapproved_or_unverified_terms(self):
        policy = {"wallet": ME, "provider": {"approvedOfferHashes": []}}
        snap = {"market": MODS["market"], "leases": {1: bundle("Forming", lease(), termsHashRecomputed=H)}}
        acts, _ = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(acts, [])
        policy["provider"]["approvedOfferHashes"] = [H]
        snap["leases"][1]["termsHashRecomputed"] = "0x" + "22" * 32
        acts, _ = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(acts, [])
        snap["leases"][1]["termsHashRecomputed"] = H
        acts, _ = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(len(acts), 1)

    def test_provider_jobs_only_for_active_accepted(self):
        policy = {"wallet": ME, "provider": {}}
        l = lease(providerAccepted=False)
        snap = {"market": MODS["market"], "leases": {1: bundle("Active", l, [epoch(0)])}}
        _, jobs = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(jobs, [])
        snap["leases"][1]["lease"]["providerAccepted"] = True
        _, jobs = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(len(jobs), 1)
        _, again = agent.plan_provider(snap, policy, now=10, jobs={jobs[0]["jobId"]: jobs[0]})
        self.assertEqual(again, [])  # idempotent

    def test_monitor_abstains_on_inconclusive_and_needs_policy_for_failure(self):
        res = [{"leaseId": 1, "epochId": 0, "verdict": "inconclusive", "evidenceHash": H, "reason": "timeout"},
               {"leaseId": 1, "epochId": 1, "verdict": "qualified_failure", "evidenceHash": H}]
        acts, abst = agent.vote_actions(res, {"monitor": {}})
        self.assertEqual(acts, [])
        self.assertEqual(len(abst), 2)
        acts, _ = agent.vote_actions(res, {"monitor": {"allowFailureVotes": True}})
        self.assertEqual(len(acts), 1)

    def test_consumer_respects_exposure_budget(self):
        l = lease(consumer=ME, provider=OTHER, providerAccepted=True, lastProgressAt=100)
        b = bundle("Active", l)
        b["accounting"] = {"exposure": 100, "budget": 150}
        snap = {"market": MODS["market"], "leases": {1: b}}
        pol = {"wallet": ME, "consumer": {"epochRequests": {"1": [H]}}}
        self.assertEqual(agent.plan_consumer(snap, pol, now=200), [])
        b["accounting"] = {"exposure": 0, "budget": 150}
        self.assertEqual(len(agent.plan_consumer(snap, pol, now=200)), 1)


class ConsoleTest(unittest.TestCase):
    def test_public_mode_refuses_upload(self):
        c = console.Console(lambda m, p: None, {"modules": MODS}, "public")
        with self.assertRaises(PermissionError):
            c.upload([("a.txt", b"x")])

    def test_local_upload_rejects_paths_and_commits(self):
        d = tempfile.mkdtemp()
        os.chmod(d, 0o700)
        c = console.Console(lambda m, p: None, {"modules": MODS}, "local", d)
        with self.assertRaises(ValueError):
            c.upload([("../etc/passwd", b"x")])
        with self.assertRaises(ValueError):
            c.upload([(".hidden", b"x")])
        r1 = c.upload([("b.txt", b"2"), ("a.txt", b"1")])
        r2 = c.upload([("a.txt", b"1"), ("b.txt", b"2")])
        self.assertEqual(r1["artifactCommitment"], r2["artifactCommitment"])  # order independent

    def test_unknown_intent_rejected(self):
        class FakeReader:
            pass
        c = console.Console(lambda m, p: {"number": "0x1", "hash": H}, {"modules": MODS}, "public")
        c._reader = lambda f: (FakeReader(), "latest")
        with self.assertRaises(ValueError):
            c.intent("selfdestruct", {})


if __name__ == "__main__":
    unittest.main()
