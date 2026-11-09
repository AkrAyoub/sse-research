# R0 WP-01 — reproducible validation transcript and status

**Date:** 2026-11-09. **Status:** PYTHON + FOUNDRY PASSED ON USER HOST, GIT BASELINE COMMITTED; **R0 GATE NOT YET PASSED**.

## Provenance

- Original archival baseline: `repo_original_2026-11-08.zip`; SHA-256 `d921cb6ca4ba80cad300bc25f00c15e73562ae7c0d05e74cf6de010661da438d` (confirmed locally).
- Baseline extracted from original archive and compared to the handoff's extracted `draft1_repo`: **zero diffs**.
- `02_AUDIT/SOURCE_SHA256_MANIFEST.csv`: **56 of 56 entries** verified using SHA-256 against unmodified baseline; **zero mismatches**.
- No Solidity files, original source tests, release keys or deployment secrets were edited.

## Actual inspection environment

- OS: Linux 6.18.57, x86-64 container (kernel build dated 2026-10-20).
- Python **3.13.5** (note the GitHub Actions matrix uses Python 3.12, not executed here).
- Installed FastAPI **0.128.2**, httpx **0.28.1**, Pydantic **2.13.5**, uvicorn **0.48.0**, not the pinned complete environment.
- **Missing:** `pycryptodome`, `eth-account`, `forge`, `solc`, `anvil`, `docker`. `python -m pip install 'pycryptodome==3.23.0'` failed because PyPI DNS resolution is disabled. This is **not evidence** that the pin is invalid.

## Commands executed (results, no extrapolation)

| Command | Observed result |
|---|---|
| `sha256sum 01_CANONICAL_INPUTS/repo_original_2026-11-08.zip` | Matched handoff provenance (above) |
| Compare all 56 SHA-256 source manifest entries | 56 matched / 0 failed |
| `python -m compileall -q /mnt/data/sse_r0_wp01` | **PASS**, Python 3.13 syntax compilation |
| Original `python -m unittest discover -s tests -q` | **41 tests discovered, 5 import loader errors**, `Crypto` missing; 0 Foundry test claims |
| Patched `python -m unittest discover -s tests -v` | **43 tests reported, 6 import loader errors and 7 subprocess smoke subtest failures**; missing `Crypto` / `eth_account` from runtime; **NOT A PASS** |
| `python services/monitor-agent/monitor_agent.py --help` | Still blocked by absent `Crypto` in this runtime; previous first missing import `challenge` is no longer referenced in source |
| `python -m pip install 'pycryptodome==3.23.0'` | **BLOCKED**: no DNS access to PyPI (captured stderr) |
| `forge build` / `forge test` | **NOT RUN**, Foundry absent; no Solidity compiler proof |
| Anvil/EVM/real VM integration | **NOT RUN**; no runtime or live ETH claims |

Subsets of existing tests that **actually passed** without optional missing packages, each executed with `python -m unittest discover -s tests -p '<filename>' -v`:

| File | Run / result |
|---|---|
| `test_control_auth.py` | 4 / 4 pass |
| `test_control_routes.py` | 7 / 7 pass |
| `test_enrollment.py` | 5 / 5 pass |
| `test_gitops.py` | 4 / 4 pass |
| `test_settlement_scenarios.py` | 5 / 5 pass |
| `test_role_agent.py` | 4 / 4 pass |
| `test_sse_residual_typed_data.py` | 4 / 4 pass |
| `test_m3_packaging.py` | 3 / 3 pass |

Total: **36 individual existing tests passed** in selected subsets (not the entire suite). New cryptographic adapter tests are authored but **not execution-verified** in this environment.

## Artifacts and immediate validation gate

- `validation/baseline_unittest_2026-11-09.txt`, `validation/wp01_unittest_2026-11-09.txt`, `validation/pip_install_2026-11-09.txt` contain the complete selected logs.
- On a connected Python 3.12 host: create new virtualenv, install `requirements.txt` cleanly, run `pip check`, full `unittest` and CLI smoke; execute Foundry dep setup + `forge build` / `forge test -vv`; record exact pins/commits, test counts and ABI hashes.
- Then verify synthetic signing tests against `SSESettlement.sol` EIP-712 on-chain hash/recover behavior. Any failures require code repair before R0 can be marked complete.
- Since dependencies and compiler could not be installed, **do not label WP-01 accepted** yet.

## External Windows Git Bash validation (user-supplied transcript, 2026-11-09)

- Foundry installation verified by `forge --version` and `anvil --version`: **v1.9.0** each.
- `bash scripts/install-contract-deps.sh`: completed, `forge-std v1.9.5` and OpenZeppelin Contracts `v5.0.2` installed.
- `forge build`: **passed**, compiled **42 files** with **Solc 0.8.24**, with compiler/lint warnings.
- `forge test -vv`: **35 passed / 0 failed / 0 skipped**, in five suites (4+9+4+11+7). Fuzz tests report 256 runs.
- These results come from the user workstation, not a new execution in the isolated review container. Exact tested Git HEAD and source equivalence with the WP-01 package have not been verified.
- Python 3.12 and full-suite results have since been supplied and passed (see subsequent 2026-11-09 Python host section); CI and clean clone remain outstanding.
- See `R0_FOUNDRY_HOST_VALIDATION_2026-11-09.md` for detailed warnings and follow-up checks. R0 stays IN PROGRESS (now 80% after subsequent Python host validation).

## External Windows Git Bash Python validation (user-supplied transcript, 2026-11-09)

- Interpreter: Python **3.12.10**, virtual environment `.venv-r0`.
- Pinned package installation: requirements already satisfied; `pip check` reported **No broken requirements found**.
- `compileall -q apps services tools tests`: no error reported.
- `unittest discover -s tests -v`: **106 tests passed / 0 failures / 0 errors** in **15.890s**.
- New typed monitor/signature and probe fixture tests passed. The controller test ran against a **fake chain**; the result is not proof of live network integration.
- Git metadata commands both failed: **not a git repository**. Source provenance/commit is therefore not externally verified.
- Full host evidence record: `docs/research/R0_PYTHON_HOST_VALIDATION_2026-11-09.md`. No tests were rerun in the isolated review environment based on these logs.
- Later Git initialization succeeded on the same working folder; see the new Git host validation section below. R0 now **90%**, pending clean-clone/CI/gate verification.


## User-host Git baseline update (2026-11-09)

- `git init -b main` succeeded; no existing `.git` was found at the searched depth.
- Initial commit `45689eaeaac0f4f65b16f3e06e60c0133925ab59` (`91 files changed, 8038 insertions(+)`) succeeded.
- `git status --short` printed no entries after the commit; working tree clean on the user's machine.
- The staged manifest excludes `.venv-r0/`, `lib/`, `out/` and generated secrets as far as the displayed 91 paths show. This excludes evidence of including those files, not a full audit of ignored/untracked files.
- `R0_PYTHON_HOST_VALIDATION_2026-11-09.md` is absent from the commit listing; add this record in a follow-on documentation commit.
- New root history does not establish earlier commit ancestry. No remote, CI run or clean-clone test is yet reported.
- R0 **90% (+10 pp)**; pending reproducibility acceptance.

## User-host independent clean-clone validation (2026-11-09)

The separate `sse-clean` checkout has now successfully installed pinned Python 3.12 dependencies; `pip check` passed; **all 106 Python tests passed**. The same clean clone successfully installed pinned Foundry libraries, compiled **42 files with Solc 0.8.24** (warnings), and **all 35 Foundry tests passed**. See `R0_CLEAN_CLONE_HOST_VALIDATION_2026-11-09.md` for the observed evidence and exclusions.

**R0 now 95% (+5 pp), not accepted.** Hosted CI status is still unverified; the supplied excerpt does not show clean-clone Git SHA/status. Retain security warnings for R2.
