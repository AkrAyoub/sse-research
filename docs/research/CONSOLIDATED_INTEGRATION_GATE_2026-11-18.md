# Consolidated R7 + WP09M–Q working baseline (2026-11-18)

This branch is based on `research/r7-vm-role-operator-no-ci` at `51b1366557d2ea7e742296dc454d81b22a5d6410`, whose Solidity tree already includes the three WP09Q on-chain commits (the 40-index batched Merkle recovery, legacy close preservation and stack-pressure fix). It also includes R5/R6/R7 onboarding, identity, Tailscale primitives and R9 four-distinct-VM QBFT plan.

The separate user's `research/wp09m-q-local-recovery` commits `eca7300` and `16c8264` preserved an additional 24 original research source/evidence files. These are copied verbatim to this branch, without running their patch scripts. Existing R7 `contracts/OpenMonitorCommittee.sol`, `contracts/GlobalRosterSampler.sol`, `contracts/SSESettlement.sol`, and `foundry/test/WP09QBatchedGlobalRecovery.t.sol` are intentionally retained from the *already patched* WP09Q branch. The local recovery test file targets a different patch revision; do not overwrite the published WP09Q test without an explicit comparison. Existing R7 `VRFAdapterIntegration.t.sol` is also left unchanged pending the compiled integration tests.

## Safety and boundaries

- No GitHub Actions workflows exist on this integration branch. All checks run manually on the user's machines; do not merge to `main` automatically.
- Do NOT execute `apply_wp09q.py` against the already-integrated WP09Q Solidity files. It is preserved as a historic patch-guard test fixture.
- `SHA256_MANIFEST.txt`, `WP09N_PYTHON_VERIFICATION.txt` and measurements describe their *original local snapshot*, not this new integrated branch. Regenerate integrity hashes and benchmarks after validation.
- `research/r10-manual-qbft-lab-no-actions` is a disposable one-host smoke test, not the accepted R9 topology. The full QBFT plan is `docs/research/R9_MULTI_VALIDATOR_QBFT_POS_EXPERIMENT.md` on this branch: chain 31338 and four **distinct** validator machines. Do not use the one-host genesis ID/config as the multi-VM network.
- Preserve live Anvil VM4695 chain 31337, block 26, funding/acceptance receipts, existing keys, assignment 1 and escrow. Neither repo integration nor new chain work migrates those obligations.

## Manual acceptance gate

```bash
python3 -m unittest discover -s tests -v
forge build
forge test --match-path 'foundry/test/WP09QBatchedGlobalRecovery.t.sol' -vv
forge test -vv
```

Treat runtime bytecode exceeding 24576 bytes, actual spending under an untested VRF coordinator, failing bond-refund liveness, evidence-policy gaps and new role-peer WAN requirements as blockers. No acceptance is claimed until logs are produced at the exact integrated commit.
