# SSE WP-04 — Install, test, read, and review

## Scope

This source package is **research only**. It includes the WP-03 trace source and tests because WP-04 imports them, together with WP-04 source, 30 new tests and explanatory research documents. The earlier WP-02 `sse_formal_reference.py` is expected from `main`, since PR #1 merged. No production Solidity or Python agent is changed by this ZIP.

## Local installation (Git Bash in your existing SSE Repo)

The ZIP's directories (`tools/`, `tests/`, `docs/research/`) are relative to the repository root. Extract while preserving relative paths. This must not overwrite `docs/research/PHASES_TRACKER.csv`, which is not in this ZIP. Inspect `git status --short` before and after extraction.

```bash
cd "/d/Ayoub/AUI/Fall_2026/Blockchain Application Development/Project/Repo"
git status --short
git fetch origin
git switch research/r1-observability-wp04
# Extract the supplied archive here (preserve folder structure)
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p 'test_sse_observability_reference.py' -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
./.venv-r0/Scripts/python.exe tools/sse_wp04_demo.py
forge build
forge test -vv
git status --short
```

The expected count from a repo that contains all three reference test modules plus the original 106 is **181** Python tests (106+19+26+30). This is an expectation, **not** a verified host/CI result. Foundry's previous 35 tests have not changed because no contracts were edited; they still must be rerun locally/CI for the branch.

If all checks pass:

```bash
git add tools/sse_service_trace_reference.py tools/sse_observability_reference.py tools/sse_wp04_demo.py
git add tests/test_sse_service_trace_reference.py tests/test_sse_observability_reference.py
git add docs/research/
git diff --cached --stat
git commit -m "R1: model observational equivalence and service-specific evidence limits"
git push -u origin research/r1-observability-wp04
```

Create a **draft PR** with base `main`, ensure Python Windows/Ubuntu and Solidity Ubuntu jobs pass, review the entire diff for accidental changes and confirm existing source semantics/financial flows remain untouched. Do not merge unreviewed code; merging reference code does not approve its interpretation rules as production evidence or settle ADR-001/002.

## Suggested learning order

1. Read `R1_WP04_OBSERVABILITY_AND_SOUNDNESS.md` sections 1-2: distinguish ground truth from evidence.
2. Run the demo to see three different observations and payment bounds.
3. Open `tools/sse_observability_reference.py`, read `Execution.projection`, then `observation_equivalence_class`.
4. Open the 30 tests, starting with `test_success_with_three_monitor_timeouts`, `test_response_seen_does_not_prove_consumer_delivery`, `test_missing_possible_execution_can_falsify_global_safety`, and `test_forged_or_untruthful_receipt_disproves_unconditional_soundness`.
5. Read the P0 mechanism comparison, then discuss which strong assumptions to approve for HTTP/compute before touching `SSESettlement.sol`.

## Why the evidence model is not deployed

It uses a finite pre-enumerated physical scenario universe, logical ticks and a simplified connectivity boolean. It includes *omniscient ground truth* only because a research simulator can stipulate physical events. A real monitor cannot know whether those events happened from timeout evidence alone. Proposed certificates and actual trusted receipt or proof verifiers are future R4; evidence semantics must be reviewed under R1/P1 first.
