# R3 WP-09I — Coordinator-bound standard VRF integration and no-reroll lifecycle

**Date:** 2026-11-14  
**Status:** Offline-only design + executable Python reference. **No GitHub Actions, pushes, commits, testnets, deployments, paid services, Foundry or Solidity compilation.**  
**Prior work:** WP09E draft PR #26; WP09F adversarial bias; WP09G batched 40-index recovery; WP09H signer-receipt/quorum study.

## Executive result

WP09I replaces the speculative idea of a custom RSA-root threshold protocol with a **design for consuming an established VRF coordinator's verified output**, specifically Chainlink **VRF v2.5 subscription** on a supported EVM network. Unlike WP09D, the proposed Solidity adapter **does not verify the VRF proof itself**; it trusts the designated coordinator to verify the proof on-chain and authenticates callbacks through `VRFConsumerBaseV2Plus` with an additional immutable coordinator pin. The key hash and subscription must be supplied from actual network-specific official configuration; **none are invented here**.

The executable Python model is a **callback/settlement-policy state machine**, not a local Chainlink instance or a cryptographic VRF implementation. It accepts mock coordinator callbacks for testing policy; these mock inputs provide **no verifiable randomness**.

## Offline artifacts and validation

- `wp09i_vrf_policy.py`: immutable request binding; frozen chain / consumer / lease / VRF request ID / global roster root+count / request block / deadline / coordinator keyHash and version. Authorization for settlement-issued requests, governance-only future-profile rotation, profile retirement blocked while old requests remain in flight. Scoped `(coordinator, vrfRequestId)` routing protects against collisions on coordinator migration. One request ever per assignment; duplicate and late callbacks do not replace output. Separate permissionless seed application and fail-closed expiry. **No reroll, seed fallback, or punitive assumptions**.
- `test_wp09i.py`: **25/25 standalone Python tests passed**, including wrong caller, unauthorized profile migration, old-coordinator in-flight fulfillment, cross-coordinator ID collision, wrong-lease and wrong-roster digest, invalid random-word lengths, deadline boundaries, duplicate/late callbacks, permanent replay protection, expiry, no seed substitution and connection to the preceding offline WP09G 40-candidate batched-selection model.
- `wp09i_reroll_experiments.py`: deterministic exact combinatorial calculations, with `reroll_attack_metrics.csv` and `experiment_results.json`. No external network data or generated VRF proofs.
- `WP09I_VRFV25_ADAPTER_DRAFT.sol`: **UNCOMPILED Solidity integration sketch** using Chainlink v2.5 contracts. It is **not drop-in deployable**: the Chainlink package must be pinned; current SSESettlement must be modified to call `requestSeed` *once* per committed assignment; address-bootstrap cycles must be resolved (e.g., with CREATE2 / two-stage wiring); `OpenMonitorCommittee.randomnessSource` must authorize the adapter, with the pool using legacy entropy callback mode and optionally WP09E Merkle global election. Only a live coordinator+mock EVM integration can validate that interface. Do not deploy this draft.

## Architecture and mandatory security rules

1. **Freeze the full eligibility commitment** (WP09E root, count, lease parties, monitor bond rules and current registered candidate snapshot) **before** requesting randomness. Never accept membership-changing parameters that reassign the election's originally committed roster after the request.
2. The bounded pool has `assignmentStatus = AwaitingRandomness`. A settlement-authorized call requests exactly one word from a **pre-configured** coordinator and gas lane. Record the external coordinator request ID and immutable lease commitment. Deny a second request for that assignment even after timeout/expiry.
3. **Authentication / proof boundary:** with Chainlink VRF v2.5, the coordinator verifies the provider's cryptographic proof; the consumer accepts only authenticated coordinator callbacks. The consumer contract **does not independently verify a VRF proof**. A local Python caller-name equality check is *not equivalent to EVM `msg.sender` authentication*.
4. **Callback must be minimal and non-reverting for normal/duplicate/late cases**: store one uint256 output and transition to `Ready`. Do not perform Merkle proof verification, perform selection, or pay escrow inside the VRF callback; the coordinator will not automatically retry a failed fulfillment callback.
5. A separate permissionless `apply` derives a domain-separated seed bound to the frozen lease, global root, request ID and provider output, and calls the existing `OpenMonitorCommittee.fulfillRandomness`. The pool must be deployed with **`randomnessSource = adapter`**. The WP09E global mode then enters `pendingGlobalSeedReady`, and WP09G's optional offline batch-proof design could finalize the committee in another bounded operation **after it is compiled/integrated**.
6. On missing VRF fulfillment at deadline, transition to `Expired`, clean up any provisional WP09G locks, and authorize only the **existing** pre-epoch SSESettlement consumer refund path. **Do not fallback to a new blockhash, second VRF request, alternate signer, or restarted nonce for the same committed election.** A later callback must not resurrect it. Subscription fees are **not automatically refundable**.
7. **Coordinator/key migration:** Choose network coordinator and `keyHash` from trusted official network configuration. Freeze configuration per request. Rotate only for future requests, and retain the old authenticated coordinator until its last in-flight request is terminal; otherwise callback completion is denied. The Python model demonstrates safe routing, but the draft Solidity adapter intentionally has **no migration feature**: for a new coordinator, deploy a new properly wired adapter/pool or design and audit an independent immutable-authority router. Old requests cannot be silently rebound.
8. **Important inherited-migration caveat:** current `VRFConsumerBaseV2Plus` exposes `setCoordinator` for upgrades. An owner or coordinator may move the base's mutable pointer. The draft independently pins `pinnedCoordinator`, rejects new requests when the base pointer no longer matches, and refuses to store callbacks whose `msg.sender` differs from the pin. **This prevents an injected new-coordinator seed, but it does not preserve liveness if the base is migrated.** Audit inherited ownership/migration behavior before deployment; do not claim an immutable base from its use alone.
9. **Budget controls and economic assumptions:** Chainlink VRF subscription requests incur fees denominated in network/native asset or LINK, separate from GitHub Actions. Configure maximum number of outstanding funded leases, request fee escrow/budget and rate limits before actual network usage. Callback gas/confirmation parameters depend on supported chain; no network or subscription balance was accessed or funded here.
10. **Independent monitor operators and truthful service observations are separate requirements.** VRF output can be cryptographically sound and still select multiple EOAs controlled by one entity, fail under adversarial network partitions, or report incorrect physical SLA truth.

## Analytical attack results (not a network benchmark)

Hypothetical registry: **160 active EOA identities, 40 attacker-controlled, 4 committee seats**, ideal uniform sampling without replacement. The probability at least one seat belongs to the adversary in a single independent, unbiased election is

\[ p=1-\tbinom{120}{4}/\tbinom{160}{4}=0.6875919398684738. \]

If an attacker may selectively abandon unfavorable outcomes **and obtain independent retries for the same intended assignment**, the probability of *finding at least one favorable draw* after `r` attempts becomes `1-(1-p)^r`:

| Independent draws available | Probability at least one favorable draw |
|---:|---:|
| 1 | 68.7592% |
| 2 | 90.2401% |
| 3 | 96.9509% |
| 5 | 99.7023% |
| 10 | 99.9991% |

This is a counterfactual **grinding opportunity model**, not an actual Chainlink VRF or adversary simulation on the user's chain. It motivates permanent non-replay/one-draw commitment.

**No-reroll does not imply no bias.** If a malicious coordinator/proof provider can withhold every unfavorable proof, among published elections the attacker-hit rate may still be 100% while only about 68.76% of assignments finalize. Preventing rerolls closes one avenue of manipulation; economic fairness and availability under **selective withholding** remain unproven. A single coordinator is also a dependency and may delay or fail, even with proof validity. Additional signer receipts or naive blockhash fallback do not fix this.

## Exit criteria and next work

- Install and pin a supported Chainlink package locally, **compile** the draft against the exact interface and fix any version mismatch. No Actions needed: `forge build`, local Anvil and `forge test`. Do **not** use any live subscription or testnet unless explicitly approved.
- Implement a specific settlement → adapter single-request hook, deterministic deployment order, terminal paths, bounded callback work, and exact escrow/VRF-fee accounting.
- Add local mock-coordinator EVM tests for authenticated/unauthorized callbacks, coordinator migration, duplicate/late outputs, reordering, requesting once, expiry, and WP09E global proof finalization.
- Benchmark gas for 40-index batched Merkle finalization and reveal failure paths. Decide whether a provider-independent beacon or threshold scheme is needed for withholding/liveness research; separate from provider-proof correctness.
- Revisit the scientific acceptance gate: no unconditional global uniformity claim until effective participation, Sybil/oracle independence, finality and selective-abort bounds have been experimentally and formally addressed.

**Recorded project progress stays R3 38%, engineering 26%, research 26%, total 26%.** This work is an offline research prototype, not compiled deployed Solidity. No GitHub workflow was invoked or triggered.

## External protocol documentation (reference only; no network transaction)

- Chainlink VRF v2.5 security considerations: https://docs.chain.link/vrf/v2-5/security
- Chainlink VRF v2.5 getting started: https://docs.chain.link/vrf/v2-5/getting-started
- Chainlink VRF v2.5 subscription: https://docs.chain.link/vrf/v2-5/overview/subscription
