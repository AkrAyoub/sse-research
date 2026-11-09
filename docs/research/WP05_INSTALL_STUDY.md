# WP-05 integration and study guide

1. Extract the WP-05 ZIP at the root of the **original** local SSE Git checkout. It adds the two new Python modules and two accompanying test/demo programs; the full original repo and Solidity contracts are *not* bundled or replaced.
2. Source-traced shadow implements contract time/authorization windows using a verified result flag, **not actual cryptographic verification**. The model's physical world is supplied by the test.
3. On a research branch based on the latest `main`, run:

```bash
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p 'test_sse_async_contract_reference.py' -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
./.venv-r0/Scripts/python.exe tools/sse_wp05_demo.py
forge build
forge test -vv
git status --short
```

Expected: 45 new tests and (if existing 106 and WP-02/03/04 modules are all present) **226 Python tests total**, plus 35 existing Foundry tests. *Counts are expected, not yet verified on the user host or hosted CI*. Review any discrepancy rather than inventing pass status. The files are stdlib-only.

4. Commit source+tests+docs only. Push branch, open a draft PR, examine all three GitHub Actions jobs (Linux/Windows Python and Linux Foundry). Merge reference code only if checks/review pass. **Do not merge a changed live evidence policy without separate proof review and differential tests.**
5. Study at code level: compare `EpochShadow.monitor_vote` with `SSESettlement._recordAuthorizedVote`, `EpochShadow.seal` with `sealMonitoring`, and `EpochShadow.admissible_after_contract_filters` with `settleEpoch`.
6. The first four JSONL demonstration lines are intentionally **counterexamples** to world soundness under stipulated physical conditions; the last is an uncertain clock reading. The proof boundary is conditional on those physical events and observed signatures.
