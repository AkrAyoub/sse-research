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

    def resource_fixture(self):
        from sse_v4_adapters import response_hash, endpoint_hash
        r = dict(cpuCores=1, memoryMiB=512, storageMiB=0)
        p = dict(schema="SSE_V4_PROFILE_V1", service="SHA256_CHAIN_8192",
                 resources=r, sla=dict(responseSeconds=100, maxRuntimeSeconds=30))
        o = dict(schema="SSE_V4_OFFER_V1", services=["SHA256_CHAIN_8192"],
                 resources=dict(r), maxConcurrentLeases=1, endpointUrl="https://provider.example")
        ph, oh = response_hash(p), response_hash(o)
        cfg = dict(profiles={ph:p}, offers={oh:o}, workers={"1":dict(
            imageId="sha256:"+"ab"*32, container="sse-compute-test",
            url="http://127.0.0.1:8877", dockerSocket="/run/user/1001/docker.sock")},
            approvedOfferHashes=[oh], approvedTermsHashes=[H],
            capacity=dict(cpuCores=1, memoryMiB=512, maxConcurrentLeases=1))
        l = lease(profileHash=ph, offerHash=oh, endpointHash=endpoint_hash(o["endpointUrl"]), responseSeconds=100)
        return {"wallet":ME,"provider":cfg}, l

    def test_provider_never_accepts_unapproved_or_unverified_terms(self):
        policy, l = self.resource_fixture()
        cfg = policy["provider"]
        snap = {"market": MODS["market"], "leases": {1: bundle("Forming", l, termsHashRecomputed=H)}}
        cfg["approvedOfferHashes"] = []
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[0], [])
        cfg["approvedOfferHashes"] = [l["offerHash"]]
        cfg["approvedTermsHashes"] = []
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[0], [])
        cfg["approvedTermsHashes"] = [H]
        snap["leases"][1]["termsHashRecomputed"] = "0x" + "22" * 32
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[0], [])
        snap["leases"][1]["termsHashRecomputed"] = H
        self.assertEqual(len(agent.plan_provider(snap, policy, now=10, jobs={})[0]), 1)
        cfg["workers"] = {}
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[0], [])

    def test_provider_jobs_only_for_active_accepted(self):
        policy, l = self.resource_fixture()
        snap = {"market": MODS["market"], "leases": {1: bundle("Active", l, [epoch(0)], termsHashRecomputed=H)}}
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[1], [])
        l["providerAccepted"] = True
        _, jobs = agent.plan_provider(snap, policy, now=10, jobs={})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["offerHash"], l["offerHash"])
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={jobs[0]["jobId"]: jobs[0]})[1], [])
        snap["leases"][2] = bundle("Active", dict(l), [epoch(0)], termsHashRecomputed=H)
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[1], [])

    def test_provider_worker_inspection_and_output(self):
        from unittest.mock import patch
        import sse_v4_adapters as adapters
        from compute_workload import compute_result
        policy, l = self.resource_fixture()
        w = policy["provider"]["workers"]["1"]
        job = dict(l, leaseId=1, epochId=0, requestHash=H, responseDeadline=10**12,
                   workerKey=agent.worker_key(w), workerBindingHash=adapters.response_hash(w))
        inspection = {"containerId":"test-container", "trustedHardwareAttestation":False}
        with tempfile.TemporaryDirectory() as d:
            run = adapters.make_job_runner(policy, d)
            with patch.object(adapters, "require_local_owner_rootless_socket"), \
                 patch.object(adapters, "inspect_container", return_value=inspection) as inspect, \
                 patch.object(adapters, "_post", return_value=compute_result(1,0,H)) as post:
                result = run(job)
                self.assertEqual(result["state"], "DONE")
                self.assertEqual(inspect.call_count, 2)
                self.assertTrue(inspect.call_args.kwargs["strict_hardening"])
                self.assertFalse(result["resourceObservation"]["trustedHardwareAttestation"])
                post.assert_called_once()
            with patch.object(adapters, "require_local_owner_rootless_socket"), \
                 patch.object(adapters, "inspect_container", side_effect=ValueError("quota mismatch")), \
                 patch.object(adapters, "_post") as post:
                self.assertEqual(run(job)["state"], "REFUSED_RESOURCE_BINDING")
                post.assert_not_called()
            with patch.object(adapters, "require_local_owner_rootless_socket"), \
                 patch.object(adapters, "inspect_container", side_effect=[inspection, dict(inspection, containerId="changed")]), \
                 patch.object(adapters, "_post", return_value=compute_result(1,0,H)):
                with self.assertRaisesRegex(ValueError, "worker changed"):
                    run(job)

    def test_parallel_dispatch_persists_before_work_and_quarantines_failure(self):
        from threading import Barrier
        from copy import deepcopy
        policy, l = self.resource_fixture()
        cfg = policy["provider"]
        from sse_v4_adapters import response_hash
        offer = dict(cfg["offers"][l["offerHash"]], resources=dict(cpuCores=2, memoryMiB=1024, storageMiB=0),
                     maxConcurrentLeases=2)
        oh = response_hash(offer)
        cfg["offers"][oh] = offer
        cfg["approvedOfferHashes"] = [oh]
        cfg["capacity"] = dict(cpuCores=2, memoryMiB=1024, maxConcurrentLeases=2)
        cfg["workers"]["2"] = dict(cfg["workers"]["1"], container="sse-compute-second", url="http://127.0.0.1:8878")
        l.update(offerHash=oh, providerAccepted=True)
        snap = {"market":MODS["market"], "leases":{
            i:bundle("Active", dict(l), [epoch(0)], termsHashRecomputed=H) for i in (1,2)}}
        _, planned = agent.plan_provider(snap, policy, 10, {})
        self.assertEqual(len(planned), 2)
        eligible = {j["jobId"]:j for j in planned}
        jobs = {jid:dict(j,state="QUEUED") for jid,j in eligible.items()}
        writes = []
        barrier = Barrier(2)
        def run(j):
            self.assertEqual(writes[-1][j["jobId"]]["state"], "RUNNING")
            barrier.wait(timeout=3)
            if j["leaseId"] == 1:
                raise TimeoutError("uncertain execution")
            return dict(state="DONE", responseHash=H, finishedAt=11, resourceObservation={"test":True})
        agent.dispatch_provider_jobs(jobs, eligible, run, lambda d:writes.append(deepcopy(d)), lambda:10, 2)
        self.assertEqual({j["leaseId"]:j["state"] for j in jobs.values()}, {1:"EXECUTION_UNKNOWN",2:"DONE"})
        self.assertTrue(agent.worker_quarantined(agent.worker_key(cfg["workers"]["1"]), jobs))
        self.assertFalse(agent.worker_quarantined(agent.worker_key(cfg["workers"]["2"]), jobs))
        self.assertTrue(agent.worker_quarantined(agent.worker_key(cfg["workers"]["2"]), {"legacy":{"state":"RUNNING"}}))
        agent.dispatch_provider_jobs(jobs, eligible, lambda j:self.fail("must never repeat"), lambda d:None, lambda:10, 2)

    def test_completed_response_callback_precedes_slow_worker(self):
        from threading import Event
        from copy import deepcopy
        release = Event()
        policy, l = self.resource_fixture()
        cfg = policy["provider"]
        from sse_v4_adapters import response_hash
        offer = dict(cfg["offers"][l["offerHash"]],
                     resources=dict(cpuCores=2, memoryMiB=1024, storageMiB=0),
                     maxConcurrentLeases=2)
        oh = response_hash(offer)
        cfg["offers"][oh] = offer
        cfg["approvedOfferHashes"] = [oh]
        cfg["capacity"] = dict(cpuCores=2, memoryMiB=1024, maxConcurrentLeases=2)
        cfg["workers"]["2"] = dict(cfg["workers"]["1"], container="sse-compute-second",
                                    url="http://127.0.0.1:8878")
        l.update(offerHash=oh, providerAccepted=True)
        snap = {"market":MODS["market"], "leases":{
            i:bundle("Active", dict(l), [epoch(0)], termsHashRecomputed=H) for i in (1,2)}}
        _, planned = agent.plan_provider(snap, policy, 10, {})
        self.assertEqual(len(planned), 2)
        eligible = {j["jobId"]:j for j in planned}
        jobs = {jid:dict(j,state="QUEUED") for jid,j in eligible.items()}
        writes, completed = [], []
        def run(j):
            if j["leaseId"] == 2:
                if not release.wait(timeout=5):
                    raise TimeoutError("completion callback did not release slow worker")
            return dict(state="DONE", responseHash=H, finishedAt=11, resourceObservation={"test":True})
        def on_complete(j):
            self.assertEqual(writes[-1][j["jobId"]]["state"], "DONE")
            completed.append(j["leaseId"])
            if j["leaseId"] == 1:
                self.assertTrue(any(x["leaseId"] == 2 and x["state"] == "RUNNING" for x in jobs.values()))
                release.set()
        agent.dispatch_provider_jobs(jobs, eligible, run, lambda d:writes.append(deepcopy(d)),
                                     lambda:10, 2, on_complete=on_complete)
        self.assertEqual(completed, [1,2])
        self.assertTrue(all(j["state"] == "DONE" for j in jobs.values()))

    def test_dispatch_refuses_changed_worker_binding(self):
        policy, l = self.resource_fixture()
        l["providerAccepted"] = True
        snap = {"market":MODS["market"], "leases":{1:bundle("Active",l,[epoch(0)],termsHashRecomputed=H)}}
        _, planned = agent.plan_provider(snap, policy, 10, {})
        j = planned[0]
        jobs = {j["jobId"]:dict(j,state="QUEUED",workerBindingHash=H)}
        agent.dispatch_provider_jobs(jobs,{j["jobId"]:j},lambda j:self.fail("must not run"),
                                     lambda d:None,lambda:10,1)
        self.assertEqual(jobs[j["jobId"]]["state"],"REFUSED_RESOURCE_ADMISSION")

    def test_provider_multi_worker_capacity(self):
        from sse_v4_adapters import response_hash
        policy, l = self.resource_fixture()
        cfg = policy["provider"]
        old = cfg["offers"][l["offerHash"]]
        offer = dict(old, resources=dict(cpuCores=2, memoryMiB=1024, storageMiB=0), maxConcurrentLeases=2)
        oh = response_hash(offer)
        cfg["offers"][oh] = offer
        cfg["approvedOfferHashes"] = [oh]
        cfg["capacity"] = dict(cpuCores=2, memoryMiB=1024, maxConcurrentLeases=2)
        cfg["workers"]["2"] = dict(cfg["workers"]["1"], container="sse-compute-second", url="http://127.0.0.1:8878")
        l["offerHash"] = oh
        l["providerAccepted"] = True
        snap = {"market":MODS["market"], "leases":{
            1:bundle("Active", l, [epoch(0)], termsHashRecomputed=H),
            2:bundle("Forming", dict(l, providerAccepted=False), termsHashRecomputed=H)}}
        self.assertEqual(len(agent.plan_provider(snap, policy, 10, {})[0]), 1)
        snap["leases"][2] = bundle("Active", dict(l), [epoch(0)], termsHashRecomputed=H)
        self.assertEqual(len(agent.plan_provider(snap, policy, 10, {})[1]), 2)
        cfg["capacity"]["memoryMiB"] = 1023
        self.assertEqual(agent.plan_provider(snap, policy, 10, {}), ([], []))
        cfg["capacity"]["memoryMiB"] = 1024
        cfg["workers"]["2"]["url"] = cfg["workers"]["1"]["url"]
        self.assertEqual(agent.plan_provider(snap, policy, 10, {}), ([], []))

    def test_provider_single_lease_admission_and_release(self):
        policy, l = self.resource_fixture()
        policy["provider"]["workers"]["2"] = dict(policy["provider"]["workers"]["1"], container="sse-compute-second", url="http://127.0.0.1:8878")
        snap = {"market": MODS["market"], "leases": {
            1: bundle("Forming", l, termsHashRecomputed=H),
            2: bundle("Forming", dict(l), termsHashRecomputed=H)}}
        self.assertEqual(len(agent.plan_provider(snap, policy, now=10, jobs={})[0]), 1)
        l["providerAccepted"] = True
        self.assertEqual(agent.plan_provider(snap, policy, now=10, jobs={})[0], [])
        snap["leases"][1]["phase"] = "Closed"
        self.assertEqual(len(agent.plan_provider(snap, policy, now=10, jobs={})[0]), 1)

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

    def test_terms_check_validates_types_before_reading_chain(self):
        c = console.Console(lambda m, p: None, {"modules": MODS}, "public")
        good = {f: (False if k == "bool" else 1) for f, k in abi.TERMS_FIELDS}
        for bad in (dict(good, acceptSeconds=2 ** 64), dict(good, conditionalQuorumPolicy=1),
                    dict(good, reservationFee=-1), dict(good, idleSeconds="1")):
            with self.assertRaises(ValueError):
                c.terms_check({"leaseId": 1, "terms": bad})
        with self.assertRaises(ValueError):
            c.terms_check({"leaseId": 0, "terms": good})

    def test_manifests_are_canonical_and_fail_closed(self):
        c = console.Console(lambda m, p: None, {"modules": MODS}, "public")
        prof = {"service": "SHA256_CHAIN_8192", "cpuCores": 1, "memoryMiB": 512, "storageMiB": 0,
                "responseSeconds": 100, "maxRuntimeSeconds": 60}
        a = c.manifest("profile", prof)
        b = c.manifest("profile", dict(reversed(list(prof.items()))))
        self.assertEqual(a["hash"], b["hash"])  # key order does not matter
        with self.assertRaises(ValueError):
            c.manifest("profile", dict(prof, service="ARBITRARY_CODE"))
        with self.assertRaises(ValueError):
            c.manifest("profile", dict(prof, cpuCores=0))
        offer = {"endpointUrl": "https://provider.example/sse", "services": ["SHA256_CHAIN_8192"], "cpuCores": 2,
                 "memoryMiB": 2048, "storageMiB": 0, "maxConcurrentLeases": 4}
        o = c.manifest("offer", offer)
        from sse_v4_adapters import endpoint_hash
        self.assertEqual(o["endpointHash"], endpoint_hash("https://provider.example/sse"))
        with self.assertRaises(ValueError):
            c.manifest("offer", dict(offer, endpointUrl="http://127.0.0.1:8881"))  # offers must be public https
        with self.assertRaises(ValueError):
            c.manifest("policy", {"probe": "SHA256_CHAIN_8192", "probeTimeoutSeconds": 30, "failureEvidence": "vote"})
        with self.assertRaises(ValueError):
            c.manifest("other", {})

    def test_unknown_intent_rejected(self):
        class FakeReader:
            pass
        c = console.Console(lambda m, p: {"number": "0x1", "hash": H}, {"modules": MODS}, "public")
        c._reader = lambda f: (FakeReader(), "latest")
        with self.assertRaises(ValueError):
            c.intent("selfdestruct", {})


if __name__ == "__main__":
    unittest.main()
