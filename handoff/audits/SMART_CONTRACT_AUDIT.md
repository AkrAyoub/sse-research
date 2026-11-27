# Smart-contract audit (static) — 2026-11-27

No compilation or execution. Every property below is "Statically reviewed" at most and must be confirmed by DRV items in
handoff/planning/DEFERRED_RUNTIME_VALIDATION.md.

## 1. Findings on the pre-session V4 candidate (SSEAdaptiveMarketV4Candidate, R411 + R430)
| ID | Severity | Finding | Resolution (this session) |
|---|---|---|---|
| SC-01 | High | Locks a capacity unit on EVERY candidate in a 64-entry window at funding; one lease can exhaust many monitors' capacity until draw (griefing; R411 noted) | Registry reserves only n+s drawn seats at draw time (SSEMonitorRegistryV4.reserveSample) |
| SC-02 | High | Rotating window of ≤64 active monitors is not global sampling | Append-only roster, global rejection sampling over population cut frozen at award |
| SC-03 | Medium | `% (roster.length - i)` without rejection: modulo bias (negligible for 256-bit hashes but not exact) | Rejection threshold `2^256 mod N` |
| SC-04 | High | No standby, no promotion; V2-style ledger with in-ledger confirmation | Integrated SSEStandbyCommittee + `freezeConfirmedCommittee` |
| SC-05 | Medium | Seats derived as min(eligible, gasBound, payable): consumer cannot fix n; quorum changes with eligibility | Board stores explicit n, s, b (n ≥ 3b+1); ledger frozen with eligibleCount=gasBound=n so decide() returns exactly n |
| SC-06 | Medium | Award only after bidding window | Board.award: any valid unexpired bid, any time while Open (explicit early close) |
| SC-07 | Medium | Market constructor deploys the ledger (initcode = market+ledger; V3 runtime already 23753 B ≈ 97% of EIP-170) | Five separate modules wired by precomputed CREATE address, verified in market constructor |
| SC-08 | Info | Monitor bonds in market mixed with service escrow | Bonds moved to registry with separate `bondAccounting()` |

## 2. New V4 architecture (SSEAdaptiveMarketV4 + Board + Registry + Standby + LedgerV4Candidate)
State machine (market `Phase`): None → PendingDraw (award+fund) → Forming (draw ok) → Active (committee frozen) → Closed;
Cancelled from PendingDraw (blockhash expired / insufficient monitors / unaccepted), Forming (standby Expired / unaccepted),
Active (unaccepted). Provider acceptance is a separate flag allowed in PendingDraw/Forming/Active before `acceptDeadline`.
Execution authorization = `EpochStarted` only (requires Active ∧ accepted ∧ exposure admission).

### Money flows (static conservation argument)
- Market holds: service escrow (`totalServiceEscrow`), monitor budget pending (`totalPendingMonitorFunding`), credits
  (`totalWithdrawable`). Award adds service+budget = msg.value exactly. Activation moves budget to ledger exactly once
  (`monitorBudgetTransferred`). Cancel credits service + (budget if not transferred). Refinement moves dp+dc from escrow
  to credits; residual allocation moves `unresolvedAmount`; close moves `available`. Hence balance ≥ sum of the three totals.
- Ledger: report budget → per-report credit; remainder refunded to consumer at `closeReporting` (or `expireUnconfirmed`, unused in V4).
- Registry: bonds → credit only on `completeExit` with `reserved == 0`.
- SSE accounting library invariant `funded = available + exposure + providerCredit + consumerCredit` (unchanged code, V3-tested).

### Authorization
Board.award, Registry.reserveSample/releaseExcept/releaseAll, Standby.initialize/cancel, Ledger.freezeConfirmedCommittee/
openEpoch/authenticateResponse/closeReporting are callable only by the immutable market. Market privileged entry points:
`awardAndFund` (request consumer), `acceptLease` (provider), `startEpoch`/`closeLease` (consumer), `cancelUnaccepted`
(consumer before deadline, anyone after). Everything else is permissionless and deterministic. No owner/admin.

### Reentrancy
Only native-ETH transfers are pull `withdraw()` in each contract with a guard and checks-effects-interactions. External
calls from the market go only to immutable trusted modules; `nonReentrant` on all functions moving funds or lifecycle.

### Sampling (SSEMonitorRegistryV4.reserveSample)
Attempt a: x = keccak(seed, domain, a); reject x < 2^256 mod N; index x mod N; skip inactive / counterparty / duplicate /
no-capacity entries. Under the uniform-hash model each accepted pick is uniform over remaining eligible entries, so the
output is a uniformly random ordered sample without replacement among entries eligible at draw time. Attempts are bounded
(8 per seat, ≤512); failure is a full refund, never a smaller committee. Exact success probability is computed by
tools/sse_v4_committee_planner.py. Adversary after seeing the seed can only exit its own entries, which cannot increase its
count of drawn identities (removing an attacker pick replaces it with the next accepted pick: change ≤ 0).
**Residual risks:** proposer of the entropy block can withhold (one-bit grinding) — not a VRF; eligibility changes from other
leases drawn in the same block depend on tx ordering; Sybil weight is one entry per bonded address.

### Standby / selective confirmation
Final committee ⊆ the n+s drawn identities, so P(final attackers > b) ≤ P(drawn attackers > b) (hypergeometric, computed by
the planner). Adversarial primaries can force promotion (delay/griefing) but cannot add attackers beyond the drawn set.
Inactive standbys and replaced primaries are never in the ledger and cannot vote. Committee is immutable after freeze
(no mid-epoch change). Quorum q = n − ⌊(n−1)/3⌋ computed identically by standby and ledger.

### Gas bounds
reserveSample ≤512 attempts (~2 storage reads each) + ≤64 reservations; releaseExcept O(k²) in memory, k ≤ 64; standby
initialize O(k²) ≤ 4096 comparisons; ledger freeze O(n). Estimated worst case well below 30M gas; **to be measured (DRV-V4-GAS)**.

### Known open issues / not implemented
SC-09 No standby retainer: unpromoted standbys are bonded but unpaid. Owner decision D-12: accepted by design, no retainer.
SC-10 No keeper bounty for permissionless transitions (draw, activate, advance, finalize).
SC-11 No misconduct penalties/slashing of monitor bonds (only provable misconduct would be acceptable; none implemented).
SC-12 Bonds of committee members are released at lease closure, not at evidence-window end (no slashing exists, so no loss).
SC-13 Runtime size of SSEAdaptiveMarketV4 unknown (EIP-170) — **Awaiting compilation** (test `testBytecodeSizeLimits`).
SC-14 Stack depth of `awardAndFund/_recordLease` statically reduced by splitting; compile may still require `via_ir` —
     owner to try default profile first and record result.
SC-15 `responseAdmitsReceipt` is an explicit bilateral term; it does NOT alter V3 semantics.
