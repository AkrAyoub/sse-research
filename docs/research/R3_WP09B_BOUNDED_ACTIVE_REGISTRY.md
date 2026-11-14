# R3 WP-09B — Dynamic active registry with bounded rolling snapshots

**Checkpoint:** 2026-11-14. Stacked **draft PR #23** on WP-09A PR #22; depends on #21, #20, #19 and #18. Nothing has been merged or deployed. This research increment is **NOT** a globally unbiased VRF-based monitor assignment design.

## Problem and security objective

Before WP-09B, `OpenMonitorCommittee.register()` rejected the 33rd *distinct identity ever registered*, even if earlier candidates had withdrawn. `requestAssignment()` iterated over every ever-registered address, meaning an arbitrary removal of the cap would allow callers to trigger gas-exhausting assignments and stranded permissionless market leases. This conflicted with ADR-003's scalable eligibility requirement.

WP-09B removes the lifetime admission cap while **explicitly bounding the work of one request and one seed fulfillment**. It is one safe engineering step, NOT full scalable uniformly random membership.

## Contract change and invariants

### Dense active roster

- `activeCandidates[]` stores **currently active** bonded identities. `activeIndexPlusOne[address]` gives a one-based membership slot, zero when inactive.
- `register()` requires a previously cleared bond, pushes the active address, records its index and increments `totalRegistrations` **once per never-before-seen address**. There is no arbitrary lifetime `MAX_IDENTITIES` ceiling; economically and block-gas limits still apply to each individual transaction.
- `requestExit()` remains prohibited while `pendingSelections > 0` or `activeAssignments > 0`. A permitted exit deactivates the candidate and removes them from the dense active roster by constant-time swap-and-pop, updating the moved candidate's index.
- Existing withdrawal delay and withdraw-before-reregister requirements are unchanged. A withdrawn candidate can join again without artificially exhausting a lifetime ID slot. `totalRegistrations` is historical; `candidateCount()/candidateAt()` **now enumerate only active candidates**, not all ever-registered ones. Clients relying on the previous lifetime-list semantics must migrate; active roster indexes are unstable across exits.
- Active roster membership does not attest to independent operators, anti-Sybil eligibility, geographic diversity, evidence quality or physical SLA soundness.

### Bounded rolling selection window

- `MAX_SNAPSHOT_SCAN = 64` is a constant *gas bound*, not a global committee-size target. The fixed committee is still `k=4`, the monitoring vote threshold still `q=3`, and all four selected members must **confirm before epoch admission**.
- `requestAssignment()` examines at most `min(activeCount, 64)` active entries, starting at `nextSnapshotCursor` and wrapping around the active roster. Entries equal to the lease provider/consumer or lacking an active minimum bond are skipped.
- A request needs at least four eligible candidates **inside its scanned window**; otherwise the entire lease creation rolls back with `InsufficientCandidates`, including cursor advancement and escrow. There is no silent reduction of initial confirmations or substitution of arbitrary addresses.
- Every eligible window entry is frozen into the existing per-assignment `snapshots[id]` and increments its `pendingSelections` lock. After a successful snapshot, the cursor advances by the number scanned and wraps at the active roster size. No iteration over all active identities occurs in the assignment transaction.
- The existing configured randomness-source call `fulfillRandomness(id, seed)` shuffles **only the bounded eligible window** into four selected members and up to 60 ordered standby members. On `expire(id)` or successful random fulfillment, each snapshot lock is released in a loop bounded by 64. Standby recovery from WP-09A remains intact, including active-bond checks, timeouts and round-robin missing-seat rotation.
- `SnapshotWindowUsed` records request ID, start index, scanned entries, active count and eligible window count for future experimental measurements.

### Trust/fairness caveat

The rolling window is **predictable from visible contract storage**. It is not a uniform sample across the global active membership and not Sybil-resistant. An adversary can influence which addresses appear near a cursor through registration/exit timing and can create many bonded identities. A seed (still controlled by the configured randomness source) only shuffles the already-chosen eligible window; it does not repair the nonuniform window filter. Modulo reduction in the V1 shuffle and source availability remain open. Do not claim random global election, honest majority or physical evidence truth.

## Reproduction and adversarial evaluation

New `foundry/test/BoundedActiveRegistry.t.sol` validates:

1. **160 simultaneously active distinct bonded addresses**, showing elimination of the previous 32-lifetime ceiling, enumeration correctness and historical `totalRegistrations`.
2. A fresh lease with 160 active identities scans **exactly 64** entries; its entire lease-creation call uses less than 8.5 million gas under Foundry's lab configuration; only scanned candidate locks change.
3. The four selected addresses are drawn only from the eligible window, with no unauthorized global candidate selected; all 60 standbys are eventually deleted on release.
4. Three consecutive windows of 64 across 96 active candidates cover each identity twice in a **static** active roster. This demonstrates deterministic rotating coverage, not global unbiased selection or a live fairness guarantee under churn.
5. Constant-time voluntary exit with correct swap-and-pop index updates, no orphan entries, unchanged exit delay, safe withdrawal and re-registration without a new historical registration.
6. Pending-selection/selected active-bond lock enforcement and standby exit behavior; no candidate may evade a currently active assignment by exiting.
7. Consumer/provider candidates are excluded from their own lease, even if bonded; insufficient qualified candidates cause atomic lease and escrow revert; unauthorized direct assignment calls cannot advance the cursor.
8. The **64-candidate seed fulfillment** also stays below the lab 8.5-million-gas budget, and the next-snapshot cursor resets safely when 65 active addresses shrink to 64.

The existing Foundry suite covers 3-of-4 no-show rescue, two absent seats, residual conservatism and signed observations. The live Anvil marketplace and signed-HTTP scenario is also run in GitHub CI.

From a disposable clone with pinned dependencies and Foundry:

```bash
forge build
forge test -vv
python -m unittest discover -s tests -v
python tools/sse_wp08c_live_marketplace.py
```

**Validated source CI:** [GitHub Actions run #43543913041](https://github.com/AkrAyoub/sse-research/actions/runs/43543913041): 67/67 Foundry tests, 385/385 Python tests on Ubuntu and Windows, plus fresh local Anvil marketplace/evidence scenario (all four jobs). These are laboratory tests, not production gas guarantees at every EVM fee schedule or audited security proofs. **Estimated engineering R3 = 26% (+6pp), engineering aggregate 25%, research aggregate 26%, overall 25%** by the project's equal-phase progress tracker.

## Remaining acceptance blockers

- **Global unpredictable, bias-auditable committee selection:** A reviewed VRF/commit-reveal or light-client-backed entropy policy tied to a *frozen global eligibility snapshot* is still required. The current 64-member rolling window cannot claim this.
- **Sybil resistance and capacity controls:** Bonds per EOA neither prevent identity splitting nor guarantee different operators; no global saturation cap per operator, on-chain minimum-capacity filter or independent infrastructure attestation.
- **Adversarial churn/fairness:** Remove/append changes roster order and predictably affects future selection windows. Need quantified selection-frequency/churn experiments and anti-griefing policies.
- **Dynamic `k` and `q`:** Current fixed 4-member/3-vote interface remains unchanged, by design, to avoid breaking settlement semantics until R1/P1 and R2 policies are reviewed.
- **Independent finality and physical SLA soundness:** Neither source-of-randomness nor active enrollment proves honest physical monitoring, service delivery, neutral timestamps, validator consensus or entitlement to escrow.
- **Deployment compatibility:** These changes require newly deployed V1 pool and settlement contracts and refreshed client expectations; merging source is not an on-chain upgrade.

**Acceptance statement:** gas-bounded dynamic **membership** and deterministic **window** sampling are demonstrated; global fairness, randomness and service/economic safety remain separate, unfinished gates.
