# WP-09J — Offline SSE ↔ VRF v2.5 adapter integration bundle

**Date:** 2026-11-14  
**Status:** Solidity implementation + Foundry tests **AUTHORED, NOT COMPILED/EVM-TESTED** here. Offline patch-safety and previously validated WP-09I policy tests passed.  
**Cost policy:** Never invokes GitHub Actions, pushes, cloud CI, public networks, paid VRF subscriptions, or a deployment.

## Contents

- `contracts/SSEVRFV25Adapter.sol`: ABI-compatible subscription-request adapter, pinned coordinator, scoped immutable VRF request ID, fail-closed callback, permissionless apply, timeout/no reroll.
- `contracts/MockVRFV25Coordinator.sol`: **INSECURE mock** that simulates coordinator callbacks but **does not verify a cryptographic VRF proof**.
- `foundry_test/VRFAdapterIntegration.t.sol`: **UNEXECUTED** local Foundry tests covering settlement requests, callback authentication, no-reroll, timeout/refunds, 4-of-4 confirmations, proof-verified *membership* via WP09E Merkle root. The VRF proof itself is NOT verified by the mock.
- `apply_wp09j.py`: fail-closed, offline source integration generator. Reads an existing WP09E-era repository checkout and writes patched contracts into **a separate output folder**, never modifies the checkout.
- `tests/test_wp09j_offline.py`: 17 local patcher and structural guard tests.
- `policy_reference/WP09I_offline/`: four files from the prior WP09I package to rerun its 25 Python state-machine tests.
- `WP09J_FINDINGS.md`: full design, trust boundaries, deployment order and risks.
- `wp09j_offline_tests.log` + `wp09i_policy_tests.log`: actual local Python test output.

## Running tests here (no network, no Solidity compiler)

```bash
python -m unittest discover -s WP09J_offline/tests -v
(cd WP09J_offline/policy_reference/WP09I_offline && python -m unittest -v test_wp09i.py)
```

## Applying locally once you have a checkout

**Do not push and do not enable any CI.** If your existing local repo is on `research/r3-wp09e-global-merkle-election`, run:

```bash
python WP09J_offline/apply_wp09j.py \
    --repo /path/to/your/local/sse-research \
    --out /tmp/wp09j-patched
```

Inspect `/tmp/wp09j-patched/wp09j_changes.patch` and the generated files. To compile/test, copy or synchronize *only* its `contracts/` and `foundry/test/` files into an **isolated disposable local clone** of the WP09E codebase and run:

```bash
forge build
forge test --match-contract VRFAdapterIntegrationTest -vv
forge test --match-contract VRFAdapterGlobalMerkleTest -vv
forge test -vv
```

Foundry (`forge`), Anvil and solc are **not installed in the ChatGPT runtime** and external network downloads failed, so these commands **were not run**. GitHub Actions are not needed for them. The repo must have its pinned OpenZeppelin, Foundry and existing libraries installed **locally**.

## Deployment/wiring order for an isolated **local simulation only**

1. Deploy `MockVRFV25Coordinator()` (not real VRF).
2. Deploy `SSEVRFV25Adapter(coordinator, keyHash, subId, confirmations>=3, callbackGasLimit>=100000, nativePayment)`.
3. Deploy `OpenMonitorCommittee(address(adapter), bond, exitDelay, randomnessTimeout)` and optionally `enableGlobalMerkleElection()` while empty. **Do not** enable WP09C blockhash or WP09D custom RSA mode.
4. Deploy `SSESettlement(address(pool))`; bind `pool.bindSettlement(address(settlement))`.
5. One-time `adapter.bindPoolAndSettlement(address(pool), address(settlement))`.
6. One-time `settlement.bindRandomnessAdapter(address(adapter))`, before first lease.
7. Register bonded monitors; create/fund lease; optionally accept by provider.
8. Anyone calls `settlement.requestLeaseRandomness(leaseId)` once, triggering the configured coordinator request.
9. The mocked coordinator calls `adapter.rawFulfillRandomWords(vrfId, [word])` with its test-only `deliver`. **Real coordinator would verify VRF cryptography before this callback.**
10. Anyone calls `adapter.apply(assignmentId)`. This calls the pool's existing `fulfillRandomness` path with a lease-bound seed. If global roster mode, a relayer must additionally supply all frozen-root proofs to `pool.finalizeGlobalCommittee`.
11. Provider accepts lease (if not already), `settlement.finalizeMonitorCommittee`, and all four monitors must confirm before epochs.
12. If coordinator withholds/late or proof finalization fails, no reroll; after the pool's timeout call `adapter.expire`, `pool.expire`, then consumer refunds unused escrow through `settlement.closeLease`.

**Production gate:** use an **official reviewed Chainlink VRF v2.5 consumer base**, network-approved coordinator/address/keyHash/subscription, funded subscription, correct callback/configuration and verified EVM tests. This standalone research adapter deliberately does **not** import `VRFConsumerBaseV2Plus`, so it should **not** be treated as a production consumer. Proof authentication is **only at the external coordinator**; the mock verifies none. Consult [official Chainlink v2.5 subscription and security docs](https://docs.chain.link/vrf/v2-5/overview/subscription) and https://docs.chain.link/vrf/v2-5/security.
