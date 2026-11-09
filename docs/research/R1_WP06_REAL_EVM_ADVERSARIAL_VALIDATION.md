# R1/R2 WP-06 — Real EVM counterexample validation (2026-11-09)

**Status: FOUNDry HOSTED CI PASSED on research PR #4. 17 new tests, 52/52 total Foundry, 226/226 Python on Ubuntu AND Windows.** The new Solidity tests execute production contract bytecode in Foundry's local EVM. **No production contract was changed.**

- Pull request: https://github.com/AkrAyoub/sse-research/pull/4
- Passing CI: https://github.com/AkrAyoub/sse-research/actions/runs/42714056087
- Tested commit: `c5068989709e6d60f9c5482c443ed78058f6dd0d`
- Source: `foundry/test/WorldSoundnessAdversarial.t.sol`
- Foundry compiler: Solidity 0.8.24 as pinned by `foundry.toml`
- Prior baseline: 35 passing Foundry; now 17 additional tests => 52 total
- Existing Python suite: 226/226 passing on both hosted Ubuntu and Windows

## Critical interpretation boundary

The test contract performs *real EVM* calls against `SSESettlement` and `OpenMonitorCommittee`, and produces EIP-712 signatures with `vm.sign`. What is **not** real is any external cloud fulfillment or physical consumer receipt. The labels **stipulated true S/F** are assumed by the adversarial scenario designer; they are **not** attested to, physically measured, or determined by Ethereum. Thus the experiments establish the **reachable on-chain payout under conditionally conflicting external histories**, not an end-to-end practical exploit or unconditional breach.

## Setup: lifecycle and why every step matters

1. `vm.warp(10000)`: fixes EVM block time for reproducible deadline calculations. It is not a trusted off-chain clock.
2. Deploy `OpenMonitorCommittee`, then `SSESettlement`, and bind the contracts. The test contract is the intentionally trusted randomness source in the fixture.
3. Derive addresses from five different monitoring private keys; fund and bond them for 1 ether apiece. Committee membership is not faked using a direct storage override.
4. Consumer creates a 25-wei, one-epoch lease with a 5-wei reservation entitlement, exposure budget 25 and time periods 10/5/8.
5. Provider accepts, test-only randomness selects four candidates, all four confirm assignment.
6. Consumer admits an epoch, locking 25 wei and computing `responseDeadline=10010`, `monitoringClose=10015`, `evidenceClose=10023`.
7. Tests construct typed `ProviderAck`, `ProviderResponse`, and `MonitorVote` struct hashes exactly matching the contract; sign `keccak256(0x1901 || settlement.domainSeparator() || structHash)` with `vm.sign`. Each signed vote binds `leaseId, epochId, requestHash, outcome, responseHash, evidenceHash`; the sender calling `submitMonitorVote` need not be the signer.
8. Contract verifies recovered signer and selection/confirmation, deadlines, evidence commitment, one-vote-per-monitor, and provider response authentication for success votes.
9. `sealMonitoring` at `monitoringClose+1` decides 3-of-4 outcome. `settleEpoch` applies on-chain N/F/S masks and updates actual stored credited amounts.
10. Each payout assertion also checks `providerCredited + consumerCredited + unresolvedExposure = 25`, withdrawable balance equality and `lease.currentExposure`.

## Four positive EVM demonstrations and their interpretation

| Test | Submitted qualified chain evidence | Actual EVM credit | Hypothetical physical-world contradiction |
|---|---|---|---|
| CE-01 | Three signed selected-monitor Failure reports no ACK | Consumer 20, unresolved 5 | If consumer actually got correct result on time (true S), consumer entitlement is 0 |
| CE-02 | Real provider-signed ACK + three signed selected Failure reports | Consumer 25, unresolved 0 | If physical S, overcredit relative to physical entitlement is 25 |
| CE-03 | Authenticated provider response and three signed selected Success votes | Provider 25, unresolved 0 | If service contract requires consumer delivery but only response signing/transmission occurred (true F), provider entitlement is 0 |
| CE-04 | Provider response first submitted to chain at `responseDeadline+1` (within grace) followed by three signed Success reports | Provider 25, unresolved 0 | Only if physical completion was late and SLA deadline governs physical completion; *late chain inclusion alone does not prove lateness* |

These tests establish the contract's **behavior when it is fed valid but physically non-conclusive evidence**, not how often that evidence arises in practice. Evidence hashes commit to bytes; the contract does not validate the bytes' physical truth. A bounded Byzantine count or quorum intersection is not a substitute for sound observations.

## Defense/control tests (13 additional)

- Failure votes **one second before** `responseDeadline` revert; votes **exactly at** it pass.
- A Success vote before provider-authenticated response reverts.
- An unselected outsider's signed monitor vote reverts.
- Tampering with the signed `evidenceHash` fails membership recovery.
- The same selected monitor cannot vote twice.
- Two failure votes do not form a quorum; funds remain fully unresolved.
- Four distinct monitors cannot supply two simultaneously opposing quorums of three.
- Provider response and monitor failure vote after `monitoringClose` revert.
- An ACK at `evidenceClose` can refine a previous partial refund *incrementally* (20 then +5, never another +20).
- An ACK after `evidenceClose` reverts.
- Incorrect provider signature on `ProviderResponse` reverts.
- Repeated settlement does not double-credit.

## Initial CI failure and precise fix

The first hosted Solidity job **compiled all source successfully**, but Foundry discovered two tests beginning with `testFailure...`. Foundry 1.9 treats the prefix `testFail` as a removed legacy naming convention and refused to execute those two tests. This was a **test discovery failure**, not an evidence counterexample assertion failure.

They were renamed to `test_RevertFailure...` in commit `c506898`. The subsequent GitHub run completed **all 17 new tests**, **all 52 Foundry tests**, **226 Python tests on Ubuntu** and **226 Python tests on Windows**, with zero failures.

## Implications: what can be implemented

- R1: versioned, explicitly conditional policy rules that differentiate provider-authentication, individual monitor-local observation, consumer delivery, and definitive contractual fulfillment.
- R4: typed, session-bound signed observations and a service-specific evidence archive; separate timestamp origin and uncertainty. A signature does not prove the underlying physical event.
- R2: retain partial guaranteed release and bounded exposure, but **do not** classify failure quorums or response signatures as unconditional world exclusions under arbitrary network partitions.
- R7: specify measurable service-specific predicates for HTTP, compute, storage, OCI and API workloads before interpreting evidence.
- P2/P4/R9: combine finite-model trace projections with actual contract traces, run independent VM experiments and identify precisely which *assumptions* are needed for soundness. Do not label this work a formal proof.

## What remains unresolved

ADR-001: epistemic 'no verifiable receipt' versus physical nonreceipt. ADR-002: which monitors can certify which service outcomes under which network assumptions. ADR-004: trusted event timestamps and precision versus blockchain inclusion time. No remote VM, proof of trusted capacity reservation, or distributed physical soundness has been validated.

## Reproduction

```bash
bash scripts/install-contract-deps.sh
forge test --match-contract WorldSoundnessAdversarialTest -vv
forge test -vv
python -m unittest discover -s tests -v
```

Acceptance for this test-only branch requires green hosted CI and peer review; **merging it does not approve a new production payment policy**.
