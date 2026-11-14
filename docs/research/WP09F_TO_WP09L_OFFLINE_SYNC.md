# SSE WP09F–WP09L research sync (2026-11-14)

**GitHub Actions deliberately skipped: all commits to this branch must include `[skip ci]`. No PR has been opened for this branch. Disable Actions in GitHub repository settings before merging/cherry-picking into a non-skipped history.**

This branch is stacked on `research/r3-wp09e-global-merkle-election` (draft PR #26), and **has not been merged into `main`**. It includes the original WP09F–WP09L offline research packages and **generated research-only Solidity integration** in `contracts/` plus authored Foundry tests. All new Solidity must be compiled and tested with local Foundry before acceptance; offline Python results are not EVM verification.

## Local sync

```bash
git status --short
git fetch origin research/r3-wp09l-offline-integration-sync
git switch --track origin/research/r3-wp09l-offline-integration-sync
```

If you have local uncommitted changes, commit or stash them yourself before switching. Do not force-reset or overwrite local work.

## Local verification, NO GitHub Actions

Run in the checkout on a machine with Foundry 0.8.24 + project libraries already installed:

```bash
forge build --offline
forge test --offline -vv
forge test --offline --gas-report
python -m unittest discover -s research/offline/wp09l/tests -v
```

The new Solidity adapter is a **mock-coordinator research prototype**, not production Chainlink VRF. The coordinator/billing, selective withholding and epoch/exit economic invariants require independent review and EVM test. The `research/offline/wp09l/apply_wp09l.py` generator remains available for reproducing the patch on a clean WP09E tree.

The published R3 progress remains 38%, overall 26% until local EVM tests have passed.
