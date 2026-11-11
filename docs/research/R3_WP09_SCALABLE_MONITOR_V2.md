# R3 WP-09 — V2 scalable pool and committee lifecycle

## Why this redesign

V1 is useful for regression testing but not an open long-lived monitor ecosystem. `OpenMonitorCommittee` caps **ever-registered** addresses at 32, scans all enrolled identities to snapshot each new request, fixes the committee at 4/3, relies on an authorized seed supplier, and cannot generally recover after a selected monitor never confirms. Bond release can also depend on the consumer ending the lease.

V2 is **a new, isolated Solidity research contract**. It does **not** replace V1 `SSESettlement`, authorize new escrow releases, or prove that any service was delivered. The goal here is practical monitor participation and *on-chain assignment liveness*, not physical-world evidence sufficiency.

## Architecture and critical choices

```text
Candidate register (registry bond)   ... unbounded distinct identities
          |
Controller opens lease assignment (K, threshold Q, R reserves, deadlines)
          |
Anyone with an active registry bond may join that assignment (ticket bond)
          |  O(1) per join; no whole-registry snapshot
          v
Close enrollment  ---> immutable ordered roster / commitment
          |
Authorized randomness provider + external proof verifier
          |  Proof correctness and unbiasedness are ASSUMPTIONS
          v
Anyone runs processSelection(id, maxSteps <= 16) repeatedly
          |  deterministic Keccak score per enrolled address
          |  retain at most 16 ranked finalists in storage
          v
Finalize K selected committee seats; retain R ranked standbys
          |
Monitors confirm before deadline
          |                 \
          |                  no-show -> timeout -> next standby -> new deadline
          |                                      |
          v                                      v
       ACTIVE                                ABORT (no reserves/time)
          |                                      |
Controller releases OR fixed max lifetime expires  |
          +--------------------+-----------------+
                               v
   Anyone settles each ticket (refund, or no-show confirmation penalty)
                               |
          Registry bond can exit after no tickets + exit delay
```

**Registry scalability:** no lifetime cap or global-list traversal when creating an assignment. Registration and per-assignment participation are O(1) *per participant*. Roster processing is **O(E × min(K+R,16)) total** for E opt-in entrants, distributed over permissionless transactions processing **at most 16 entrants each**. The protocol is not constant-total-gas, and on-chain storage/transaction costs still grow with participation. A large registry of non-participants has no per-assignment scan cost.

**Selection:** each identity opts into an assignment and locks a separate ticket deposit **before a randomness seed is accepted**. The roster is then immutable. Candidate score is `uint256(keccak256(abi.encode(seed,assignmentId,candidate)))`. Keep the lowest scores, breaking ties by address. This makes the ranking deterministic and publicly recomputable for a given seed and opt-in roster; it is only a fair lottery **conditional on** a correct, unbiasable seed source and registration/participation assumptions. It does not sample every registry member automatically. One address = one ticket per assignment, but **one economic operator can control many addresses**; ticket and registry bonds price Sybil admission rather than proving independence.

**Randomness is NOT solved:** `IVerifiedMonitorRandomnessV2.verify(...)` is an external interface. The Foundry mock checks interface correctness but allows arbitrary seeds and is **not a VRF**. A real provider needs proof verification, request-binding, coordinator availability, callback replay behavior, bias/censorship analysis and economic trust boundaries before deployment. Do not call the current V2 selection unconditionally unbiased.

**Configurable committee:** `3 <= K <= 16`, `K/2 < Q <= K`, with `K+R <= 16`. Majority intersection is a minimal structural constraint, **not** a physical truth certificate and **not** by itself a sufficient Byzantine fault/security threshold. The future service-specific quorum/fault model must justify K and Q.

**Liveness:** the enrollment, seed, batched selection, confirmation and service periods each have explicit upper bounds. Any address can expire a stalled assignment. Missing confirmations can be replaced by the next ranked standby in bounded rounds. Missing reserves or expiration aborts instead of pretending the quorum exists. A controller can release an active committee, but **anyone can release it after the configured maximum service lifetime**, so an absent consumer alone cannot lock monitor deposits forever. This maximum MUST be synchronized with V2 escrow lease duration; independent V1 leases cannot rely on this guarantee without integration.

**Bonds:** registry deposit `minimumRegistryBond` and each-assignment `ticketBond` are distinct. Joining locks a ticket; the registry deposit cannot be withdrawn while tickets remain. Anyone can settle a ticket when its lifecycle permits. A selected monitor who does **not submit its on-chain confirmation** before the objective chain deadline loses its ticket deposit to the assignment consumer. This is a contractual on-chain confirmation obligation, **not punishment for failure to deliver or observe an off-chain SLA**, and it still imposes network-availability risk on honest monitors. Other ticket deposits and registry bonds return as credits. `withdraw()` uses a reentrancy guard and zeroes credit before transfer.

### State transitions and invariants

`None -> Enrollment -> WaitingSeed -> Selecting -> Confirming -> Active -> Released`; timeout/shortage can transition to `Aborted`. Confirmation timeouts with standbys stay in `Confirming` with a refreshed bounded deadline. No state should authorize a monetary V1 outcome; V2 only manages committee participation.

Testable invariants include: (1) no duplicate join, (2) consumer/provider not selected, (3) enrolled roster frozen before seed, (4) processing cursor monotone and <= entrants, (5) selected/standby ranking deterministic independently of batch division, (6) each active selected member must confirm, (7) once-paid tickets cannot pay again, (8) every deposit remains either contract-held or credited/withdrawn, and (9) permissionless terminal recovery by a fixed chain-time bound.

### Known limitations before integrating into escrow

- No real VRF/proof verifier and no verified randomness-vs-grinding/censorship result.
- No robust independent identity or Sybil-resistance proof; stake may be insufficient against a wealthy or coordinated operator.
- Per-assignment opt-in changes the sample population; response availability and selective registration require measurements.
- Someone must submit permissionless processing and timeout transactions; permissionless access does not guarantee that someone will do so.
- Standby exhaustion still aborts the assignment rather than always guaranteeing progress.
- SLA-world soundness remains independent: votes are authenticated observations; a large honest committee does not prove physical consumer delivery under arbitrary partitions.
- No V2 settlement adapter, no on-chain V2 lease versioning, no cross-contract service deadline enforcement, no slashing audit/economic calibration. **V1 monetary contracts remain untouched.**
- Bounded score-sortition runs in multiple transactions. The total workload grows with entrant count and gas benchmarking is required.
- Selection limits concern per-assignment K+R, not global registry identities. K, Q and reserves require fault-model proof and economic/safety review.
- Contract is **research-only and unaudited**; no production funds or slashable third-party stakes.

## Verification record and interpretation

PR #9 introduced **24 new Foundry cases**, including rosters with **80 and 96** participant identities, 16-at-a-time processing, deterministic top-score ranking, reserve replacement across rounds, authorization checks, ticket conservation/refund and permissionless recovery.

Initial CI: 23/24 new Foundry tests passed; one test harness incorrectly called a read-only getter after `vm.expectRevert`. It was fixed without changing the contract or the intended assertion. Corrected implementation CI:
- GitHub Actions run https://github.com/AkrAyoub/sse-research/actions/runs/43110731766
- **Foundry: 76/76 named tests passed**, 24 new and 52 existing, 0 failed, 0 skipped
- **Python Ubuntu: 337/337 tests passed**, no failures or skips
- **Python Windows: 337/337 tests passed**, no failures or skips

The R4 WP-08C Python tests (31) remain in a **separate open draft PR #8** and are not part of `main` or this R3 branch; do not mistakenly expect 368 tests here until PR #8 is independently merged.

### Research proof/experiment tasks

1. Prove ticket escrow conservation over all state transitions, including replaced and unconfirmed members and concurrent assignments; test adversarial reentrant withdrawal.
2. Model replacement liveness conditioned on third-party executors and bounded chain transaction inclusion.
3. Integrate an actual publicly verifiable randomness oracle with confirmed proof verification and analyze seed availability/bias.
4. Simulate and measure gas versus pool size N, per-assignment opt-in E, committee K and reserve R, alongside source-operator stake concentration and adversarial nonparticipation.
5. Integrate with separately designed V2 escrow policy while preserving the existing world-soundness constraints from WP-02 through WP-08.
6. Demonstrate deployment under independent hosts and real partitions.

**Acceptance level:** soundly compiled and adversarial-test-validated *standalone research V2 participation prototype*, NOT verified unbiased production committee selection or physical SLA enforcement.
