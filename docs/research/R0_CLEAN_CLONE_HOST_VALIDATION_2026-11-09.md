# SSE R0 — Independent clean-clone host verification

**Evidence date:** 2026-11-09. **Evidence type:** user-supplied Git Bash log from a separate `sse-clean` checkout in a Windows temporary directory. **Gate:** clean-clone verification **PASS**, hosted CI **NOT YET DEMONSTRATED**.

## Observed results

- Fresh `pip install -r requirements.txt` completed successfully in the new `.venv-r0` environment with Python 3.12-compatible pinned wheels (e.g. `pydantic-core==2.33.2`, `ckzg==2.1.8`).
- `python -m pip check`: `No broken requirements found`.
- `python -m unittest discover -s tests -v`: **106 tests, OK**, in **11.591s**.
- Tests included cryptographic signed-monitor adapters and the fake-chain controller state-machine simulation. These are not independent physical delivery proofs.
- `bash scripts/install-contract-deps.sh`: successfully installed **forge-std v1.9.5** and **openzeppelin-contracts v5.0.2**.
- `forge build`: **42 Solidity files compiled** with **Solc 0.8.24** in **22.20s**, compiler run successful **with warnings**.
- `forge test -vv`: **35 tests passed, 0 failed, 0 skipped**, five test suites; two fuzz tests reported **256 runs** each.
- The observed prompt path was `/tmp/tmp.khWwr18ca1/sse-clean (main)` at the end of the transcript, distinct from the original source checkout.
- The newly supplied pasted log excerpt starts mid-installation and does **not** show the clean clone's `git rev-parse HEAD` or final `git status --short` output. The source commit expected by the preceding checklist is `45689eaeaac0f4f65b16f3e06e60c0133925ab59`; compare explicitly before closing R0.

## Remaining acceptance conditions

1. Verify or retain the actual clean-clone `git rev-parse HEAD` and `git status --short` output, plus precise source dependency provenance if needed for the release record.
2. Run `.github/workflows/ci.yml` in hosted GitHub Actions on `push` or `pull_request`, with all jobs green: `python` on `ubuntu-latest` and `windows-latest`, plus `solidity` on `ubuntu-latest`. Save exact commit SHA and CI run URL/logs.
3. Review the R0 acceptance record. **Do not mark R0 at 100% solely from the current host logs.**
4. Carry all reentrancy, timestamp, unsafe cast, uninitialized-local and event ordering warnings to **R2** for targeted review and adversarial tests; they are not resolved by successful compilation.

## Phase progress

- **R0: 95% (+5 percentage points from 90%).**
- All other R and P percentages unchanged.
- Equal-phase arithmetic mean: engineering **16%** (195/12 = 16.25%), research **6%** (40/7 ≈ 5.71%), combined **12%** (235/19 ≈ 12.37%), all rounded to nearest integer.

**Classification:** source present and tested; fresh-clone regression reproduced; hosted cross-platform CI and final R0 acceptance pending. User log independently supplied, not executed in this inspection container.
