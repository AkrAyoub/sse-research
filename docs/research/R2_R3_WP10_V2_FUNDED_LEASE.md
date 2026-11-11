# WP-10 — Funded V2 lease/controller, committee gating and bilateral allocation

## The concrete gap

WP-09's V2 monitoring contract provides opt-in selection, configurable K/Q, reserves, no-show replacement, ticket deposits, and bounded terminal recovery, but it is **not connected to a funded service lease**. V1 `SSESettlement` remains a separate 4-monitor path and must not be silently repointed to V2.

This increment adds `contracts/SSELeaseControllerV2.sol` as a **separate experimental controller** that owns prefunded lease escrow and is authorized as the V2 pool's controller. It deliberately makes **no physical delivery decision** from monitoring votes. The only payout for an admitted epoch requires a jointly signed, exact consumer/provider allocation.

## Integrated transaction lifecycle

```text
Consumer: createLease{value = epochFee * maxEpochs}
    |
    +-- Nonzero SLA, resource, endpoint commitments + exact consumer/provider binding
    +-- requestAssignment in V2 pool (atomic with funding)
    |
  OFFERED --provider accepts during enrollment--> ACCEPTED
    |                                                |
    +-- acceptance deadline/assignment abort -------+----> CANCELLED (full unused refund)
                                                     |
                                  Pool: opt-in roster, verified-seed interface,
                                        batched selection, on-chain confirmations
                                                     |
                                                     v
                                              Pool: ACTIVE
                                                     |
                              anyone activates V2 controller lease
                                                     v
                                                   LIVE
                                                     |
                         consumer admits unique epoch request (bounded exposure,
                         remaining escrow, max epochs and pool service deadline)
                                                     |
                         [fee becomes PENDING / unresolved]
                                                     |
                        two EIP-712 signatures on exact epoch allocation
                             (providerShare + consumerShare = fee)
                                                     |
                              provider/consumer withdrawable credits
                                                     |
                                    pool's fixed service deadline
                                                     |
                                anyone calls endAdmissions()
                             unused escrow -> consumer credit
                             unresolved admitted escrow remains pending
                                                     |
                                when ALL epochs allocated:
                                  anyone calls finishLease()
                                                     v
                                                   CLOSED
```

**Strict limitation:** An admitted epoch whose parties cannot agree is **not resolved**, even after the service deadline. It retains its entire fee as pending escrow. This prototype does not provide full financial liveness, arbitration, an automatic bound-driven payout, or a court/DAO fallback. Such a fallback must be justified by R1/P1 physical evidence assumptions and a versioned dispute policy.

## What the contract actually enforces

- **Prefunding:** exact deposit `epochFee * maxEpochs`; `maxEpochs` capped at 64; nonzero SLA/resource/endpoint hashes. Funding plus V2 pool assignment occurs in one atomic transaction.
- **Actor binding:** consumer is `msg.sender`; requested V2 pool terms must name the same consumer and provider. Only provider may accept; acceptance must precede a stated deadline and occur during V2 pool enrollment.
- **Committee gating:** `activateLease` only succeeds when V2 pool status is `Active`. This means every currently seated monitor has confirmed on chain under WP-09 rules. It **does not** mean those identities are independent, truthful or physically capable.
- **Epoch admission:** only consumer may admit a nonzero unique request. The fee is transferred from `uncommitted` to `pending`. Admission is limited by escrow, `maxEpochs`, `exposureBudget`, and whether the request's contractual epoch window fits within the pool's absolute `serviceDeadline`.
- **Bilateral money movement:** `EpochAllocation(leaseId,epochId,requestHash,providerShare,consumerShare,nonce,expiry)` is EIP-712 signed by both consumer and provider, for `SSELeaseControllerV2` domain version `2`. Either party may use a relayer. The allocation must add up to exactly one admitted fee, can happen once, increments the per-epoch nonce, and rejects signer or field substitution.
- **Setup failure:** before any epoch can be admitted, failed setup or expired *unaccepted* offer can return the full prefund to the consumer. An accepted offer only cancels on pool abortion/release or the pool's fixed lifetime, not merely because the offer acceptance deadline has elapsed.
- **Time-bounded unused capital:** after the pool's service deadline, anyone can stop new admission. **Only never-admitted** funds are returned unilaterally. The entire admitted but unallocated amount is held as pending.
- **Withdrawal:** user-specific pull credits with zero-before-external-transfer and a withdrawal reentrancy guard. Neither monitor votes nor an aborted pool alone grant the provider any entitlement.
- **No active V1 modification:** existing `SSESettlement`, `OpenMonitorCommittee`, WP-08A/B signing code and WP-08C chain-authority research stay unmodified.

## Conservation and limits

For each prefunded lease with principal `V = epochFee * maxEpochs`, the internal accounting tracks:
- `U`: uncommitted escrow, not yet admitted;
- `X`: admitted, unresolved pending escrow;
- `P`: cumulative provider credited;
- `C`: cumulative consumer credited from resolved epochs;
- `R`: cumulative unused principal refunded.

The intended invariant is

```text
V = U + X + P + C + R
```

The cumulative credits `P,C,R` remain in the equation even after a user withdraws. A withdrawal moves credit out of the controller; it does not undo that entitlement. Transactionally held ether therefore differs from the cumulative accounting sum.

This is **not the final SSE bounds algorithm**. Under raw authenticated observations alone, WP-07 generally cannot exclude a physically possible N/F/S state. The safe lower bound for automatic provider and consumer payout may be zero. Here bilateral signatures supply consent, not an independent proof of performance.

## Security and design questions deliberately open

1. **Unresolved escrow liveness:** if either party refuses a settlement signature, the admitted fee can remain locked indefinitely. The first sound service-specific physical certificate, independent dispute resolution, or opt-in finite arbitration needs an explicit threat model and rights proof before an automatic timeout rule is acceptable.
2. **VRF:** WP-09's selection proof verifier is only an interface; Foundry uses a mock, **not a true unbiased VRF**. Seed generation/verification, availability, pre-seed confidentiality, collusion and censorship remain separate.
3. **Pool lifetime:** V2 `serviceDeadline` is fixed at assignment creation, not calculated from actual activation. The controller prevents admissions whose windows extend beyond it. Pool bonds cover opt-in and on-chain confirmation, **not unresolved escrow claims**. Anyone can expire the pool at the configured lifetime even if admitted fees remain under dispute.
4. **Economic fairness:** the consumer can stop before enrollment is completed if the provider never accepts. Monitors may nevertheless have opted into an assignment and remain locked until the pool expires. Enrollment fees, penalties, setup cancellation and assigned-monitor incentives need analysis.
5. **Signer model:** this proof-of-concept uses ECDSA EOA signatures, not general ERC-1271 smart-contract wallets. There is no arbitrary admin who can force a payout.
6. **Future V2 policy and observability:** SLA commitment is stored but not executable; the controller cannot yet prove actual consumer delivery, provider uptime, time bounds or quorum soundness. Need independent WAN hosts, reproducible fault injection and sound evidence qualifiers.
7. **Gas/security audit:** Foundry unit/fuzz tests are not exhaustive; add multi-lease invariant fuzzing, failure-injection, contract-signature edge tests, economic games and independent audit before live capital.

## Verified increment

Dependent PR #10 is based on WP-09 branch, which must merge first. Its initial hosted CI found two test-harness errors involving the use of `vm.expectRevert` before `vm.sign` helpers. The fixes move signature construction before the expectation and **do not change payout behavior**.

After correction, Solidity CI run https://github.com/AkrAyoub/sse-research/actions/runs/43115381955 reported:
- **New `SSELeaseControllerV2Test`: 21/21 passed**, including fuzz-conservation for 256 runs;
- **Full Foundry: 99/99 passed**, 78 previous WP-09 tests + 21 new, no skips or failures;
- **Ubuntu Python: 337/337** (WP-08C's separate PR #8 is not yet merged).

Windows CI result is recorded in the PR once complete. This evidence validates a **standalone funded V2 controller under stated conditions**, not a production viable SLA-oracle settlement.

## Acceptance sequence and immediately following work

1. Complete both-platform Python and full Foundry CI; review source for domain replay, conserved escrow, non-reentrant withdrawals, cancellation and allocation safety.
2. Merge independent WP-09 only after review. Retarget this dependent PR #10 to `main`, refresh CI, and merge only after review. WP-08C is separate and must be tested/merged independently.
3. WP-11: implement a genuinely verifiable randomness integration with proof verification, non-grindable request domain, timeout/re-request and independent deployment checks. Document concrete oracle and threat model.
4. WP-12: world-sound HTTP delivery certificate or explicitly limited arbitration scheme; do not equate authenticated provider/monitor statements with the physical delivery event.
5. R5/R6/R9: run provider/consumer/monitor processes on independent machines and evaluate reliability, reorg/finality and actual timestamp uncertainty.
