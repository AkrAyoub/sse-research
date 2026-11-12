# WP-12 — Local end-to-end V2 contract interaction

## Reason for doing this now

WP-09, WP-10 and WP-11 had each passed their own Foundry tests but had **not been run as one dependency graph**. A passing pool test does not establish that an actual funded lease can wait for that pool; a passing VRF adapter test does not establish a successful funded epoch; a passing payout test does not establish that randomness withholding or absent confirmations leave the original escrow protected.

This increment runs all three contracts together, through the real Solidity entry points in a single Foundry EVM environment. It is **not a multi-host experiment**, a real VRF-proof test, or a completed physical service-evidence pipeline.

## Integration graph

```text
Consumer --prefund 300--> SSELeaseControllerV2
                               |
                      requestAssignment (V2 pool)
                               |
Provider accepts --┐           v
                   └--> ScalableMonitorCommitteeV2 <--- per-assignment monitor tickets
                                 |
                      enrollments frozen (roster hash)
                                 |
              SSEVRFV25Adapter.requestRandomness(id)
                                 |
                      WP12InsecureLocalCoordinator (TEST ONLY)
                                 |
                 rawFulfillRandomWords(requestId, [word])
                                 |
              adapter.finalizeRandomness(id) -> pool.supplyRandomness
                                 |
                         selection in batches
                                 |
                        4 selected monitor seats
                            /           \
                  confirmations       no-show -> reserve replacement
                            \           /
                             Pool Active
                                 |
                controller.activateLease -> Live
                                 |
                     consumer.admitEpoch(requestHash)
                                 |
                  full fee PENDING, no automatic payout
                                 |
       +-------------------------+----------------------+
       |                                                |
 consumer + provider sign exact EIP-712 split      no signatures
       |                                                |
  withdrawable allocation                          unresolved escrow
       |                                                |
  withdraw credits                        deadline returns ONLY unused escrow
```

The mock coordinator is deliberately untrusted: any test can instruct it to deliver an arbitrary word. Its sole purpose is to exercise the **correct ABI/callback boundary** and ensure the rest of the V2 EVM flow consumes the correctly scoped word. This test neither verifies a Chainlink cryptographic VRF proof nor demonstrates an unbiased selection against a compromised coordinator.

## Tested complete lifecycle

One case funds a 300-unit lease (3 epoch slots × 100), enrolls eight bonded monitors, requests one simulated coordinator word, selects/activates the committee, and admits the first epoch.

- Epoch 0 is resolved **by exact bilateral consent**: provider 70, consumer 30.
- Epoch 1 is admitted but remains unresolved for 100, satisfying exposure <= 100.
- At service end, the committee expires permissionlessly and unused epoch-2 funding (100) becomes consumer credit, **without** assigning epoch 1.
- Later the parties sign an exact 20/80 allocation for epoch 1. The controller closes and both parties withdraw, so provider gets 90 and consumer gets 210, totaling 300.
- The monitor ticket deposits can be settled after pool release; no honest ticket is destroyed merely because the consumer stopped interacting.

The accounting invariant checked at each stage is

```
escrow = uncommitted + pending + providerCredited + consumerCredited + unusedRefunded
```

Cumulative credited fields remain in this equation after users withdraw; **contract-held balance is not identical to cumulative credits after withdrawal**.

## Other integration counterexamples

Seven new `SSEV2IntegratedScenarioTest` cases cover:

1. **End-to-end success and conservation**, through both parties' actual withdrawals.
2. **Randomness and confirmations are not payout authority:** an attacker-signed consumer allocation fails; provider gets zero from a merely active committee. If the epoch remains unresolved through service end, the pending fee stays locked.
3. **Missing coordinator callback:** pool expires, funded setup cancels, consumer gets all uncommitted escrow, monitor tickets become reclaimable. There is no invented VRF result or service admission.
4. **Late callback:** storing a word after the pool's deadline cannot revive an aborted assignment or prevent the legitimate consumer refund.
5. **Direct fake callback:** EOA caller cannot impersonate the designated coordinator or activate the funded lease.
6. **Missing monitor confirmation:** standby replacement succeeds and the controller activates only after the reserve confirms. The objective no-show ticket deposit accrues to the consumer.
7. **Exposure limit:** a still-unresolved epoch blocks a second admission even after VRF/monitor selection succeeds.

Existing WP-09, WP-10 and WP-11 Foundry test suites are present unchanged on this branch; their code is integrated, not reimplemented in the new test harness.

## CI verification and limits

Combined branch research commit `07c29e9` passed GitHub Actions run:
https://github.com/AkrAyoub/sse-research/actions/runs/43188072420

- **Foundry: 124/124**, 0 failed, 0 skipped; 7 new integrated cases.
- **Python Ubuntu: 337/337**, 0 failed, 0 skipped.
- **Python Windows: 337/337**, 0 failed, 0 skipped.

Because independent WP-08C PR #8 is not merged, its additional 31 chain-authority tests are **not** present in this branch. The validation is an on-chain simulation, **not** an RPC-finalized proof, multi-process WAN probe, economic security audit, or production randomness demonstration.

### Remaining security gates

- Replace `WP12InsecureLocalCoordinator` with a **verified real Chainlink VRF v2.5 coordinator on a supported test network**, configured funded subscription, authenticated coordinator code/address and genuine callback. Measure latency/cost/failures; do not loosen seed-deadline protection to make tests pass.
- Ensure assignment-size economics, arbitrary Sybil wallet concentration, VRF operator censorship and opt-in timing are experimentally addressed.
- Integrate raw off-chain WP-08B signed HTTP observations with an **independent chain-authority adapter for V2**; WP-08C currently only knows SSE V1 fixed-four lease structs.
- Define physical delivery qualification and a time model with explicit challenge/consumer receipt assumptions; signed monitor success alone must not release escrow.
- Resolve indefinite pending escrow fairly, via bilaterally approved rules and/or independently justified physical evidence. The existing V2 bilateral-only controller prioritizes agreement safety over dispute liveness.
- Run external independent hosts, more realistic service/agent credentials, malicious clock/RPC/monitor and network partition experiments.
- Prove conservation under arbitrary multi-lease reentrancy/interleavings; audit contracts prior to funded adversarial deployment.

## Dependency and merge strategy

At this checkpoint, the PRs are **unmerged drafts**:
- #9 WP-09 scalable committee, base `main`;
- #10 WP-10 funded controller, base #9;
- #11 WP-11 VRF coordinator adapter, base #9;
- #12 WP-12 integration, base #10; contains **byte-for-byte copied** WP-11 Solidity adapter and Foundry tests to exercise all three in one cumulative branch.

Review and merge #9 first. Then retarget #10 to `main` and merge after CI/review. Retarget/merge #11 to `main` after #9, reconciling progress changes. Once both are merged, retarget #12 to `main`: the identical WP-11 adapter/test paths should no longer appear as changes, leaving the new integration tests, decisions and phase-tracker diff for review. Resolve conflicts rather than force-pushing a new history onto already merged PRs.

No V1 monetary code is modified and none of these PRs should be merged solely because a mocked coordinator produced a random word.

## Local reproduction

```bash
git fetch origin
git switch --track origin/research/r2-r3-wp12-local-v2-integration
forge test --match-contract SSEV2IntegratedScenarioTest -vv
forge test -vv
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -q
```

Targets on this cumulative branch: 7 integrated cases; 124 total Foundry; 337 Python. Do not substitute the counts of another draft branch.
