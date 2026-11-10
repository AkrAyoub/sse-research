# WP-07 change log and validation — 2026-11-10

## Artifacts created

- `tools/sse_evidence_policy_v1.py`: stdlib-only prototype of two distinct **contractual** policies, evidence binding, raw-vs-qualified claims, explicit assumptions, deadline intervals, monotone refinements, fail-closed contradiction handling, and canonical-chain publication alternative.
- `tests/test_sse_evidence_policy_v1.py`: **50** new local unit tests with deterministic randomized conservation and adversarial cases.
- `tools/sse_wp07_demo.py`: machine-readable JSON-lines examples for strict timeouts, assumed qualified failure, false qualifier, ambiguous clock and finality-conditioned chain publication.
- `docs/research/R1_WP07_EVIDENCE_POLICY_SPEC.md`: detailed model and implementation decisions, explicit proof assumptions and safe boundaries.
- `docs/research/P0_WP07_WHAT_WE_ADAPT.md`: primary-source mapping and no-novelty-overclaim review.
- `docs/research/WP07_INSTALL_STUDY.md`: integration and learning instructions.
- `docs/research/validation/wp07_focused_tests_2026-11-10.txt`: focused test log.
- `docs/research/validation/wp07_all_research_tests_2026-11-10.txt`: all available research tests in isolated source tree (prior-model source restored from ZIPs).
- `docs/research/validation/wp07_demo_2026-11-10.jsonl`: demonstration outputs.

## Actual tests run

- Python **3.13.5** in the isolated authoring environment: **50/50 WP-07 tests passed**, 0 failed, 0 errors.
- Combined research modules from WP-02 through WP-07: **168 tests discovered; 167 passed and 1 skipped**, no failures or errors. The skip belongs to an older source-dependent WP-05 test because the isolated work tree does not include the full original contract source; it is **not** a failing WP-07 test.
- The historical **106 project Python tests**, **52 Foundry tests** and complete CI were **not rerun in the authoring environment**. Foundry was not installed there. Host and hosted CI integration are pending.

## Assumption boundaries

**No real signature verifier or certificate validator exists in this prototype.** A caller can construct a `QualifiedFact` arbitrarily. Policy whitelists DO NOT make it cryptographically sound. Canonical chain snapshots are also entirely stipulated by the caller; no RPC/finality verification is performed. This source **must not** be connected to production financial transfers as-is.

**No deployed SLA policy change.** Existing Solidity quorum policy has not been altered. The alternative chain-publication SLA is *not* a substitute for cloud-resource delivery.

## Next gates

1. Put the deliverable source/test/docs in the WP-07 research branch and execute full host Python discovery and Foundry regression.
2. CI three jobs on a draft PR; merge research model only after review.
3. R4: build a real proof qualification boundary with canonical crypto/hash/time binding and trusted/conditionally trusted validators.
4. R2: design and audit new on-chain policy version. Preserve old funded lease semantics; require explicit consent for new service contract terms.
5. P0/P2: systematic literature comparison and formal proof obligations beyond finite tests.
