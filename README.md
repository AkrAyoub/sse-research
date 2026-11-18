# WP-09Q — Experimental 40-index batched global election recovery

**Status:** Experimental local Solidity patch, **NOT compiled or Foundry-tested by ChatGPT**. Its Python source-patch guards have passed locally. This is not a deployed feature, an audited design, or a proof of trustworthy entropy.

**Scope:** On a fresh deployment only, opt in to 40 ordered global sample indexes and verify all historical Merkle proofs in groups of up to eight. The existing ten-index path is preserved for deployments that do not opt in. No GitHub or public chain action is performed by the included scripts.

## Changes

1. `OpenMonitorCommittee.sol`: one-way `enableGlobalBatchedRecovery()` before settlement binding; `globalRecoveryDrawIndexes` and `advanceGlobalRecovery`. First four currently eligible proven monitors are provisionally bond-locked; remaining proven eligible monitors become ordered standbys. Every original drawn index is proven. No new seed can be requested.
2. `GlobalRosterSampler.sol`: raise the *internal sampler maximum* from 10 to 40. The existing `GLOBAL_SAMPLE_LIMIT` remains 10 for non-opt-in users.
3. `SSESettlement.sol`: allow `closeLease()` to cancel an unfinalized assignment even without the optional VRF adapter, freeing partial selections. This changes the closure path for legacy entropy deployments and requires the full regression suite.
4. `foundry/test/WP09QBatchedGlobalRecovery.t.sol`: end-to-end local tests covering ordering, Merkle tampering, no replay, 37 exited monitors, early close/timeout, locked-bond exits, and five per-batch gas measurements and live runtime-code-size measurements.

## Apply to a CLEAN local checkout of current main

Run commands in **Git Bash** from the repository root (with `foundry.toml`). Check your current changes first; the prior WP09L/WP09N/WP09P local edits should remain present.

```bash
git status --short
python -m unittest discover -s WP09Q_offline/tests -p 'test_*.py' -v
python WP09Q_offline/apply_wp09q.py --repo . --check > .local_wp09q_preview.diff
# Inspect preview diff before deciding to change three production files:
less .local_wp09q_preview.diff
python WP09Q_offline/apply_wp09q.py --repo . --apply
forge build
forge test --match-path 'foundry/test/WP09QBatchedGlobalRecovery.t.sol' -vv
forge test -vv
forge test --match-test testBenchRecoveryFiveSuccessfulProofBatches -vv
```

The `--apply` mode makes *local* originals in `.local/wp09q/prepatch/`; no `git commit`, `push`, PR, GitHub Actions, remote node or deployment. It refuses missing source anchors and already existing WP09Q Foundry test. It installs exactly one new Foundry test. If any build/test fails, **do not deploy, push or merge**; share the error. The Python patch can be checked before any changes.

## Gas/economics caveats

- This experiment is intentionally pessimistic about finalization: prove all 40 indexes, even if four seats are already selected, to prevent a relayer suppressing standbys via early completion.
- Up to 40 Merkle inclusion proofs of depth 20 are required (about 25,600 sibling bytes across five transactions, plus address/ABI overhead). Five batches are a structural bound, not a gas-sufficiency guarantee. The `_at` partial sampler is O(k^2) per draw and is recomputed per batch.
- Provisional seat locking increases the chance of liveness recovery but creates a potential griefing window. If relayers withhold subsequent batches, selected bonds are stuck until someone invokes permissionless expiry, or the consumer closes the lease. Need a keeper and economic-incentive model.
- A dishonest entropy provider can still withhold the seed. Merkle proofs establish *membership*, not honest randomness, operator independence, anti-Sybil defense, or physical service delivery.
- The live-ran WP09P baseline was **22,400 bytes settlement runtime at optimizer_runs=200**; adding code changes this baseline. A new actual-runtime measurement is mandatory.
- This experimental implementation should be considered only for **newly deployed** contracts. Existing deployed EVM contracts cannot be patched in-place.

## Acceptance gates

All WP09Q tests pass, all previous Foundry tests pass, source/reentrancy tests remain green, runtime contract sizes stay under EIP-170 (24,576 bytes), and each of the five proof batches fits the target-chain gas budget. Benchmark at N=16,160,1000 with measured gas and compare complete lifecycle cost, not only lease creation. No production rollout before external security review and confirmation of a real coordinator-backed VRF setup.
