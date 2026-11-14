# WP-09Q experimental batched global-election recovery

This branch is **not production verified**. It is intended for local Foundry evaluation only.

## Motivation
The previous global Merkle election always proved at most ten deterministic candidate indexes. If fewer than four were still eligible after the snapshot, the request failed closed even if the wider roster still had eligible candidates.

## Opt-in path
Before enrollment and settlement binding, the bootstrapper enables global Merkle mode and calls `enableGlobalBatchedRecovery()`. The seeded election then has up to forty deterministic indexes. A relayer submits the *next* one to eight indexed Merkle proofs per transaction with `advanceGlobalRecovery`. Finalization occurs only after the complete committed index sequence is processed. The default ten-index mode is preserved unless explicitly opted in.

The first four currently eligible identities receive provisional active-assignment locks and later form the committee; eligible later indexes become ordered standbys. The same initial seed is used throughout. An incorrect, reordered, omitted, or replayed proof fails.

## Cleanup and risks
Closing the lease or timing out before finalization releases provisional active-assignment locks. The settlement close path handles both adapter-bound and legacy entropy pools. If fewer than four eligible monitors remain after processing all drawn indexes, the request expires without a reroll.

**Known limitations:** proof withholding can still prevent timely finalization; the 40-index cap does not guarantee liveness when many candidates leave or when identities are Sybil-controlled. On-chain verification cost increases, and the 40-index draw is recomputed on each batch. The test harness uses a trusted deterministic seed, **not a verified production VRF**.

## Local test commands
```bash
forge build
forge test --match-path 'foundry/test/WP09QBatchedGlobalRecovery.t.sol' -vv
forge test -vv
forge test --match-test testBenchRecoveryFiveSuccessfulProofBatches -vv
```

Record `WP09Q|pool_runtime_bytes`, `WP09Q|settlement_runtime_bytes`, and the five `WP09Q|batch_call_gas` measurements. Compare both runtime sizes with EIP-170's 24,576-byte limit.

The branch also incorporates the WP-09L adapter reserved-keyword and test-fixture fixes that were locally validated as part of the 134-test WP-09P baseline. WP-09Q itself remains **uncompiled/unexecuted** until the local test run.

No hosted CI is required. The commit uses `[skip ci]`; do not create a PR or merge until confirming Actions will stay disabled/skipped.
