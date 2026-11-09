# Parallel scientific work: R1 and P0 initial screening (2026-11-09)

**Status: scoping, NOT a completed formal protocol or systematic literature review.** These questions must shape R1 ADR-001/002/003 and the paper's threat and novelty claims before R2 changes the settlement engine.

## R1 proof boundary

Let `H*` be a physical contractual history and `I(E)` the interpretation of accepted authenticated records. Require `H* ∈ I(E)` under explicit assumptions; `I(E) ≠ ∅`. With bounded provider obligation `0 ≤ F(H) ≤ V`, compute `L = min F(I(E))`, `U = max F(I(E))`, allocate provider `L`, consumer `V-U`, retain `U-L`.

Propositions that follow from these definitions **conditional on soundness**: conservation `L + (V-U) + (U-L) = V`, lower/upper safety against `F(H*)`, maximal universal individual guaranteed credits, and monotone release under `I(E2) ⊆ I(E1)` with sound refinement. They are elementary; the scientific problem is constructing sound `I` despite malicious witnesses, missing receipt and bad clocks.

### Immediate questions / ADR inputs

1. Define a physical request lifecycle distinguishing consumer *send*, provider *receive*, provider *accept/acknowledge*, service execution, and consumer *receive response*. Specify which events are contractually relevant; why is a provider's signature on a public challenge not itself proof of receipt? (ADR-001)
2. Distinguish evidence `NO_VALID_RESPONSE_OBSERVED`, `PROVIDER_SIGNED_RESPONSE`, `MONITOR_REPORTED_FAILURE`, `PROVIDER_ACK`, and `UNKNOWN` with explicit observation/clock/network assumptions. If the actual history is S but monitors cannot reach it, can a 3/4 FAILURE quorum soundly exclude S? Not without additional fault/availability assumptions. (ADR-001/002)
3. Specify the interpretation for contradictory reports and no quorum, including the empty-history case (fail closed). Specify exactly which history exclusions are justified under f Byzantine monitors; signing does not imply physically independent operators. (ADR-002)
4. Specify admission-time exposure upper bounds and timing. The existing `SSESettlement` conservatively reserves a full next fee; prove induction before optimizing. (ADR-003)
5. Write regression vectors for `N/F/S`, observed-but-undelivered responses, Byzantine monitors, partitions, clock skew, duplicate/replayed signatures, and onchain/offchain digest mismatch.

## P0 literature screening — compare protocol semantics, not features

| Work | Verified focus | Comparison that still requires full-text reading |
|---|---|---|
| Shi et al., **AWESOME** (2022), https://link.springer.com/article/10.1186/s13677-022-00292-8 | Auctions, witnesses, SLA enforcement in cloud marketplace | Are payments ever finalized partially when mutually admissible contractual histories imply different payouts? |
| **Enforcing trustworthy cloud SLA with witnesses** (2019), https://onlinelibrary.wiley.com/doi/10.1002/cpe.5511 | Incentivized witnesses and out-of-chain service violation attestation | Which oracle / network honesty assumptions yield conclusive versus inconclusive decisions? |
| Basin, Klaedtke & Zălinescu, **Failure-aware Runtime Verification of Distributed Systems** (2015), https://drops.dagstuhl.de/opus/volltexte/2015/5619/pdf/3.pdf | Three-valued monitoring with failures, out-of-order delivery and incomplete knowledge | Can its sound uncertainty semantics inform `I(E)`? It does not by itself show monetary SSE novelty. |
| **Distributed service-level agreement management with smart contracts and blockchain** (2020), https://onlinelibrary.wiley.com/doi/10.1002/cpe.5800 | Hybrid permissionless/permissioned monitoring oracles and SLA compensation | Can accepted violation claims remain unresolved financially, and are funds released conservatively? |
| **Automated Quality of Service Monitoring for 5G and beyond Using Distributed Ledgers** (2021), https://arpi.unipi.it/handle/11568/1127020 | Cryptographic Bloom-filter usage records and signed state-channel summaries | What happens on signature mismatch, missing data, or unavailable counterparties? Is partial safe settlement already present? |

This list is preliminary, not a claim of exhaustive novelty clearance. For P0 completion, examine full algorithms/proofs; search specifically for robust interval settlements, guaranteed partial payouts and exposure-aware service admission; build a claim-by-claim comparison matrix with negative and positive evidence.

## Evaluation prerequisites (P4 dependent on R1)

Pre-register measured early released capital, retained exposure, admission throughput, unsafe exclusions under simulated faults, timing distribution, on-chain gas and extra monitoring costs; compare at least `definitive-outcome-or-hold`, explicit binary/default decision and SSE, all under the same physical histories and evidence semantics. Do not call a fabricated weak binary baseline representative of a specific paper.
