# R3 WP-09A — Pre-epoch monitor no-show recovery by seeded standby rotation

**Status:** 2026-11-14 · draft stacked PR #22 (depends on drafts #21 → #20 → #19 → #18). Not merged or deployed. This changes Solidity source; previously deployed V1 contracts are **not** upgraded automatically.

## Exact problem

SSESettlement requires **four selected monitors to confirm the committee before any epoch is admitted**. Monitoring *votes after activation* use a separate quorum of **three of four**, but the vote quorum does not waive the initial four-confirmation requirement.

Previously, if three selected monitors confirmed and the fourth did not, the lease stayed **Accepted** and the consumer could not submit `admitEpoch`. An existing escape already existed: `closeLease` refunds **uncommitted** escrow, then `releaseCommitteeAfterEvidence` unlocks selected candidate bonds (and `refundUnusedIncentives` can refund unused separately funded incentives). WP-09A adds a way to **continue the same lease**, without inventing a fourth confirmation or granting a payout.

## Protocol change

1. **Seed-determined standby order.** `OpenMonitorCommittee.fulfillRandomness` now completes the existing keccak-seeded Fisher–Yates-style candidate permutation. It preserves exactly the **first four originally selected addresses for the same seed and candidate snapshot** and records the rest as an ordered standby roster. Selection still trusts the V1 `randomnessSource`; it is not an external VRF or a proven independent random beacon. Modulo reduction remains a technical bias caveat.
2. **Fixed pre-epoch confirmation window.** When `SSESettlement.finalizeMonitorCommittee` retrieves the selected committee, it sets `monitorConfirmationDeadline[leaseId]` to `block.timestamp + 1 hours`. This mapping is **outside the Lease struct**, preserving the struct's ABI layout used by the existing Python chain reader.
3. **Permissionless recovery, not consumer discretion.** Only after `block.timestamp > deadline`, while the lease is still `Accepted` with zero admitted epochs and fewer than four confirmations, anyone may call `replaceNoShowMonitor(leaseId)`. Settlement deterministically chooses the **first unconfirmed seat** and asks the bound pool to rotate it. The caller cannot specify a target monitor, replacement candidate or randomness seed.
4. **Pool-validated substitute.** The pool's `replaceUnconfirmed` can be called only by the bound settlement. It consumes the next currently active, sufficiently bonded standby in the original fixed seed order, skipping standby candidates that later exited. It cannot select the consumer, provider or a duplicate current committee member (the initial candidate snapshot excluded both parties). The pool decrements `activeAssignments` for the removed member and increments it for the substitute, without transferring funds or slashing.
5. **Preserve valid confirmations.** The settlement replaces one unconfirmed seat only; all earlier confirmed seats and their `confirmedMonitor` states remain unchanged. The removed member loses confirmation eligibility. **The new candidate must confirm on-chain** before the committee can transition to `Ready`.
6. **Full renewed window.** After each successful rotation, the deadline resets to another hour. Nobody can immediately consume all remaining standbys just because the original deadline expired. Replacements are forbidden once the lease is `Ready`, an epoch has been admitted or the lease has closed.
7. **Explicit fallback, not infinite availability.** If no active bonded standby remains, replacement fails closed with `InsufficientCandidates`. The consumer can still close and refund uncommitted escrow and any remaining incentive budget through the existing flows. `releaseAssignment` decrements locks for precisely the **current** four committee members and deletes unused standby storage.

## Safety invariants

- **Before epoch admission:** `monitorConfirmations == 4` is still required, even if the selected remaining three agree with each other.
- **No payment via recovery:** rotation does not admit an epoch, create a monitor vote, validate a provider response, change escrow, transfer ETH or authorize a penalty/reward.
- **No early or repeated forced rotation:** the deadline must expire for each seat being replaced; a newly substituted monitor receives a full confirmation chance.
- **No third-party seat selection:** only the original seed permutation determines replacement order. The settlement chooses the first *unconfirmed* seat, never a confirmed monitor.
- **Bond conservation:** every selected member holds one active assignment lock; removed no-shows lose that assignment lock, new members gain it, and a finalized release decrements current locks once.
- **No downgrade of monitoring quorum or SLA truth:** this is a pre-epoch availability mechanism, not a proof that a physical workload succeeded.

## Reproduction and tests

`foundry/test/MonitorConfirmationRecovery.t.sol` covers the 3-of-4-to-4-of-4 recovery flow, exact deadline boundary and unauthorized direct pool calls; restored epoch eligibility; re-confirmation requirements; full renewed deadline; exhausted and inactive standbys; deterministic skipping of an exited standby among seven candidates; consumer abort/refund and bond lock cleanup.

The existing real Anvil marketplace integration `tools/sse_wp08c_live_marketplace.py` now follows the same flow: request marketplace resource → fund lease → select 4 → only 3 confirm → verify Accepted/not Ready → wait 1 hour of **simulated Anvil chain time** → replace missing seat with original seeded standby via outsider → replacement confirms → admit epoch → provider/monitor signed HTTP capture → block anchor/witnesses/replica → fork/finality-report negative tests. The Anvil clock is not an honest wall-clock oracle.

From a disposable clean checkout with Foundry/Anvil and dependencies:

```bash
forge build
forge test -vv
python -m unittest discover -s tests -v
python tools/sse_wp08c_live_marketplace.py
```

The Anvil runner refuses to overwrite a nonempty `.local/wp08c-live/` output path; test keys are public and must never be used on real networks.

## Remaining risks / future work

- **Production randomness trust:** `randomnessSource` is fixed/trusted in V1, not externally verified VRF; end-to-end fairness and eligibility remain open research.
- **No guaranteed liveness:** a finite standby roster can be exhausted; candidates can exit before replacement. We intentionally do not lower initial confirmation count, forcibly lock standby candidates or award payouts based on unconfirmed participants.
- **No slashing for no-show:** replacement only releases that assignment's active bond lock. Economically sound no-show penalties need explicit signed duty/notice, grace/dispute policies, griefing protection and audited slashing conditions.
- **Chain timestamp assumption:** timeouts use `block.timestamp` subject to chain timestamp manipulation bounds. This is not a physical timestamp oracle.
- **No existing deployment upgrade:** a new pool/settlement deployment and role binding are required to use the change; this PR does not affect deployed contract code or balances.
- **Fixed V1 committee and registry:** four monitors remain fixed, candidate storage still caps at 32 lifetime addresses; large-scale open membership, multi-lease capacity limits, anti-Sybil independence, multi-host agents and Byzantine evidence soundness require further engineering and proof.

**No physical SLA certificate, `QualifiedFact`, epoch payout, or new Solidity monitor vote semantics are implied by this increment.**
