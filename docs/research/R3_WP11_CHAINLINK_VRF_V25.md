# WP-11 — VRF v2.5 coordinator-bound randomness for V2 monitor selection

## The decision

Do not implement a home-grown VRF or treat a locally generated `seed` as a proof. Use Chainlink **VRF v2.5 subscription mode** and its coordinator's on-chain cryptographic proof verification. The SSE adapter trusts only the **configured coordinator contract address** to deliver the random word. The adapter binds that word to one previously frozen V2 assignment, and then authorizes the pool's existing deterministic sortition.

This provides a **real coordinator-ABI integration**, NOT a verified live-oracle deployment. The adversarial unit tests use a mock coordinator and therefore do not prove the cryptographic VRF or coordinator correctness.

Official interface/operations references:
- https://docs.chain.link/vrf/v2-5/overview/subscription
- https://docs.chain.link/vrf/v2-5/getting-started
- https://docs.chain.link/vrf/v2-5/security

## Contract wiring

```text
[SSEVRFV25Adapter deployed first]
  - immutable coordinator address + requester/operator, keyHash, subscription ID
  - keyHash and billing config require independently confirmed network deployment
         |
         v
[ScalableMonitorCommitteeV2 deployed with:
   randomnessSource = adapter, verifier = adapter]
         |
         v
[adapter.bindPool(pool) one-time, only bootstrapper]
         |
         v
[Pool enrollment, exactly one ticket per address per assignment]
         |
         v
[Enrollment closes, immutable rosterHash and assignmentCommitment]
         |
         v
[Request operator calls adapter.requestRandomness(assignmentId)]
         |
         +--> Chainlink v2.5 coordinator.requestRandomWords({
                 keyHash,subId,requestConfirmations,callbackGasLimit,
                 numWords=1,extraArgs=encoded nativePayment flag
              })
         |                 |
         |         Chainlink VRF oracle constructs proof
         |         Coordinator verifies proof on chain
         |                 |
         +<-- coordinator.rawFulfillRandomWords(requestId,[randomWord])
         |
[Adapter stores word and derives:
 seed = keccak256(abi.encode(word, assignmentCommitment,
                            assignmentId, chainId, adapter address))]
         |
[ANYONE calls adapter.finalizeRandomness(assignmentId) by pool seedDeadline]
         |
[Pool.supplyRandomness(id,seed,abi.encode(requestId))]
         | only adapter may call as randomnessSource
         v
[Pool calls adapter.verify(commitment,seed,proof)]
   checks saved exact request, fulfilled flag, seed, frozen commitment,
   assignmentId, and that msg.sender is the pool
         |
         v
[Pool's existing 16-per-transaction deterministic selection + standby seats]
```

## Why this design

- **No arbitrary EOA seed:** only the immutably configured VRF coordinator may invoke `rawFulfillRandomWords`; the coordinator verifies VRF proof before callback. Our adapter does **not** implement ECVRF proof verification itself. A malicious/incorrect configured coordinator could feed fabricated results and must be ruled out by verified deployment configuration and trust assumptions.
- **No request grinding:** exactly one coordinator request ID per frozen assignment. Neither a second request nor resampling after an unfavorable result is allowed. A missing/late VRF response causes the V2 pool to time out/abort; there is no selective redraw.
- **Scope binding:** V2 `assignmentCommitment` commits chain ID, pool, assignment ID, frozen roster hash, candidate count, consumer/provider, committee K, quorum Q, and reserves. Adapter stores it at request time and mixes it with returned VRF word, assignment ID, adapter address and chain ID to derive the seed. The pool checks exact equality.
- **Callback decoupled from pool:** store the coordinator's result without a fragile nested pool transition in the callback. Any third party can deliver it to V2 later via `finalizeRandomness`. A callback after the pool's seed deadline remains recorded but cannot activate the committee; pool expiry proceeds normally.
- **Billed subscription protected:** only an immutable, accountable `requestOperator` is allowed to trigger subscription-funded requests. Otherwise an attacker could create many cheap assignments and drain shared VRF subscription credits. This preserves a centralized liveness/availability dependency: a missing operator must not be described as permissionless VRF requesting. Finalization **is** permissionless.
- **One-time pool linkage:** adapter deployed before V2 pool. Pool constructed with adapter as **both** randomness source and verifier; adapter then binds pool once, checking both addresses. This avoids circular constructor addresses/CREATE2 tricks.
- **No upgradeable coordinator:** coordinator, keyHash, subscription, payment mode and requester immutable. A network/key-lane upgrade means deploy a new adapter and pool generation, not silently swap the source of randomness.
- **VRF v2.5 ABI:** request structure and native-payment extraArgs encoding match the Chainlink v2.5 subscription interface. No Chainlink Solidity package is vendored in this research increment; the ABI is intentionally minimal.

## Testing (cryptographic limits explicit)

The Foundry file `foundry/test/SSEVRFV25Adapter.t.sol` uses `WP11MockCoordinator` to simulate callback authorization and request lifecycle. This test mock supplies an arbitrary word and **does not verify a VRF proof**. It is suitable for testing the SSE integration logic and detecting forged EOA callbacks, replay, wrong IDs, late words, preseed-roster errors, duplicate request IDs and wrong binding. It cannot validate a true oracle's bias-resistance.

Before production-like experiments, deploy and test against a real Chainlink VRF v2.5 coordinator and an adequately funded subscription with this adapter approved as a consumer; verify official coordinator address/code, keyHash/gas lane, chain availability, request confirmations, native/LINK billing, callback gas and cost. A live coordinator integration, audit and on-chain verification of expected output/VRF proof are **not yet demonstrated** by mocked Foundry CI.

## Open attack surfaces / research issues

1. **Coordinator and requester trust:** cryptographic proof checking is delegated to the independently authenticated coordinator; configured requester controls when each billable request happens. The requester could censor/delay; the adapter cannot force it to spend subscription funding.
2. **Callback timing and censorship:** pool deadlines may pass before the VRF transaction finalizes or callback arrives. Abort and bond release preserve liveness of deposited tickets but not service availability. Need a realistic waiting-period model and measured responsiveness before picking timeouts.
3. **Chain reorgs and oracle withholding:** enough confirmations reduce but cannot eliminate chain-finality/availability risks. Confirmations, coordinator access and RPC trust must be specified in P1.
4. **Sybil economics:** genuinely unbiased randomness still samples **addresses**, not independent economic entities. Preseed opt-in can be split into many Sybil wallets and funded by one operator.
5. **V2 funded lease:** WP-10 remains a separate dependent PR; the adapter modifies no service escrow payouts or physical qualification rules.
6. **Test deployment limits:** mock coordinator is intentionally insecure and never suitable for use with live funds, despite successful tests.
7. **Network migration:** v2.5 is the currently documented path; avoid deprecated legacy VRF v1/v2 coordinators.

## Integration dependencies and acceptance

- Base: draft PR #9 `research/r3-scalable-monitor-v2-wp09`; PR #10 (funded controller) is another dependent PR on #9. PR #8 chain authorization is separate.
- On approval of #9, retarget this PR to `main` and rerun all jobs before merge. No change is made to V1 settlement.
- Local acceptance: Foundry full suite plus focused adapter tests, Python on Ubuntu and Windows, no skips.
- Scientific acceptance: a real network/subscription coordinator callback and independently checked proof/coordinator deployment, plus gas/availability experiments and an explicit seed unpredictability/withholding threat model. Test-suite success alone is not that evidence.
