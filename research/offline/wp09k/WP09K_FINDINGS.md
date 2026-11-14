# WP-09K technical findings — VRF subscription cost and lease closure races

**Research-only, 2026-11-14.** Entirely offline, based on the draft WP09E source and the WP09J uncompiled integration package. No GitHub Actions, pushes or deployments. This report does not assert Solidity compilation or EVM correctness.

## Architecture and previous limitations

SSESettlement issues a lease-backed pool assignment; OpenMonitorCommittee records an immutable requested-at timestamp and frozen eligibility commitment; SSEVRFV25Adapter dispatches one VRF v2.5-compatible subscription request and binds a coordinator-generated request ID to this assignment. The coordinator's VRF proof verification is **outside this adapter**, and the bundled mock verifies nothing. After callback, any caller can apply the random word. If WP09E global-Merkle mode is enabled, the seed is staged until a separate inclusion-proof transaction selects four monitors.

WP09J left three economically/operationally significant paths open:

1. **Unauthorized subscription spend:** any account could request the subscription-funded VRF result for an offered lease. An attacker could create low-escrow leases and make the application sponsor pay per request. Subscriber budget depletion is especially important when the request is relatively cheap to create and the coordinator charge is not funded by the caller.
2. **Refunded lease, unfinalized seed:** the consumer could close/refund the lease between coordinator callback and seed application, but WP09J did not inspect settlement's lease status when calling `pool.fulfillRandomness`. This could lock unrelated monitor bonds for a dead lease.
3. **Refunded lease, already-staged seed:** global Merkle election is two-phase (apply seed, then prove members). Simply checking the lease status in the adapter does NOT prevent a relayer from finalizing an already-staged seed after closure. A pool-facing cancellation hook is required.

## WP09K changes

| Security boundary | WP09K behavior | Important limit |
|---|---|---|
| Sponsor-funded subscription | Only bootstrapper/sponsor EOA can request, and only after provider accepts | A temporary **centralized** funding gate, not a permissionless fee market or cost cap on the sponsor |
| Request identity | `requestSeed(leaseId, assignmentId)` stores the lease mapping; `isLeaseRandomnessOpen` cross-checks both IDs | No independent proof that `lease.consumer` owns the underlying physical service |
| Reentrant coordinator | `assignmentEverRequested` set *before* request call; revert atomically restores it | A reviewed real coordinator still required; mock has adversarial hooks only |
| Callback application after close | Re-checks `Accepted`, matching assignment and no committee copy | Callback may store a word after closure, but `apply()` cannot use it |
| Early close while waiting | Settlement calls pool `cancelUnassigned`: releases `pendingSelections` or global staged state | Already-paid coordinator fee is not refunded by the chain |
| Close after pool selection, before settlement committee copy | Pool decrements four `activeAssignments` and deletes standbys; state becomes Released | Strictly intended for the settlement pre-epoch closure path |
| Close after global seed staging | Pool clears `pendingGlobalSeedReady` and `pendingGlobalSeed` before returning from settlement close | This prevents later `finalizeGlobalCommittee` from creating locks |
| Close after committee copied | No early pool release; existing evidence and release logic remains | The previous evidence/accounting rules still govern; not altered here |
| Timeout | One request only; expiry or closure ends election with no alternate seed | Withholding remains a liveness failure, not a solved cryptographic issue |

## Precise invariants and ordering

- **No funded VRF purchase before provider accepts**, and no purchase by any arbitrary address; only a configured sponsor may initiate spending. (This is not fee-backed decentralization.)
- **One coordinator purchase per assignment** if successful. Failed coordinator transactions revert all adapter state. A repeated or nested request for the same assignment is prohibited.
- **No new post-closure bond locks.** Even after a real authenticated callback or a global staged seed, settlement closes atomically with pool cancellation. The pool rejects both the old callback application's attempt and any follow-on global-finalize attempt.
- **No unlocked committee before proof/reward conditions**: after the committee has been finalized into settlement, WP09K does not bypass prior monitoring confirmation or evidence-release requirements.
- **Consumer escrow is conserved** in the restricted modeled pre-epoch close path. Solidity escrow and payment invariants have not been mechanically proven for this patch yet.
- **Historical version compatibility is fail-closed**: patcher demands exact, singular source anchors from WP09E/WP09J. It refuses unknown versions, nonempty destination, existing VRF files and output inside the source checkout.

## Verification completed and not completed

- **Completed:** 19 offline Python checks, including 10 patch/structural guards and 9 policy tests, 48,000 deterministic model steps, mock attack-hook presence and read-only input/output checks. Plus 25 previously authored WP09I reference tests replayed locally. **44 Python tests passed**.
- **Authored, NOT executed:** 15 Foundry test functions (including 8 new WP09K-specific controls). These require an installed local Forge/solc and the project's dependencies. The mock coordinator explicitly performs **NO VRF proof verification**.
- **NOT done:** Solidity 0.8.24 compilation, EVM execution, gas measurement, multi-process coordinator availability testing, production chain integration, formal audit, cryptographic VRF verification, subscription billing measurements. Do not misstate the Python state-machine test as equivalent to EVM.

## Known remaining research / security obligations

1. **Remove temporary centralized sponsor gate safely:** introduce user-funded VRF cost escrow, quote/charge limits, per-request anti-grief constraints, and refund/slashing rules without granting a malicious caller control of randomness rerolls.
2. **Canonical reviewed VRF coordinator and consumer:** use verified network-specific key hash, subscription, coordinator address, consumer permissions, and correctly funded v2.5 request/response. The adapter does not contain a VRF proof verification primitive.
3. **Request/abort fairness:** authorization prevents trivial subscription drainage but may let the bootstrapper strategically omit or delay unfavorable requests. No guarantee of unbiasable public availability yet.
4. **WP09G batched recovery integration:** existing optional global election still has an at-most-ten-member proof. The independently developed WP09G batched 40-candidate prototype was not integrated or EVM-validated in WP09K.
5. **Selection bias and Sybil/operator identity:** all previous unpredictability/withholding, dishonest operator and post-snapshot churn limits remain. Global Merkle membership proves inclusion, not organizational independence.
6. **Review closeLease economics:** the baseline close path refunds uncommitted escrow; physical service, provider liabilities and pre-epoch incentive accounting need separate professional review before public funds are at risk.

## Progress accounting

Unchanged recorded estimates: R3 **38%**, R4 **38%**, P4 **20%**, engineering **26%**, research **26%**, overall **26%**. WP09K hardening is **offline authored and model-tested**, not an accepted on-chain milestone. No GitHub Actions were started, no commits/pushes/deployments occurred.
