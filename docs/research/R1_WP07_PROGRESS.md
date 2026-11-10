# R1 WP-07 checkpoint — versioned conditional evidence policy, physical vs chain-publication services

**2026-11-10. Status:** local research model, downloadable artifact; source package NOT yet integrated in GitHub branch or hosted CI. No production Solidity payout changes.

## Core contribution under evaluation

A clear boundary between (1) raw authenticated observation and (2) a qualified physical fact under a named, *externally validated* soundness assumption. A raw ACK, signed response, any number of honest timeouts, or a positive monitor quorum **never by itself** permits history exclusion in the strict physical-delivery policy. An assumed sound receipt certificate conditionally removes N; an assumed sound full nonfulfillment certificate after the SLA deadline conditionally removes S; an assumed sound timely delivered-result certificate conditionally selects S. An ambiguous external timestamp cannot prove timeliness.

A separate on-chain-publication *product*, in which the contract purchases canonical inclusion of a valid response before a deadline, is modeled with **{F,S} only** and the explicit `CANONICAL_CHAIN_COMPLETE` assumption. This is **not** physical compute rental, consumer-side delivery, storage durability, or a compatible replacement for the current N/F/S reservation promise.

The new Python classes `QualifiedFact` and `ChainSnapshot` can be arbitrarily constructed by a caller and **are not security boundaries**. Real certificate cryptography, canonical manifest hashing, chain finality and robust service validators remain R4/R2 work.

## Local evidence

The delivered artifact `SSE_R1_WP07_Versioned_Evidence_Policy_2026-11-10.zip` includes:
- `tools/sse_evidence_policy_v1.py`
- `tools/sse_wp07_demo.py`
- `tests/test_sse_evidence_policy_v1.py`
- R1/P0 specification, install/study guide, focused/combined logs and SHA-256 manifest.

**Python 3.13.5 isolated:** 50/50 new tests PASS, zero failures. Combined restored research source WP-02 through WP-07: 168 discovered, 167 pass, one prior source-dependent test skipped because full historical Solidity source was not loaded in that isolated work tree. Demo: seven JSON-lines scenarios. **Original complete project Python suite, 52 Foundry tests, Windows host and GitHub CI were NOT rerun with WP-07.** Foundry not installed in authoring container.

ZIP SHA256: `814b0aabf3b136fa86e751a42334b9724dd7cae77bb4fe9b37bbbc14b0d36fe6`.

## Follow-up gates

1. Extract ZIP into local repo on branch `research/r1-evidence-policy-wp07`; run full Python discovery, demo, Foundry build and 52 existing Foundry tests.
2. Commit source/tests/docs, push, create draft PR, inspect all three GitHub Actions jobs; only then merge research code.
3. Do **not** connect `QualifiedFact` to live escrow: no actual verifier exists. First specify ADR-001 physical receipt and delivery, ADR-002 verifier soundness, ADR-004 clock/time, and update R2 economic rules with explicit service modes.
4. R4: implement immutable Keccak/EIP-712 service manifest, scope/replay binding and independent evidence-verifier/qualification SDK.
5. P0: comprehensive prior-art/novelty verification against runtime monitoring, failure detectors, and optimistic fair exchange (the present screening is not systematic).

## Provisional project percentages

R0 100%; **R1 62% (+6pp)**; R2 26%; R3 15%; R4 10%; R5 10%; R6 5%; R7 15%; R8 10%; R9 5%; R10 0%; R11 0%.

**P0 37% (+2pp)**; **P1 55% (+5pp)**; **P2 29% (+4pp)**; **P3 39% (+7pp)**; **P4 20% (+2pp)**; P5 0%; P6 0%.

Equal-weight averages: engineering 22% (258/12 = 21.5%), research 26% (180/7≈25.71%), entire project 23% (438/19≈23.05%). These percentages count local source/research work, **not production deployment or security acceptance**.
