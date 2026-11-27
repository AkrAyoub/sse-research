#!/usr/bin/env python3
"""SSE V4 persistent role agent: keeper, consumer, provider, monitor.

SOURCE-ONLY (2026-11-27): never executed. One process may run several roles
for one wallet (multi-role), or one process per role/wallet.

Safety model
  * Planners are PURE: (chain snapshot, local policy, clock) -> actions. Every
    action is re-validated by eth_call simulation at `latest` before signing,
    and every contract re-checks its own preconditions.
  * Automatic actions are zero-value only. Payable actions (awardAndFund,
    register, updateBond) are never automatic; they go through the owner
    console intent flow with explicit confirmation.
  * Provider work starts ONLY from a FINALIZED EpochStarted of a lease that is
    Active, accepted by this provider, and not previously journaled (job id =
    sha256(chain, market, leaseId, epochId, requestHash)). Bids never start work.
  * Monitors vote only from real probe results returned by the probe adapter;
    an inconclusive probe produces an abstention record, never a Failure vote.
  * Spending: per-tx max fee and rolling 24h gas budget (owner policy file).
    Any UNKNOWN journal entry for the wallet blocks further sends.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import sse_v4_abi as abi
import sse_v4_state as st
import sse_v4_terms as terms

ROLES = ("keeper", "consumer", "provider", "monitor")


# ---------------------------------------------------------------- policy
def load_policy(path):
    p = st.read_json(path, 65536)
    st.require(isinstance(p, dict) and p.get("schema") == "SSE_V4_AGENT_POLICY_V1", "wrong policy schema")
    roles = p.get("roles")
    st.require(isinstance(roles, list) and roles and set(roles) <= set(ROLES), "roles must be a subset of " + str(ROLES))
    st.require(st.ADDR.fullmatch(p.get("wallet", "").lower()), "wallet address required")
    spend = p.get("spending", {})
    for k in ("maxFeePerGasWei", "maxPriorityFeePerGasWei", "maxGasPerTx", "dailyGasWeiBudget"):
        st.require(type(spend.get(k)) is int and spend[k] > 0, "spending." + k + " required (owner authorization)")
    p["wallet"] = p["wallet"].lower()
    return p


# ------------------------------------------------------------- planners
def _act(module, call, why, kind, key=""):
    mod, data, value = call
    st.require(value == 0, "automatic actions must be zero-value")
    # `key` distinguishes legitimately repeated identical calls (e.g. advance per round).
    return {"module": mod, "calldata": data, "value": 0, "reason": why, "kind": kind, "key": key}


def plan_keeper(snapshot, now, head):
    """Deterministic permissionless transitions; safe for anyone to send."""
    out = []
    for lid, b in snapshot["leases"].items():
        l, phase = b["lease"], b["phase"]
        if phase == "PendingDraw":
            if head > l["entropyBlock"] + 256:
                out.append(_act("market", abi.lease_call("cancelExpiredDraw", lid), "entropy expired", "keeper"))
            elif head > l["entropyBlock"]:
                out.append(_act("market", abi.lease_call("drawCommittee", lid), "entropy available", "keeper"))
        elif phase == "Forming":
            a = b["assignment"]
            if a["phaseName"] == "Ready":
                out.append(_act("market", abi.lease_call("activateCommittee", lid), "standby ready", "keeper"))
            elif a["phaseName"] == "Expired":
                out.append(_act("market", abi.lease_call("cancelUnformed", lid), "standby exhausted", "keeper"))
            elif a["phaseName"] == "Confirming" and now > a["deadline"]:
                out.append(_act("standby", abi.standby_call("advance", lid), "confirmation round over", "keeper",
                                key=str(a["deadline"])))
        if phase in ("PendingDraw", "Forming", "Active") and not l["providerAccepted"] and now > l["acceptDeadline"]:
            out.append(_act("market", abi.lease_call("cancelUnaccepted", lid), "provider never accepted", "keeper"))
        if phase == "Active":
            for e in b["epochs"]:
                if not e["market"]["accounted"] and now > e["votes"]["monitoringClose"] and e["id"] == l["closedEpochs"]:
                    out.append(_act("market", abi.epoch_call("finalizeEpoch", lid, e["id"]), "monitoring closed", "keeper"))
            if (l["providerAccepted"] and l["nextEpoch"] == l["closedEpochs"] and
                    (l["nextEpoch"] == l["maxEpochs"] or now > l["lastProgressAt"] + l["idleSeconds"])):
                out.append(_act("market", abi.lease_call("forceCloseIdle", lid), "completed or idle", "keeper"))
        for e in b["epochs"]:
            s = e["science"]
            if e["market"]["exists"] and not s["evidenceClosed"] and now > e["market"]["evidenceClose"]:
                out.append(_act("market", abi.epoch_call("closeEpochEvidence", lid, e["id"]), "evidence window over", "keeper"))
    return out


def self_keep_scope(snapshot, policy):
    """Design D-09 self-keeping: with no on-chain keeper bounty, a consumer or
    provider (not a keeper) advances ONLY leases where it is the consumer or
    provider, and only if the owner set policy selfKeep=true."""
    roles = set(policy["roles"])
    if policy.get("selfKeep") is not True or "keeper" in roles or not roles & {"consumer", "provider"}:
        return dict(snapshot, leases={})
    me = policy["wallet"]
    return dict(snapshot, leases={lid: b for lid, b in snapshot["leases"].items()
                                  if me in (b["lease"]["consumer"], b["lease"]["provider"])})


def plan_consumer(snapshot, policy, now):
    me, out = policy["wallet"], []
    plans = policy.get("consumer", {}).get("epochRequests", {})
    for lid, b in snapshot["leases"].items():
        l = b["lease"]
        if l["consumer"] != me or b["phase"] != "Active" or not l["providerAccepted"]:
            continue
        if l["nextEpoch"] == l["closedEpochs"] and l["nextEpoch"] < l["maxEpochs"]:
            hashes = plans.get(str(lid), [])
            acc = b["accounting"]
            if l["nextEpoch"] < len(hashes) and acc["exposure"] + l["epochFee"] <= acc["budget"] \
                    and now <= l["lastProgressAt"] + l["idleSeconds"]:
                out.append(_act("market", abi.start_epoch(lid, hashes[l["nextEpoch"]]),
                                "owner-planned epoch within exposure budget", "consumer"))
    return out


def plan_provider(snapshot, policy, now, jobs):
    """Accept only exact, locally approved offers; enqueue finalized admitted epochs."""
    me, out, new_jobs = policy["wallet"], [], []
    approved = {o.lower() for o in policy.get("provider", {}).get("approvedOfferHashes", [])}
    for lid, b in snapshot["leases"].items():
        l = b["lease"]
        if l["provider"] != me:
            continue
        if (not l["providerAccepted"] and b["phase"] in ("PendingDraw", "Forming", "Active")
                and now <= l["acceptDeadline"] and l["offerHash"] in approved
                and b.get("termsHashRecomputed") == l["termsHash"]):
            out.append(_act("market", abi.accept_lease(lid, l["termsHash"]), "offer approved, terms verified", "provider"))
        if b["phase"] != "Active" or not l["providerAccepted"]:
            continue
        for e in b["epochs"]:
            m = e["market"]
            jid = job_id(snapshot["market"], lid, e["id"], m["requestHash"])
            if m["exists"] and not m["accounted"] and jid not in jobs and now <= e["votes"]["responseDeadline"]:
                new_jobs.append({"jobId": jid, "leaseId": lid, "epochId": e["id"], "requestHash": m["requestHash"],
                                 "profileHash": l["profileHash"], "artifactCommitment": l["artifactCommitment"],
                                 "responseDeadline": e["votes"]["responseDeadline"]})
    return out, new_jobs


def plan_monitor(snapshot, policy, now):
    me, out = policy["wallet"], []
    allow = policy.get("monitor", {}).get("autoConfirm", False)
    for lid, b in snapshot["leases"].items():
        a = b.get("assignment")
        if b["phase"] == "Forming" and allow and a and a["phaseName"] == "Confirming" and now <= a["deadline"]:
            if me in a["primary"] and me not in b.get("confirmedByMe", ()):
                out.append(_act("standby", abi.standby_call("confirm", lid), "active seat, policy autoConfirm", "monitor"))
    return out


def job_id(market, lid, eid, request_hash):
    return hashlib.sha256(json.dumps([st.CHAIN_ID, market, lid, eid, request_hash]).encode()).hexdigest()


def vote_actions(results, policy):
    """Translate REAL probe results into votes. results: list of dicts with
    leaseId, epochId, verdict in {"success","qualified_failure","inconclusive"},
    evidenceHash (commitment to archived raw probe evidence)."""
    out, abstain = [], []
    for r in results:
        if r["verdict"] == "success":
            out.append(_act("ledger", abi.submit_vote_direct(r["leaseId"], r["epochId"], 1, r["evidenceHash"]),
                            "probe success", "monitor"))
        elif r["verdict"] == "qualified_failure" and policy.get("monitor", {}).get("allowFailureVotes", False):
            out.append(_act("ledger", abi.submit_vote_direct(r["leaseId"], r["epochId"], 2, r["evidenceHash"]),
                            "qualified negative evidence under committed policy", "monitor"))
        else:
            abstain.append({"leaseId": r["leaseId"], "epochId": r["epochId"], "reason": r.get("reason", "inconclusive")})
    return out, abstain


# ------------------------------------------------------------- snapshot
def snapshot(reader, manifest, lease_ids, wallet):
    snap = {"market": manifest["modules"]["market"], "leases": {}}
    for lid in sorted(lease_ids):
        b = reader.lease_bundle(lid)
        l = b["lease"]
        try:
            q = reader.request(l["requestId"])
            bid = reader.bids(l["requestId"], l["bidIndex"], 1)[0]
            bid.pop("index", None)
            b["termsHashRecomputed"] = None  # filled by provider policy with locally stored terms
        except (ValueError, IndexError):
            q = bid = None
        b["request"], b["bid"] = q, bid
        if b.get("assignment") and wallet:
            b["confirmedByMe"] = [wallet] if reader._v("standby", "confirmed(uint256,address)", ("uint256", "address"),
                                                       (lid, wallet), ("bool",))[0] else []
        snap["leases"][lid] = b
    return snap


def verify_terms(bundle, market, chain_id, local_terms):
    """Provider-side: recompute termsHash from public views + the consumer's
    Terms (decoded from the awardAndFund calldata or the consumer's offer)."""
    q, bid = bundle["request"], bundle["bid"]
    if q is None or bid is None or local_terms is None:
        return None
    h = terms.terms_hash(chain_id, market, bundle["leaseId"], bundle["lease"]["bidIndex"], q, bid, local_terms)
    return "0x" + h.hex()


def provider_response_actions(jobs, manifest, sender):
    """Sign and relay the provider response for finished jobs (once per job).
    The response hash commits to the delivered output manifest; it authenticates
    origin and context, NOT SLA correctness."""
    market = manifest["modules"]["market"]
    domain = terms.domain_separator(terms.MARKET_NAME, st.CHAIN_ID, market)
    out = []
    for j in jobs.values():
        if j.get("state") == "DONE" and j.get("responseHash") and not j.get("responseRelayed"):
            d = terms.response_digest(domain, j["leaseId"], j["epochId"], j["requestHash"], j["responseHash"])
            out.append(_act("market", abi.authenticate_response(j["leaseId"], j["epochId"], j["responseHash"],
                                                                 sender.sign_digest(d)),
                            "job finished; relay signed response", "provider"))
    return out


# ---------------------------------------------------------------- sender
class Sender:
    """Owner-local signing with journal-before-broadcast. The key never leaves
    the eth_account LocalAccount object; it is never logged or serialized."""

    def __init__(self, ask, manifest, policy, account, journal):
        self.ask, self.m, self.p, self.acct, self.j = ask, manifest["modules"], policy, account, journal
        st.require(account.address.lower() == policy["wallet"], "unlocked key does not match policy wallet")

    def _gas_spent_24h(self, now):
        total = 0
        for e in self.j.entries():
            if e["sender"] == self.p["wallet"] and now - e.get("signedAt", 0) < 86400:
                total += e.get("maxCostWei", 0)
        return total

    def send(self, action, now):
        sp = self.p["spending"]
        st.require(not self.j.blocking(self.p["wallet"]), "unresolved journal entry: reconcile before sending")
        target = self.m[action["module"]]
        task = st.Journal.task_id(target, action["calldata"], 0, action.get("key", ""))
        prior = [e for e in self.j.find_task(task) if e.get("status") != "FINALIZED_REVERTED"]
        if prior:
            return {"skipped": "task already journaled", "taskId": task}
        call = {"from": self.p["wallet"], "to": target, "data": action["calldata"], "value": "0x0"}
        self.ask("eth_call", [call, "latest"])  # raises on revert -> precondition not met, no send
        gas = int(self.ask("eth_estimateGas", [call]), 16) * 12 // 10
        st.require(gas <= sp["maxGasPerTx"], "gas above owner cap")
        max_cost = gas * sp["maxFeePerGasWei"]
        st.require(self._gas_spent_24h(now) + max_cost <= sp["dailyGasWeiBudget"], "daily gas budget exhausted")
        nonce = int(self.ask("eth_getTransactionCount", [self.p["wallet"], "pending"]), 16)
        tx = {"chainId": st.CHAIN_ID, "nonce": nonce, "to": target, "value": 0, "data": action["calldata"],
              "gas": gas, "maxFeePerGas": sp["maxFeePerGasWei"], "maxPriorityFeePerGas": sp["maxPriorityFeePerGasWei"],
              "type": 2}
        signed = self.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = "0x" + bytes(signed.hash).hex()
        path = self.j.record(self.p["wallet"], nonce, h, task, target, action["calldata"], 0, action["reason"])
        entry = st.read_json(path)
        self.j.update(entry, signedAt=int(now), maxCostWei=max_cost)
        try:
            self.ask("eth_sendRawTransaction", ["0x" + bytes(raw).hex()])
        except Exception as exc:  # noqa: BLE001 - outcome unknown; never resend automatically
            self.j.update(st.read_json(path), status="BROADCAST_ERROR_UNKNOWN", error=str(exc)[:200])
            raise
        self.j.update(st.read_json(path), status="BROADCAST")
        return {"sent": h, "nonce": nonce, "taskId": task}

    def sign_digest(self, digest):
        """EIP-712 digest signature (r||s||v) for provider responses/acks."""
        s = self.acct.unsafe_sign_hash(digest)
        return bytes(s.signature)


# ------------------------------------------------------------------ loop
class Agent:
    def __init__(self, ask, manifest, policy, state_dir, sender=None, job_runner=None, prober=None, clock=time.time):
        self.ask, self.manifest, self.policy = ask, manifest, policy
        self.cursor = st.Cursor(ask, manifest, state_dir)
        self.state_dir = st.private_dir(state_dir)
        self.sender, self.job_runner, self.prober, self.clock = sender, job_runner, prober, clock
        self.index_path = self.state_dir / "v4-index.json"
        self.jobs_path = self.state_dir / "v4-jobs.json"

    def _index(self):
        return st.read_json(self.index_path) or {"leases": [], "mine": []}

    def _interesting(self, ev, idx):
        me = self.policy["wallet"]
        lid = ev.get("leaseId")
        if lid is None:
            return
        roles = set(self.policy["roles"])
        mine = (ev.get("provider") == me or ev.get("monitor") == me or ev.get("replacement") == me or
                (ev["event"] == "SeatsReserved" and me in ev["ordered"]))
        if "keeper" in roles or mine:
            if lid not in idx["leases"]:
                idx["leases"].append(lid)
        if ev["event"] == "LeaseFunded" and ev.get("provider") == me:
            # Remember the funding transaction so the provider can decode the
            # consumer's Terms from calldata (authenticated later by termsHash).
            idx.setdefault("fundingTx", {})[str(lid)] = ev["transactionHash"]
        if ev["event"] == "LeaseFunded":
            # consumer is not indexed in the event; resolved from lease view in step()
            if lid not in idx["leases"] and "consumer" in roles:
                idx["leases"].append(lid)

    def _decoded_terms(self, idx, lid, lease):
        """Terms from the finalized funding transaction's calldata, cached in the
        index. Only direct EOA calls to the market decode; a consumer using a
        contract wallet must hand the provider its Terms (policy leaseTerms).
        Never trusted alone: plan_provider accepts only if the recomputed
        termsHash equals the on-chain lease.termsHash."""
        key = str(lid)
        cache = idx.setdefault("decodedTerms", {})
        if key in cache:
            return cache[key]
        tx_hash = idx.get("fundingTx", {}).get(key)
        if not tx_hash:
            return None
        try:
            tx = self.ask("eth_getTransactionByHash", [tx_hash])
            if not tx:
                return None  # node has not served it (yet); retry next step, do not cache
            st.require( (tx.get("to") or "").lower() == self.manifest["modules"]["market"],
                       "funding tx is not a direct market call")
            st.require((tx.get("from") or "").lower() == lease["consumer"], "funding tx sender is not the consumer")
            rid, bid_index, t = abi.decode_award_and_fund(tx["input"])
            st.require(rid == lease["requestId"] and bid_index == lease["bidIndex"], "calldata/lease mismatch")
        except (ValueError, KeyError, TypeError):
            cache[key] = None  # remembered: fall back to policy leaseTerms
            return None
        cache[key] = t
        return t

    def step(self):
        events, new_cursor = self.cursor.poll()
        idx = self._index()
        for ev in events:
            self._interesting(ev, idx)
        reader = st.Reader(self.ask, self.manifest, tag="finalized")
        now = int(self.clock())
        head = int(self.ask("eth_blockNumber", []), 16)
        snap = snapshot(reader, self.manifest, idx["leases"], self.policy["wallet"])
        # Keep only leases that are still live (or have open evidence windows) AND,
        # unless this process is a keeper, involve this wallet.
        me = self.policy["wallet"]
        keeper = "keeper" in self.policy["roles"]
        def relevant(b):
            l = b["lease"]
            involved = me in (l["consumer"], l["provider"]) or me in b.get("members", []) or \
                me in (b.get("assignment") or {}).get("primary", []) or me in (b.get("assignment") or {}).get("standby", [])
            live = b["phase"] not in ("Closed", "Cancelled") or any(not e["science"]["evidenceClosed"] for e in b["epochs"])
            return live and (keeper or involved)
        snap["leases"] = {lid: b for lid, b in snap["leases"].items() if relevant(b)}
        idx["leases"] = sorted(snap["leases"])
        actions, jobs = [], st.read_json(self.jobs_path) or {}
        roles = set(self.policy["roles"])
        if "keeper" in roles:
            actions += plan_keeper(snap, now, head)
        else:
            scope = self_keep_scope(snap, self.policy)  # design D-09
            if scope["leases"]:
                actions += plan_keeper(scope, now, head)
        if "consumer" in roles:
            actions += plan_consumer(snap, self.policy, now)
        if "monitor" in roles:
            actions += plan_monitor(snap, self.policy, now)
        if "provider" in roles:
            for lid, b in snap["leases"].items():
                lt = self.policy.get("provider", {}).get("leaseTerms", {}).get(str(lid)) \
                    or self._decoded_terms(idx, lid, b["lease"])
                b["leaseId"] = lid
                b["termsHashRecomputed"] = verify_terms(b, self.manifest["modules"]["market"], st.CHAIN_ID, lt)
            acts, new_jobs = plan_provider(snap, self.policy, now, jobs)
            actions += acts
            for j in new_jobs:
                jobs[j["jobId"]] = dict(j, state="QUEUED", queuedAt=now)
            st.atomic_write_json(self.jobs_path, jobs)  # persist BEFORE any execution
            if self.job_runner:
                for jid, j in jobs.items():
                    if j["state"] == "QUEUED":
                        jobs[jid] = dict(j, state="RUNNING")
                        st.atomic_write_json(self.jobs_path, jobs)
                        jobs[jid] = dict(jobs[jid], **self.job_runner(j))  # returns state + responseHash
                        st.atomic_write_json(self.jobs_path, jobs)
            if self.sender:
                actions += provider_response_actions(jobs, self.manifest, self.sender)
        if "monitor" in roles and self.prober:
            acts, abstentions = vote_actions(self.prober(snap, now), self.policy)
            actions += acts
            log = self.state_dir / "v4-abstentions.jsonl"
            with open(log, "a") as fh:
                for a in abstentions:
                    fh.write(json.dumps(dict(a, at=now)) + "\n")
        results = []
        if self.sender:
            for e in self.sender.j.unresolved(self.policy["wallet"]):
                self.sender.j.reconcile(self.ask, e)
            for a in actions:
                try:
                    results.append(self.sender.send(a, now))
                except (st.StateError, ValueError) as exc:
                    results.append({"refused": str(exc), "action": a["reason"]})
                    if "unresolved journal" in str(exc):
                        break
        st.atomic_write_json(self.index_path, idx)
        self.cursor.commit(new_cursor)
        return {"events": len(events), "actions": actions, "results": results, "cursor": new_cursor}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--rpc", required=True, help="local node or verified RPC endpoint, e.g. http://127.0.0.1:28545")
    p.add_argument("--dry-run", action="store_true", help="plan only; never sign")
    p.add_argument("--interval", type=int, default=12)
    a = p.parse_args()
    from sse_chain_read import LocalRPC
    rpc = LocalRPC(a.rpc)
    ask = rpc.request
    manifest = st.load_manifest(a.manifest)
    policy = load_policy(a.policy)
    st.verify_deployment(ask, manifest)
    sender = None
    if not a.dry_run:
        from sse_v4_signer import unlock_account
        sender = Sender(ask, manifest, policy, unlock_account(policy), st.Journal(a.state))
    import sse_v4_adapters as adapters
    runner = adapters.make_job_runner(policy, a.state) if "provider" in policy["roles"] and not a.dry_run else None
    prober = adapters.make_prober(policy, None, a.state) if "monitor" in policy["roles"] and not a.dry_run else None
    agent = Agent(ask, manifest, policy, a.state, sender=sender, job_runner=runner, prober=prober)
    while True:
        try:
            print(json.dumps(agent.step(), default=str))
        except st.StateError as exc:
            print(json.dumps({"halted": str(exc)}))
            if "canonical" in str(exc):
                raise SystemExit(3)
        time.sleep(max(4, a.interval))


if __name__ == "__main__":
    main()
