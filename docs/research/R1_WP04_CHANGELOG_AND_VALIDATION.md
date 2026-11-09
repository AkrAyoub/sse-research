# R1 WP-04 — Authoring, validation, and integration status

**2026-11-09. Status:** research-only, source and tests are delivered as a ZIP; **not merged into main; not run on the user's host or GitHub Actions**. No Solidity or economic contract changes.

## Deliverables

- `tools/sse_observability_reference.py`: finite possible-execution/evidence-projection model with explicit relative world soundness, financial bounds, intentionally unsafe evidence heuristics and an adapter to WP-02 raw observations.
- `tests/test_sse_observability_reference.py`: **30 new cases**, including partition-equivalence, output-generation versus delivery, compute work requirement, dishonest claims, omitted-world counterexamples, observation horizon constraints, and numeric conservation.
- `tools/sse_wp04_demo.py`: instructional three-scenario printout with cautious vs naive payout calculations.
- `docs/research/R1_WP04_OBSERVABILITY_AND_SOUNDNESS.md`: formal semantics, limitations, decisions, and next proof gates.
- `docs/research/P0_WP04_EVIDENCE_MECHANISMS_AND_GAPS.md`: focused primary-source research and what we might adopt, reject or defer.
- `docs/research/validation/r1_wp04_combined_tests_2026-11-09.txt`: full stdout/stderr from authoring-environment tests of three related reference modules.
- `docs/research/validation/r1_wp04_demonstration_2026-11-09.txt`: teaching demo output.

## Actual local evidence

Python stdlib 3.13 in authoring environment; executed from a local tree containing exact WP-02 and WP-03 reference source plus WP-04 module.

```
python -m compileall -q tools tests
python -m unittest discover -s tests -v
# 75 tests passed / 0 failures / 0 errors (19 WP-02 + 26 WP-03 + 30 WP-04)
python tools/sse_wp04_demo.py
# 3 case studies printed
```

The full SSE repository's original 106 tests and 35 Foundry tests were **not rerun here**. Hosting CI for the branch must be checked separately. No real network, independent provider/consumer VM, cryptographic proof verifier, external clock or production settlement transactions were executed.

## Scope/compatibility note

This ZIP includes source/test files from WP-03 for convenient dependency installation (and the new WP-04 source/test files). WP-02 source/test files are *not included* because they are already merged in SSE `main`; the local authoring test bundle used their exact source extracted from WP-02 package.

WP-03 uses a *ground-truth* simulation with logical ticks and static monitor connectivity. WP-04's finite universe is only sound if all actual possible executions are represented. The toy `unsafe_quorum_rule()` intentionally omits some real on-chain authorization/signature/time checks; these are **counterexample abstractions**, not executed SSE exploitation claims.

## Progress estimates, contingent on code integration

R0 100% (unchanged), R1 **43% (+8 pp)**, P0 **32% (+7 pp)**, P1 **40% (+10 pp)**, P2 **15% (+5 pp)**, P3 **25% (+5 pp)**, P4 **10% (+5 pp)**. Others unchanged. Approx equal-weight engineering **19%**, research **17%**, overall **19%**. Not 100%-acceptance statuses.

## Next gates

1. Sync GitHub, install missing WP-03 source/test files from this ZIP into research branch, add WP-04 files, run 30-case suite, full Python suite and Foundry regressions.
2. Push, create draft PR, get hosted CI Python Windows/Ubuntu and Solidity Ubuntu green; review code and visible diff.
3. Study whether chosen service SLA really requires *consumer* delivery versus provider result generation; resolve ADR-001 before changing settlement history filters.
4. Define separate certificates for verified positive observations and negative uncertainty; never infer physical failure from three timeouts under network partition alone.
