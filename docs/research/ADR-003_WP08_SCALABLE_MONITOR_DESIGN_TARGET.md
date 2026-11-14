# ADR-003 (WP-08) — Scalable monitoring and original requirements reconciliation

**Status:** TARGET REQUIREMENTS, not implemented. **Date:** 2026-11-10.

## Crucial separation

`n` eligible bonded identities across the network need **not** equal `k` monitors selected for a particular lease. Nor does `q` votes out of `k` establish physical truth by itself. The **original WP-08 baseline** had lifetime `MAX_IDENTITIES=32`, fixed `k=4`, `q=3` and an authorized randomness source. The later **draft WP-09B** implementation (stacked PR #23, not merged) replaces that lifetime cap with an O(1)-removable active roster and a bounded 64-entry rotating candidate window. This is a gas-bounded *window-sampling* research prototype, **not** globally uniformly random selection, Sybil-resistant membership or final trusted-VRF election. `k=4`, `q=3` and the original authorized randomness source remain. The older baseline is retained as research history.

## R3 target requirements and acceptance measurements

1. **Expandable eligibility registry**: no arbitrary lifetime identity cap; registration, exit, eligibility snapshots and bond withdrawals must remain gas-bounded or be broken into bounded steps. Avoid an unbounded on-chain loop over all candidates.
2. **Per-lease selection**: verifiable (e.g. VRF-type) unpredictable seed tied to a frozen eligibility snapshot and lease ID. Measure assignment delay and randomness failure recovery. A VRF does **not** establish independent operators or Sybil resistance.
3. **Configurable committee**: research parameter `k` and reporting threshold `q`; define maximum tolerated faulty/offline nodes `f`, for reporting liveness require `q <= k-f`. Majority of signed reports is not an SLA proof unless qualified separately.
4. **Economic membership policy**: explicit bond and lock rules, slashable offenses limited to independently *provable* misconduct (e.g., equivocation), and quantified Sybil/concentration assumptions.
5. **No-show recovery**: monitor confirmation timeout, permissionless expiry/reassignment, no indefinite lock when selected monitor disappears, and independent committee release even if consumer becomes inactive.
6. **Correlated partitions and Byzantine behavior**: randomized and adversarial experiments where multiple monitors observe the same incorrect or missing network information. Distinct addresses are not assumed independent organizations.
7. **Reward mechanism**: avoid rewarding truthful-looking but false physical assertions as if objective fulfillment were proven. Pay for verifiably submitted observations and/or defined duties, with incentive claims clearly separated from fact truth.
8. **Scalability measurements**: candidate count, gas for register/exit/select, active leases, assignment latency, nonresponse rate, distribution of monitor selections and failure recovery time; compare with fixed 4-of-3 baseline.

## WP-09B incremental implementation (draft, 2026-11-14)

- Implemented: no 32-identity lifetime cap, dense active set with swap-and-pop exit, rejoin after delayed withdrawal, O(64) bounded rolling assignment snapshots and gas-bounded seed fulfillment, while preserving four selected monitors and WP09A no-show recovery.
- Explicitly **not implemented**: globally uniform randomness across all active candidates, independent VRF/consensus entropy, immutable global eligibility commitments, anti-Sybil guarantees, dynamic k/q or independent third-party operators. Membership churn and front-running can predictably change which candidates are in a rolling window.
- Client API migration: `candidateCount()` and `candidateAt()` now enumerate only **currently active** entries; historical distinct-account count is `totalRegistrations()` and historical identities can be reconstructed from event logs.
- Evidence: [stacked draft PR #23](https://github.com/AkrAyoub/sse-research/pull/23) and `R3_WP09B_BOUNDED_ACTIVE_REGISTRY.md`. Acceptance remains conditional on GitHub CI plus subsequent fairness/adversarial experiments.

## Dependencies retained elsewhere

R1 contractual SLA/evidence semantics; R2 financial and residual safety; R4 interoperable signed records; R5 independent role agents; R6 NAT/cloud enrollment; R7 HTTP/compute/storage/OCI/API predicates; R8 archive/observatory; R9/R10 cross-host failure experiments; R11 external reproduction; P0–P6 theory and paper. **Nothing is dropped.**

## Sequence

Finish ADR-001/002 and a narrow authenticated *observation* SDK before the R3 redesign is used for irreversible settlement. R3 may be prototyped in parallel, but changing `k` or the randomness provider without an evidence-soundness definition would solve a different problem.
