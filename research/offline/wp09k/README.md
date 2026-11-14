# WP-09K — VRF subscription-spend and closed-lease safety hardening

**Date:** 2026-11-14. **Entirely offline and unmerged.** This is a **WP09E → WP09J → WP09K combined patch generator**; it is **not** a compiled/audited Solidity release. Never deploy or use paid VRF from the bundled mock. No GitHub Actions, GitHub writes, or paid services were invoked.

## What was fixed in the earlier WP09J integration design

1. **Subscription-spend griefing.** WP09J let *any caller* invoke `requestLeaseRandomness(leaseId)` for an `Offered` lease. Escrow can be tiny and unrelated to actual Chainlink subscription charges. WP09K requires the **deployer/bootstrapper sponsor** to call this function and the **provider to have accepted** before it dispatches paid VRF. This is an **explicit interim centralized safety trade-off**, NOT permissionless fair payment. Budget-backed permissionless dispatch must be designed before production.
2. **Closing a lease before applying VRF.** WP09J's adapter only inspected the *pool* assignment state, not the *lease*. In WP09K the settled lease ID is bound to the assignment ID and checked via `SSESettlement.isLeaseRandomnessOpen(leaseId, assignmentId)` both before a coordinator request **and** before applying its result. Closed leases cannot lock monitor bonds after callback.
3. **Closing a lease after global seed staging.** Even a lease-state guard in the adapter is insufficient after the adapter has staged a seed in the WP09E global Merkle pool: an unrelated caller could finalize the staged seed after lease closure. WP09K extends `OpenMonitorCommittee` with `cancelUnassigned(id) external onlySettlement`. `SSESettlement.closeLease()` calls it **atomically** when an adapter is bound and a committee has not been copied to settlement. This clears staged global entropy, releases a legacy pending snapshot, or unlocks a selected but not-yet-finalized four-seat committee. A previously expired pool is an idempotent cancellation case.
4. **Coordinator purchase reentrancy.** WP09J only marked `assignmentEverRequested` after the coordinator call. WP09K sets one-request state **before** the external call; the EVM reverts these changes automatically if the call fails. The mock can attempt a nested purchase or reject an order; tests check that the adapter cannot double-spend or lose its ability to retry a reverted request.

No reroll or alternate-seed fallback has been added. Raw callbacks still authenticate an immutable `pinnedCoordinator`, ignore duplicates/late values, and perform no pool call. Global Merkle inclusion-proof checks and 4-of-4 monitor confirmations are retained; they are not VRF proof verification.

## Files

- `contracts/SSEVRFV25Adapter.sol`: hardened standalone **research** adapter, no third-party imports.
- `contracts/MockVRFV25Coordinator.sol`: **INSECURE mock** with adversarial reentry/rejection hooks. **No proof verification**.
- `apply_wp09k.py`, `harden_source.py`: exact-anchor source transformations; read-only WP09E checkout, writes a **different** patch output directory and refuses unknown source versions / existing VRF files.
- `foundry_test/VRFAdapterIntegration.t.sol`: **15 authored Foundry tests, NOT run** (old integration + new spend, closure, cancellation, failure and mock reentry cases).
- `wp09k_policy_model.py`, `tests/test_wp09k_offline.py`: Python finite-state tests and structured patch checks. State model is not EVM execution and makes no security proof.
- `policy_reference/WP09I_offline/`: copied prior WP09I independent policy model and 25 tests.
- `verify_evm_locally.sh`: optional **disposable, offline** runner. Requires Foundry, Solidity 0.8.24 compiler and repository library dependencies to **already be installed**. Never installs or downloads anything and does not modify the checkout.
- `WP09K_FINDINGS.md`: detailed threat analysis, remaining gaps, test and progress tracking.
- `wp09k_offline_tests.log`, `wp09i_replay.log`: actual Python test logs.

## What was actually executed, for free

```bash
python -m unittest discover -s WP09K_offline/tests -v
(cd WP09K_offline/policy_reference/WP09I_offline && python -m unittest -v test_wp09i.py)
```

**19/19 WP09K Python tests + 25/25 WP09I Python tests = 44/44 passed.** The WP09K randomized model test ran 1,500 sequences × 32 steps = **48,000 deterministic model steps**. This counts steps within a model, NOT on-chain transactions or measured proofs.

## How to EVM-test later without GitHub Actions or paid services

Use a **local** WP09E checkout and locally installed Foundry dependencies:

```bash
bash WP09K_offline/verify_evm_locally.sh /absolute/path/to/sse-research
```

The script creates a disposable workspace using only `contracts/`, `foundry/`, `foundry.toml`, and `lib/` from your existing checkout (no `.git` or `.github`), applies the WP09K patch in a separate output folder, and runs `forge build/test --offline`. If Foundry/solc is absent, it **stops without installing or downloading anything**. It never runs `git`, pushes, deploys, or accesses any hosted runner. Inspect the generated unified patch and full test logs before considering merge/deployment.

**Foundry, Anvil and solc are absent from this chat runtime; the 15 Solidity tests were authored but NOT compiled or executed.** DO NOT advance R3 or project percentages on these Python-only checks. Never enable repository Actions just to run tests; use a locally installed compiler on your computer.
