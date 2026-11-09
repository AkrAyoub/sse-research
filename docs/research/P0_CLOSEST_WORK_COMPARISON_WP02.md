# P0 — Initial source-grounded nearest-work comparison (WP-02)

**Status:** structured initial screening, not systematic novelty clearance. Date: 2026-11-09. No empirical results or paper contribution claim is established yet.

## Scope and methodology

We compare **what prior protocols accomplish and assume**, not whether they have Ethereum, signatures, committees, or cloud UIs. The decisive SSE research claim to investigate is whether a mechanism combines (1) uncertainty-preserving, sound mapping from incomplete authenticated observations to possible contractual worlds, (2) maximal guaranteed *partial* financial release with residual held, and (3) bounded *future* exposure from continued service. Each element may have extensive precedents; novelty cannot be inferred from the combination without a more comprehensive search and full-algorithm comparison.

## Reviewed primary sources (publication facts independently verified)

1. Z. Shi et al., **AWESOME: an auction and witness enhanced SLA model for decentralized cloud marketplaces**, Journal of Cloud Computing 11:27 (2022), DOI: https://doi.org/10.1186/s13677-022-00292-8, open article https://link.springer.com/article/10.1186/s13677-022-00292-8. Sections on witnesses/payment describe refunds for SLA violation and fee withdrawal for successful fulfillment; auction, witness committee and smart contract factory evaluated for cost/latency. No clear explanation of *partial guaranteed payment under unresolved mutually compatible histories* identified in the inspected text. **This is not proof of absence** across all supplementary material.
2. H. Zhou et al., **Enforcing trustworthy cloud SLA with witnesses: A game theory-based model using smart contracts**, Concurrency and Computation: Practice and Experience 33(14):e5511 (first published 2019), DOI: https://doi.org/10.1002/cpe.5511, full article https://onlinelibrary.wiley.com/doi/10.1002/cpe.5511 and bibliographic record https://pubmed.ncbi.nlm.nih.gov/35866176/. Core mechanism: witness incentives, game-theoretic truth telling, unbiased selection, auditing for malicious monitors. Their incentive result is conditional on game assumptions, not a cryptographic proof that a physical event occurred. **Need full payoff theorem/assumption analysis** before making a stronger contrast.
3. **Distributed service-level agreement management with smart contracts and blockchain**, Concurrency and Computation: Practice and Experience 33(14):e5800 (first published 2020), DOI: https://doi.org/10.1002/cpe.5800, full article https://onlinelibrary.wiley.com/doi/10.1002/cpe.5800. Mechanism: permissionless SLA contract + permissioned randomly selected monitoring-oracle blockchain to produce measurements and enable contract state transitions. Strong prior work for monitoring/committee architecture, not obviously for admissible-history residual allocation. **Need inspect complete SLA and compensation algorithms**, not infer from abstract alone.
4. D. Basin, F. Klaedtke, E. Zălinescu, **Failure-aware Runtime Verification of Distributed Systems**, FSTTCS 2015, DOI: https://doi.org/10.4230/LIPIcs.FSTTCS.2015.590, full version https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.FSTTCS.2015.590. Uses three-valued real-time (MTL) monitoring semantics for knowledge gaps and message reordering, with soundness and conditional completeness results. This is substantial prior art for *reasoning soundly under unknown observations*. It is not a safe novelty claim to portray SSE as inventing three-valued or partial observation semantics. Their main target is runtime-verification verdicts, not contractual monetary bounds in the paper's described algorithm.

## Mechanism-specific comparison (interpret as provisional)

| Prior mechanism | Evidentiary foundation | Observable decision/financial mechanism | Direct SSE differentiation *to test*, not assert | Confidence |
|---|---|---|---|---|
| AWESOME (2022) | Bonded/incentivized witness committee with on-chain SLA reports | Confirmation of violation -> refund; fulfilled SLA -> provider fee | guaranteed partial refund *without deciding* one physical history, and retention of residual exposure | Article passages reviewed; supplements not fully audited |
| Zhou et al. witness model (2019) | incentives/game equilibrium, selection and auditing | witness SLO-violation attestations | mathematical handling of mutually admissible, payout-divergent worlds even when witness statements are authenticated | Abstract and accessible article summary; payoff theorem not reproduced |
| Distributed SLA management (2020) | permissioned oracle consensus + public smart SLA | monitoring information drives dynamic state change | uncertainty budget coupling partial settlement to next service admission | Full article relevant sections reviewed; comparison still incomplete |
| Basin et al. (2015) | sound, failure-aware three-valued logic for incomplete distributed observations | sound/unknown runtime verdicts | translation of incomplete-world semantics into robust monetary entitlements and continuation exposure | Formal abstract/method reviewed; not a payments paper |

## Open novelty risks and actions

- **Strong risk:** history-set min/max optimization is a generic robust decision rule; the arithmetic itself is unlikely novel. Avoid claiming a fundamental theorem solely from min/max.
- **Strong risk:** uncertainty/incompleteness reasoning has deep existing literature. Cite and substantively compare it, not a superficial reference to monitoring.
- **Risk:** witness-based financial reimbursement and refund-on-violation are already published. Do not claim those as new.
- **Open:** prior approaches may already encode partial fund release, withheld escrow, budget-limited outstanding obligations, or interval reasoning under other terminology. Search escrow/fair exchange, optimistic dispute protocols, quantitative runtime verification, incomplete logs, assume-guarantee oracle frameworks, and financial robust optimization.
- **Open:** independent evidence soundness against adversarial witnesses might be impossible under asynchronous network partitions without additional communication/availability assumptions; formulate a conditional or impossibility result instead of promising a fully trustless physical truth oracle.

## Concrete P0 follow-up checklist

1. Extract and independently summarize exact statements, algorithms, and stated adversary assumptions from the above articles, with page/section identifiers.
2. Search citations and forward citations for *partial* SLA settlement, settlement intervals, commitment of unresolved amounts, and 'exposure budget' analogues; keep dated search records.
3. Define **feature-level negative evidence**: explicitly record what was searched and where, not 'paper does not do X' without full-text examination.
4. Compare all candidate baselines under identical physical histories and monitoring inputs, using a common accounting model (P4).
5. Revise SSE contribution statement only after checking adverse nearest work; record duplicates and nonnovel elements openly.
