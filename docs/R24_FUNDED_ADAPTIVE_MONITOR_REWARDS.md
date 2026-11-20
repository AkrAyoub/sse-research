# R24 — Actually funded V2 monitoring incentives and financial invariants

**Status 2026-11-20:** GitHub source-only R24 on draft PR #35; **NOT yet compiled or run on VM4706**. The previous immutable source checkpoint `5fe0cc6d671977939243c1bffd1607aa22a50dda` really did pass **21/21** focused V2 and **186/186** complete Solidity EVM tests, and its **8,701-byte** V2 deployed runtime is observed. This new code requires a fresh `forge test` / `forge build --sizes` result. Do not promote it to live/independent validation without actual chain31340 transactions.

## Why this change is necessary

Previously, `SSEAdaptiveVoteLedger.freezeCommittee` accepted `p.monitorBudget` as an arbitrary calldata amount to calculate a committee, while **no native TEST ETH was sent to the ledger**. This could falsely imply monitors' report rewards were escrowed. The R24 change enforces an actual payable deposit and explicit pull-payment accounting, **not fake ledger balances**. It concerns **monitor reporting incentives only**; it does **not** resolve service-performance funds and cannot assert world soundness.

## Exact on-chain rules

1. `freezeCommittee(FreezeTerms, selectedSeats)` is `payable` and `onlySettlement`; require `msg.value == p.monitorBudget`. Calculate per-task `k,q` using the already-tested frozen adaptive policy; reject budget too small, bogus eligible count, duplicate seat, prohibited consumer/provider self-monitor, or **overfunding** when `p.monitorBudget != k*payableEpochs*perMonitorEpochReward`. All effects revert atomically on failure. Source context is the chain's worthless native TEST ETH (not mainnet).
2. Freeze the **actual** deposit as per-lease `unspentReportBudget`, with total reserve and credited-balance accounting across leases. No role is entitled to funds merely for being selected or confirming. For every unique, eligible, confirmed monitor who submits a valid EIP-712 signed or directly signed-in-call outcome/evidence commitment within the epoch: reserve decreases by the report reward, `withdrawable[monitor]` increases. Dissenting monitors receive the same guaranteed per-report reward as majority monitors; there is no automatic reward to an unresponsive member. Every seat can report at most once per epoch, and epochs cannot exceed the funded `payableEpochs`.
3. A nonconfirming committee may be permissionlessly expired **only after its precommitted deadline**. Unspent reporting incentives become a **consumer-specific claimable credit**, independent of the caller; no direct external ETH transfer occurs during expiration. Duplicate expiration or attempted reroll under the same lease identifier fails closed.
4. `closeReporting` is callable **only from the immutable settlement address** (which must be the future audited settlement contract, never a coordinator EOA in public release). It can finalize/refund unused monitor incentive reserve only if every previously opened epoch has already been sealed. It cannot silently settle open reports or confiscate earned credits. On closing, future epochs are refused.
5. `withdraw` uses a non-reentrant pull payment to **`msg.sender` only**: sets claimable balance to zero **before** external transfer, bounds all total counters, checks ETH transfer result and prevents second claim. An attempted malicious fallback reentry is tested with an actual EVM contract adversary.
6. Emitted `SeatSelected`, `ReportRewardEarned`, `ReportingClosed` and `Withdrawal` events support verifiable off-chain UI and reporting; logs do not confer role authority. No Docker socket, private key, arbitrary host command, protocol parameter override or centralized admin is introduced.

**Fund conservation invariant (ignoring externally forced Ether):**

```text
ledger ETH balance
   == totalUnspentReserves + totalWithdrawableCredits

on lease registration:  +funding to balance and reserves
on valid monitor vote:  reserves -= reward, credited += reward
on expiry/close:        reserves -= refund, credited += refund
on recipient withdraw:  balance -= amount, credited -= amount
```

No 4-monitor cap is introduced: committees continue to have task-specific `k,q`, while the network's registration and role membership must remain adaptive/open. Gas for dynamic `k` and actual P2P incentives still require honest benchmarks.

## New adversarial source-only Foundry tests

`foundry/test/SSEAdaptiveVoteLedger.t.sol` now contains **31 tests** (the previous 21 real VM-passed tests plus **10 new unexecuted tests**). Added cases include actual transaction ETH deposit requirement, rejecting overpaid/underpaid committees, exact reserve/credit conservation across two leases, payout for valid dissent, repeat/outsider withdrawal refusal, guard against a contract fallback reentering `withdraw`, conditional consumer refund after no-show, permissioned closure only after opened epochs sealed, no more epochs than funded, and no claim by a monitor that never submitted a report.

The tests use `vm.deal`, `vm.prank`, EVM fixtures and synthetic evidence; successful local Foundry checks prove **Solidity state behavior**, **not the existence of real deposited TEST ETH or physical monitor work on the future network**. Before declaring success, run VM4706 focused `forge test --match-contract SSEAdaptiveVoteLedgerTest -vv`, full `forge test`, and `forge build --sizes`, all at the exact committed SHA.

## Blocking next integration and threats

- V2 service escrow accounting for provider delivery and SSE contractual histories `H(E)`, lower and upper bounds `L(E),U(E)`, exposure budgets, refunds and joint signatures is not yet connected to ledger. Do NOT infer true real-world delivery from quorum count or payment for reports: the four `WorldSoundnessAdversarial` counterexamples from V1 remain genuinely unresolved.
- Fair, cryptographically justified **permissionless** election is not provided by `freezeCommittee`. The immutable `settlement` writer must later independently verify candidate membership, bonded registration, real unpredictable unbiased sortition, snapshot/selection validity, actual funding and transaction gas. It must NOT be controlled by a node operator EOA or raw dashboard action. Cheap TEST ETH addresses cannot prove independently administered monitors.
- No automatic selected-seat replacement or bond slashing; the no-show policy expires without reroll, and *service escrow* resolution remains a future settlement responsibility.
- New network chain31340, real Besu+Lighthouse EL/CL genesis, operator-held BLS validator keys, native public P2P, VM↔laptop and measured physical workload SLAs are all **NOT yet deployed**. Preserve the user's finite VM resources and just one external non-VM laptop; do not fabricate operators.
- All code changes in draft PR #35; no GitHub Actions, no main merge or VM source edits; never create or log private keys without owner permission.

**Release classification:** real code for financial accounting **source-only and unverified until VM test**; legacy fixed `SSESettlement` / `OpenMonitorCommittee` remains a release blocker under issue #38.
