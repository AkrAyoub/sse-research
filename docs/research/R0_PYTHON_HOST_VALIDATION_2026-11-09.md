# SSE R0 — Python 3.12 workstation validation

**Evidence date:** 2026-11-09. **Source:** user-supplied Git Bash output (not independently executed in the review runtime). **Status:** all reported Python unit tests PASS; complete R0 exit gate remains open.

## Commands and observed results

| Command | Observed result |
|---|---|
| `.venv-r0/Scripts/python.exe --version` | Python **3.12.10** |
| `.venv-r0/Scripts/python.exe -m pip install -r requirements.txt` | All specified packages already installed, including FastAPI 0.116.1, Pydantic 2.11.7, pycryptodome 3.23.0, eth-account 0.14.0 |
| `.venv-r0/Scripts/python.exe -m pip check` | **No broken requirements found** |
| `.venv-r0/Scripts/python.exe -m compileall -q apps services tools tests` | Completed without error output |
| `.venv-r0/Scripts/python.exe -m unittest discover -s tests -v` | **Ran 106 tests in 15.890s — OK** |
| `git rev-parse HEAD` | **fatal: not a git repository** |
| `git status --short` | **fatal: not a git repository** |

Previously supplied separate host transcript: Solidity 0.8.24 compiled 42 files; 35 of 35 Foundry tests passed using Foundry 1.9.0. These two test sets are not evidence of a clean clone or CI-run reproduction.

## Coverage and limitations

Successful Python suite includes EIP-712 typed-data tests, correct/incorrect provider signatures, unsigned-provider-response rejection, challenge binding, monitor-selection checks, local HTTP and compute behaviors, Docker inspection, control-plane route/auth tests, and a simulated controller flow. The controller test explicitly names `FullControllerFlowTest.test_full_flow_state_machine_with_fake_chain`; a fake-chain state machine does **not** establish a real-chain E2E run. No independent remote monitors or Ubuntu auto-onboarding have been demonstrated. The Solidity compiler also issued lint warnings requiring classification under R2.

## Remaining R0 exit criteria and immediate actions

1. Determine whether authoritative `.git` metadata/remote exists elsewhere. The tested folder has no available Git working tree.
2. Before staging files, add `.venv-r0/` to `.gitignore` and avoid committing locally generated keys, build artifacts, credentials, or the Python environment.
3. Recover/initialize Git provenance; capture exact commit (`git rev-parse HEAD`) and clean/staged state (`git status --short`) against the tested version. Do not pretend the historical handoff commit exists in a freshly initialized repository.
4. Verify a clean clone/release and GitHub Actions CI on Python 3.12 and Foundry, recording full logs and pinned dependency revisions.
5. Record CI results and compile/test environment metadata in the project tracker, then evaluate R0 acceptance criteria before marking 100%.

**Estimated phase progress:** R0 **80%**, +25 pp from the prior 55%. Other R1–R11 and P0–P6 percentages remain unchanged. Equal-weight means: engineering **15%**, research **6%**, overall **12%** (rounded).
