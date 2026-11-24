# R244 — Real VM4707 R235 first new V2 integration test: 37/38; fix cross-contract selector assertion

**Operator observed, 2026-11-24.** Exact source `67243ad9830fd209dd53d1a539a3cc0d822d1371`,
fresh isolated checkout `/tmp/tmp.Ridv9nIavf/repo`, Foundry v1.9.0,
isolated Python virtualenv `/tmp/tmp.Ridv9nIavf/testvenv`.

## Actual evidence

- Python 3.12 isolated venv successfully installed pinned direct
  `eth-account==0.14.0`, `pycryptodome==3.23.0`,
  `eth-abi==5.2.0`, with `PYTHON_DEPENDENCIES_OK=true`.
- R235 exact SHA/source guard passed; `forge --version` was 1.9.0.
- **R226–R229 Python regression: 38 executed, 37 passed, 1 FAIL.**
  Failure:
  `test_every_canonical_action_has_unique_selector`
  asserting unique selectors **across two different deployed contracts**:
  `AssertionError: 20 != 21`.
- Valid `withdraw()` signature is declared by BOTH
  `SSEAdaptiveMarketV2` and `SSEAdaptiveVoteLedger`, yielding
  identical `0x3ccfd60b` selector. This is unambiguous at EVM call
  execution because `to` identifies the deployed contract.
  All other observed R226–R229 tests passed, including dynamic ABI
  offset, funded tuple, EIP712 public signature recovery, event
  attribution mocks and finalized lease state-decoding mocks.
- Because `set -euo pipefail` enforced gate fail-fast, **NONE** of
  R231–R239, R242, full Python suite, post-R236 contract compilation,
  V2 Foundry tests or full Foundry regression ran in that first attempt.
  Do not claim full source PASS.

## Exact GitHub-only correction

- Fixed ONLY `tests/test_sse_pos_r226_adaptive_v2_transaction_planner.py`
  to require **no selector collisions within each contract**, and
  expect exactly one cross-contract overlap: canonical `withdraw()`.
- Test additionally checks withdrawal plan target `market` and
  `ledger` point to DIFFERENT addresses, not just matching selectors.
- No contracts, keys, wallet, Docker, running original-chain clients or
  blockchain runtime were changed.
- Patch source commit:
  `dc6535b9bec82cbb0b51f9a103c57b4aa511038c`.
- Status **FIX COMMITTED BUT UNVERIFIED** until the user reruns the
  complete R235 gate on VM4707 at a newly pinned immutable SHA.

## Next operator action

On VM4707 re-use the existing isolated checkout and venv:
`cd /tmp/tmp.Ridv9nIavf/repo`;
fetch `feature/r226-adaptive-v2-operator-runtime`;
switch to exact GitHub SHA; prepend
`/tmp/tmp.Ridv9nIavf/testvenv/bin` and the original pinned Foundry
directory to `PATH`; run
`bash scripts/r235_vm4707_v2_source_only_gate.sh "$SHA"`.
Do not broadcast transactions or touch original VM4706 validator.
If new test fails, paste actual log; fix only via GitHub immutable commits.
