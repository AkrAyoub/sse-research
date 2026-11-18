# WP-09N — EIP-170 headroom, controlled gas, and reentrancy regression

Date: 2026-11-14. Basis: **the user's successful local WP-09M Foundry gas report** (`117 passed; 0 failed`), and read-only inspection of the `AkrAyoub/sse-research` main branch at commit `7e86edb9aff6a2e45eac940cf7ced3b2c88f2bea`. Local user test changes in `foundry/test/VRFAdapterIntegration.t.sol` and `foundry/test/VRFFeePolicy.t.sol` are **not** necessarily present on GitHub main; the user's local checkout is the definitive tested source. No hosted CI, remote Git writes, deployments or chain payments occurred in WP-09N.

## 1. Verified baseline from WP-09M

| Contract | Runtime bytes | EIP-170 headroom | Deployment gas |
|---|---:|---:|---:|
| `SSESettlement` | 23,661 | **915** | 4,930,346 |
| `OpenMonitorCommittee` | 20,697 | 3,879 | 4,406,158 |
| `SSEVRFV25Adapter` | 6,461 | 18,115 | 1,304,446 |

Ethereum's EIP-170 limit in this baseline is **24,576 bytes** (`0x6000`). Bytecode size is a **deployment correctness boundary**; exceeding it may make creation fail. This package uses a recommended **2,048-byte discretionary runway** as an engineering alert, not as a protocol limit. Source: https://eips.ethereum.org/EIPS/eip-170.

The 915-byte baseline is measured, **not** a claim that a refactor or new optimizer configuration was tested here.

## 2. New deliverables

1. `foundry/test/WP09NGasBench.t.sol`: **15 success-path EVM test cases** producing **16 `gasleft` measurements** for completed operations. Different roster sizes and legacy/global Merkle modes are explicit. Tests include registration, lease creation, fee-backed VRF request/seed application and ten-leaf global committee finalization. The coordinator is a non-cryptographic mock.
2. `foundry/test/WP09NWithdrawalReentrancy.t.sol`: **one new adversarial EVM regression**. A contract consumer closes its lease, withdraws its refund, and tries to reenter `withdraw()` from `receive()`. It should receive exactly one payout and record that the nested withdrawal was blocked.
3. `tools/wp09n_local.py`: **isolated compiler optimization sweep** for runs 1, 50, 200 and 500. Uses `FOUNDRY_OPTIMIZER_RUNS`, `FOUNDRY_OUT`, `FOUNDRY_CACHE_PATH` and `FOUNDRY_OFFLINE`; checks resolved configuration before building, compares full deployed runtime bytecode from Foundry JSON artifacts, and writes `.local/wp09n/optimizer_sweep.csv`. It NEVER edits `foundry.toml` or production sources.
4. Same tool also runs benchmarks, saves **success-only** CSV `success_call_gas.csv` and raw Forge log. It refuses to report measurements if Foundry reports a failure.
5. `tests/test_wp09n.py`: **15 passed offline Python tests**, including configuration-isolation and fail-closed safeguards. They **do not** compile or execute Solidity.

### Measurement definition

`gasleft()` is sampled immediately before and after the successful call. It includes the caller-frame EVM instruction overhead and the nested contract execution, but excludes 21,000 intrinsic transaction gas, actual calldata fees, network inclusion costs and real VRF coordinator charges. These are **local relative gas benchmarks**, not live on-chain transaction receipts. For registered-member-count `n`, `register` measures registering identity `n+1` after `n` eligible members exist. `createLease` measures a single lease with exactly `n` active identities. The global election benchmark verifies exactly ten drawn Merkle leaves, with all candidates remaining active. Each benchmark is one independent Foundry test with a fresh setup; these are not independent statistical replicates and are not stress-test throughput metrics.

One global election case may consume substantial *test* gas due to setup of 160 historical registrations; that setup is excluded from the reported `gasleft()` delta.

## 3. Security warning triage (read-only source review)

**Withdrawal reentrancy — pending new EVM test, design appears appropriately guarded.** In `SSESettlement.withdraw()`, `withdrawalEntered = true` and `withdrawable[msg.sender] = 0` occur *before* the external ETH `call`. The guard is then reset after successful transfer. A linter warning alone does not prove exploitability. The new EVM attack-regression explicitly checks this path; do not mark it cleared until it runs.

**Subscription-spend reentrancy — existing EVM tests passed.** `SSESettlement.requestLeaseRandomness` validates funded request, lease state and cap, sets `vrfPurchaseEntered`, consumes prepaid fee and increments quota *before* calling `randomnessAdapter.requestSeed`. Earlier WP-09M Foundry tests include coordinator reentry and failure rollback. The linter reports an external call, but the source guard and tests are relevant mitigating evidence. Further work should threat-model arbitrary VRF coordinator migration and callback gas-budget constraints.

**Lease-closure call ordering — review required before production.** `closeLease` calls the bound committee pool's `cancelUnassigned` when a committee has not been copied into settlement; this is an external contract call before setting `Closed`. The specific pool's `cancelUnassigned` currently performs local state updates and does not call an arbitrary untrusted recipient. Nonetheless, the pool/settlement trust boundary and upgrade policies must be reviewed. Existing Foundry tests cover closing pending/seed-staged/selected assignments.

**Timestamp warnings — expected but safety-sensitive** due to timeout/expiry rules. Ensure off-chain operations tolerate chain time drift and exact boundary differences. Do not suppress without explaining validity assumptions.

**Outstanding high-priority risks**: `SSESettlement` runtime size headroom; global sample limited to first **10** indexes (WP09G's 40-index batched recovery remains **unmerged/uncompiled**); insufficient standbys after registration churn; third-party VRF coordinator dependence; off-chain delivery-proof soundness; the `RSA2048EntropyVerifier` path's non-standard single signer/withholding tradeoffs.

## 4. Decision gate

Run the optimizer sweep and EVM benchmarks on the user's Foundry machine. A smaller bytecode profile is a **candidate**, not a result of a safe architectural refactor, and must be checked against the *full existing suite*. Optimizer run count changes the tradeoff between deployment code size and runtime gas. Do not choose the smallest size without measuring operational gas and verifying all tests. If every profile still leaves <2 KiB code headroom, prioritize extracting independent logic into a separately deployed module/library; moving `SSESettlement` storage state without planned storage and authorization boundaries is unsafe.

**EVM run status at package creation:** 16 new Solidity tests authored, **not executed here** (Forge/Solc not installed in the ChatGPT container). No change to existing 117-pass baseline until the user runs the 16 tests and full suite on their computer.
