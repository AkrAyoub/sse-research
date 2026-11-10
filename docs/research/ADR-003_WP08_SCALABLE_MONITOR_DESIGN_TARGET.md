# ADR-003 (WP-08) — Scalable monitoring and original requirements reconciliation

**Status:** TARGET REQUIREMENTS, not implemented. **Date:** 2026-11-10.

## Crucial separation

`n` eligible bonded identities across the network need **not** equal `k` monitors selected for a particular lease. Nor does `q` votes out of `k` establish physical truth by itself. The current implementation has a lifetime `MAX_IDENTITIES=32`, fixed `k=4`, `q=3`, and an authorized randomness source. This is a *reproducible prototype baseline*, not the final permissionless/scalable solution.

## R3 target requirements and acceptance measurements

1. **Expandable eligibility registry**: no arbitrary lifetime identity cap; registration, exit, eligibility snapshots and bond withdrawals must remain gas-bounded or be broken into bounded steps. Avoid an unbounded on-chain loop over all candidates.
2. **Per-lease selection**: verifiable (e.g. VRF-type) unpredictable seed tied to a frozen eligibility snapshot and lease ID. Measure assignment delay and randomness failure recovery. A VRF does **not** establish independent operators or Sybil resistance.
3. **Configurable committee**: research parameter `k` and reporting threshold `q`; define maximum tolerated faulty/offline nodes `f`, for reporting liveness require `q <= k-f`. Majority of signed reports is not an SLA proof unless qualified separately.
4. **Economic membership policy**: explicit bond and lock rules, slashable offenses limited to independently *provable* misconduct (e.g., equivocation), and quantified Sybil/concentration assumptions.
5. **No-show recovery**: monitor confirmation timeout, permissionless expiry/reassignment, no indefinite lock when selected monitor disappears, and independent committee release even if consumer becomes inactive.
6. **Correlated partitions and Byzantine behavior**: randomized and adversarial experiments where multiple monitors observe the same incorrect or missing network information. Distinct addresses are not assumed independent organizations.
7. **Reward mechanism**: avoid rewarding truthful-looking but false physical assertions as if objective fulfillment were proven. Pay for verifiably submitted observations and/or defined duties, with incentive claims clearly separated from fact truth.
8. **Scalability measurements**: candidate count, gas for register/exit/select, active leases, assignment latency, nonresponse rate, distribution of monitor selections and failure recovery time; compare with fixed 4-of-3 baseline.

## Dependencies retained elsewhere

R1 contractual SLA/evidence semantics; R2 financial and residual safety; R4 interoperable signed records; R5 independent role agents; R6 NAT/cloud enrollment; R7 HTTP/compute/storage/OCI/API predicates; R8 archive/observatory; R9/R10 cross-host failure experiments; R11 external reproduction; P0–P6 theory and paper. **Nothing is dropped.**

## Sequence

Finish ADR-001/002 and a narrow authenticated *observation* SDK before the R3 redesign is used for irreversible settlement. R3 may be prototyped in parallel, but changing `k` or the randomness provider without an evidence-soundness definition would solve a different problem.
