# SSE R1 WP-04 — Observation equivalence and evidence mechanisms (integration checkpoint)

**Date:** 2026-11-09. **Status:** source/test/docs produced in a separately downloadable package, not yet committed into this branch, not run on the user's host or GitHub Actions; production Solidity unchanged.

## Core scientific result
Given a physical execution (x), a network-dependent observation projection (π(x)), and finite possible-execution set (Ω), define `A(o)={world(x): x in Ω and π(x)=o}`. If the true execution belongs to Ω, the true world is retained; **this does not show Ω is complete in any real network**. Indistinguishable F and S histories can carry different entitlements (0 vs 25); a deterministic observation-only payout cannot safely release either side more than the common guarantee.

The WP-04 package adds `tools/sse_observability_reference.py`, `tools/sse_wp04_demo.py`, `tests/test_sse_observability_reference.py`, detailed P0 literature comparison and R1 design notes. It also includes missing WP-03 source/test prerequisites. **30 new WP-04 tests passed locally; 75 combined WP-02+WP-03+WP-04 tests passed (19+26+30), 0 failures**. This is a finite, fully stipulated simulator, not a cryptographic proof of physical cloud delivery or a Solidity exploit.

## Prior-art conclusions
- Failure detectors: Chandra & Toueg (1996), https://www.cs.cornell.edu/info/people/sam/FDpapers.html — timeout suspicion is not unconditional physical failure.
- Partial-observation runtime verification: Basin, Klaedtke & Zălinescu (2015), https://doi.org/10.4230/LIPIcs.FSTTCS.2015.590 — sound three-valued semantics is existing research.
- SLA oracle precedents: Uriarte et al., https://doi.org/10.1002/cpe.5800 — dynamic SLA monitoring via blockchain/oracles exists.
- HTTP TLS provenance: DECO, https://sigsac.org/ccs/CCS2020/proceedings.html; TLSNotary, https://tlsnotary.org/docs/faq/ — third-party data provenance is not automatically consumer delivery or SLA fulfillment.
- Storage PoRep/PoSt: https://spec.filecoin.io/ — specialized temporal proofs, not universal cloud verifier.
- zkVM receipt: https://dev.risczero.com/api/zkvm — execution/output proof, not rented CPU capacity or physical deadline.
- Akash resource manifests: https://akash.network/docs/learn/core-concepts/deployments/ — leased resource specifications already exist.

## Implementation decisions
**Now:** retain unknown rather than treating monitor nonarrival as certain failure, model service-specific contractual predicates, version manifests, test indistinguishable traces and build differential tests. **Later/conditional:** authenticated consumer receipt and trusted timing, TLS notary, verifiable compute, storage proof adapter, hardware attestation under explicit assumptions. **Do not claim:** unconditional failure inference from 3 timeouts, hash as proof of CPU allocation, or single GET as proof of persistent storage.

## Git/reproduction status
Research branch `research/r1-observability-wp04` was created from `research/r1-service-conditions-wp03`; the package's 11 source/test/doc files still must be extracted and committed. The authoritative source of exact install/test instructions is in `WP04_INSTALL_AND_STUDY.md` inside `SSE_R1_WP04_Observability_Research_2026-11-09.zip`.

Run all new source/tests plus existing Python/Foundry suites on the user's host, then push, make a draft PR and verify Python Ubuntu+Windows and Solidity Ubuntu CI. Do not approve production evidence interpretation by merging research code. The original 106 Python / 35 Foundry tests were not rerun with WP-04 in the authoring environment.

## Estimated phase changes
R0 100% unchanged, R1 **43% (+8 pp)**; P0 **32% (+7 pp)**, P1 **40% (+10 pp)**, P2 **15% (+5 pp)**, P3 **25% (+5 pp)**, P4 **10% (+5 pp)**. All other phases unchanged. Engineering approx **19%**, research approx **17%**, total approx **19%** (equal-phase rounded averages). Scientific novelty remains unconfirmed.
