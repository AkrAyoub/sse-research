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

    def test_award_calldata_decodes_back_to_terms(self):
        t = {f: (True if k == "bool" else 7) for f, k in abi.TERMS_FIELDS}
        _, data, _ = abi.award_and_fund(5, 2, t, {"seats": 4, "perReportReward": 1}, {"epochFee": 1, "epochs": 1})
        rid, bi, back = abi.decode_award_and_fund(data)
        self.assertEqual((rid, bi, back), (5, 2, t))
        with self.assertRaises(ValueError):
            abi.decode_award_and_fund("0x12345678" + data[10:])
        with self.assertRaises(ValueError):
            abi.decode_award_and_fund(data[:40])

    def test_provider_decodes_terms_only_from_consumer_direct_call(self):
        import types
        t = {f: (False if k == "bool" else 3) for f, k in abi.TERMS_FIELDS}
        _, data, _ = abi.award_and_fund(9, 1, t, {"seats": 4, "perReportReward": 0}, {"epochFee": 1, "epochs": 1})
        l = lease(requestId=9, bidIndex=1)

        def run(tx):
            fake = types.SimpleNamespace(ask=lambda m, p: tx, manifest={"modules": MODS})
            idx = {"fundingTx": {"4": "0x" + "22" * 32}}
            return agent.Agent._decoded_terms(fake, idx, 4, l), idx
        good = {"to": MODS["market"], "from": OTHER, "input": data}
        self.assertEqual(run(good)[0], t)
        self.assertIsNone(run(dict(good, to=MODS["board"]))[0])        # not a direct market call
        self.assertIsNone(run(dict(good, **{"from": ME}))[0])          # sender is not the consumer
        self.assertIsNone(run(dict(good, input="0x" + data[10:]))[0])  # wrong selector
        got, idx = run(None)                                            # tx not served: not cached
        self.assertIsNone(got)
        self.assertNotIn("4", idx.get("decodedTerms", {}))

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

    def test_self_keep_only_own_leases_and_only_when_authorized(self):
        snap = {"market": MODS["market"], "leases": {1: bundle("PendingDraw", lease()),
                                                     2: bundle("PendingDraw", lease(consumer=OTHER, provider=OTHER))}}
        pol = {"roles": ["provider"], "wallet": ME, "selfKeep": True}
        self.assertEqual(list(agent.self_keep_scope(snap, pol)["leases"]), [1])
        self.assertEqual(agent.self_keep_scope(snap, dict(pol, selfKeep=False))["leases"], {})
        self.assertEqual(agent.self_keep_scope(snap, {"roles": ["provider"], "wallet": ME})["leases"], {})
        self.assertEqual(agent.self_keep_scope(snap, dict(pol, roles=["monitor"]))["leases"], {})
        acts = agent.plan_keeper(agent.self_keep_scope(snap, pol), now=10, head=101)
        self.assertTrue(acts and all(a["value"] == 0 for a in acts))

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

    def test_output_verify_matches_only_finalized_response_hash(self):
        from sse_v4_adapters import response_hash
        out = {"result": "0x" + "ab" * 32, "iterations": 8192}

        class R:
            def __init__(self, h):
                self.h = h

            def market_epoch(self, lid, eid):
                return {"responseHash": self.h}
        c = console.Console(lambda m, p: {"number": "0x1", "hash": H}, {"modules": MODS}, "public")
        c._meta = lambda tag: {"observedBlock": 1}
        for onchain, expected in ((response_hash(out), True), ("0x" + "00" * 32, False), (H, False)):
            c._reader = lambda f, h=onchain: (R(h), "0x1")
            self.assertIs(c.output_verify({"leaseId": 1, "epochId": 0, "output": out})["verified"], expected)
        with self.assertRaises(ValueError):
            c.output_verify({"leaseId": "1", "epochId": 0, "output": out})

    def test_output_fetch_local_only_and_endpoint_bound(self):
        body = {"providerUrl": "https://provider.example/sse", "leaseId": 1, "epochId": 0, "expiry": 1, "signature": "0x"}
        pub = console.Console(lambda m, p: None, {"modules": MODS}, "public")
        with self.assertRaises(PermissionError):
            pub.output_fetch(body)
        loc = console.Console(lambda m, p: None, {"modules": MODS}, "local")
        for bad in ("http://provider.example/sse", "https://user@host/x", "file:///etc/passwd", "http://10.0.0.1:80"):
            with self.assertRaises(ValueError):
                loc.output_fetch(dict(body, providerUrl=bad))

        class R:
            def lease(self, lid):
                return {"endpointHash": H}  # does not commit to this URL
        loc._reader = lambda f: (R(), "0x1")
        with self.assertRaises(ValueError):  # StateError is a ValueError; no network request is made
            loc.output_fetch(body)

    def test_rewards_summary_keeps_unavailable_unknown(self):
        import json as _json
        import time as _time
        d = tempfile.mkdtemp()
        latest = {"headSlot": 99, "finalizedEpoch": "2", "gapBeforeStart": False, "observedUnixNs": _time.time_ns(),
                  "attestationRewards": [{"epoch": "1", "validator": "3", "netGwei": 5},
                                         {"epoch": "2", "validator": "3", "netGwei": -2},
                                         {"epoch": "0", "available": False, "httpStatus": 404}],
                  "blockRewards": [{"slot": "98", "proposer": "3", "totalGwei": "7", "apiFinalized": False},
                                   {"slot": "99", "available": False, "httpStatus": 404}]}
        Path(d, "latest.json").write_text(_json.dumps(latest))
        r = console.Console(lambda m, p: None, {"modules": MODS}, "public", rewards_dir=d).rewards()
        self.assertEqual(r["attestationByValidator"], [{"validator": "3", "epochs": 2, "netGwei": 3}])
        self.assertEqual((r["epochsUnavailable"], r["blocksUnavailable"], r["stale"]), (["0"], 1, False))
        self.assertFalse(console.Console(lambda m, p: None, {"modules": MODS}, "public").rewards()["available"])

    def test_unknown_intent_rejected(self):
        class FakeReader:
            pass
        c = console.Console(lambda m, p: {"number": "0x1", "hash": H}, {"modules": MODS}, "public")
        c._reader = lambda f: (FakeReader(), "latest")
        with self.assertRaises(ValueError):
            c.intent("selfdestruct", {})


if __name__ == "__main__":
    unittest.main()
