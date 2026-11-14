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

## WP-09C bounded-snapshot future-block entropy (draft, 2026-11-14)

- Implemented: **opt-in, one-way** future-block mode before settlement binding; hash-commit the entire **already bounded eligible snapshot** at assignment time; after four additional blocks, any caller may derive a domain-separated seed from the future block hash. Arbitrary seed submission by the former authorized source is disabled **in this mode**, while the legacy behavior remains supported when not enabled.
- The snapshot commitment is cryptographically reproducible, but the input block hash is **not a verified VRF result** and may be affected by validators, sequencers, reorgs, chain timing, and selective requester cancellation. A four-block wait is for the lab, not a justified production security parameter. This incremental change does **not** freeze the *entire global candidate universe*, which remains limited to the rolling 64-entry WP09B snapshot.
- Full unbiased, ungrindable global selection, Sybil/operator independence, verifiable PoS finality, candidate-concentration defenses and physical evidence soundness remain separate and unfinished research goals. In particular, a future-block hash must never be described as a Chainlink/VRF proof.
- Evidence: [stacked draft PR #24](https://github.com/AkrAyoub/sse-research/pull/24), `R3_WP09C_FUTURE_BLOCK_ENTROPY.md`; hosted source CI [75 Foundry, 385 Python each OS and live Anvil](https://github.com/AkrAyoub/sse-research/actions/runs/43545560434), 4/4 green.

## WP-09D experimentally verified RSA-root entropy (draft, 2026-11-14)

- A mutually exclusive deployment-time entropy mode validates a **canonical RSA-2048 root** of a lease-/snapshot-scoped digest on the EVM modular-exponentiation precompile (0x05). Unauthorized arbitrary seeds are rejected; any relayer can submit an operator-produced proof.
- **Not a standardized VRF:** custom eight-Keccak representative has no audited FDH proof, the modulus/key ceremony is trusted, and the signer may selectively withhold a computed result. The test RSA private exponent is **public and insecure** and is deliberately unsuitable for deployment. This does not independently solve selection fairness or liveness.
- Evidence: [draft PR #25](https://github.com/AkrAyoub/sse-research/pull/25), `R3_WP09D_RSA_PROOF_ENTROPY.md`; [81 Foundry + 393 Python each OS + Anvil real proof 4/4 green](https://github.com/AkrAyoub/sse-research/actions/runs/43547062260).

## WP-09E global indexed Merkle roster (draft, 2026-11-14)

- A **second, independent** pre-binding opt-in maintains a depth-20 sparse Merkle tree over the complete active address list. Register and swap-pop exit update O(log N) nodes; each lease freezes the **entire active root/count in O(1)**. The maximum 2^20 **simultaneous** slots is a bounded-index design choice, not a lifetime identity cap.
- After deriving a seed from **one** of the legacy / future-block / experimental RSA modes, on-chain logic deterministically draws the first at most 10 distinct indices across **all N active addresses**, using a sparse partial Fisher–Yates permutation. Caller-supplied 20-sibling inclusion proofs for every drawn index must exactly match the historical root, with no ability to skip unpopular indices, hand-pick leaves, or reorder the draw. The first four currently active/bonded non-party monitors are selected; remaining proved eligible candidates become ordered standbys.
- **Research limit:** under a stable honest registry and ideal seed, this conditionally samples from the **global** roster, unlike WP09B's predictable 64-entry window. Yet the original seed trust/withholding vulnerabilities, tiny modulo reduction bias, Sybil identity splitting, mutable physical operators, missing independent candidacy qualification and selective abort still exist. This **does not** establish an unbiased, production-grade VRF committee.
- **Liveness trade-off:** the entire registry is **not pending-locked** at request time. Candidate exits following the frozen root may reduce eligible selected members or exhaust reserve proof availability, at which point the assignment must fail closed and rely on timeout/consumer refund. No unproven availability guarantee should be inferred from the Merkle proof. Historical indexers and archives must be able to reconstruct the snapshot for relayer success.
- Evidence: [draft PR #26](https://github.com/AkrAyoub/sse-research/pull/26), `R3_WP09E_GLOBAL_MERKLE_ELECTION.md`; initial [88 Foundry + 403 Python each OS + actual RSA/global Merkle Anvil integration 4/4 green](https://github.com/AkrAyoub/sse-research/actions/runs/43548406416). Remaining work: audited entropy, adversarial churn/withholding experiments and gas/concurrency measurement.

## Dependencies retained elsewhere

R1 contractual SLA/evidence semantics; R2 financial and residual safety; R4 interoperable signed records; R5 independent role agents; R6 NAT/cloud enrollment; R7 HTTP/compute/storage/OCI/API predicates; R8 archive/observatory; R9/R10 cross-host failure experiments; R11 external reproduction; P0–P6 theory and paper. **Nothing is dropped.**

## Sequence

Finish ADR-001/002 and a narrow authenticated *observation* SDK before the R3 redesign is used for irreversible settlement. R3 may be prototyped in parallel, but changing `k` or the randomness provider without an evidence-soundness definition would solve a different problem.
