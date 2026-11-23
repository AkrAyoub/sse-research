# R221 — V2 deadline-hardening review and source-only CI

Reviewed branch `feature/r136-independent-observer-preflight` and PR #41
after R216. No running VM, validator, Docker state, keystore or test ETH
was accessed. No transaction was signed or broadcast.

## Security defects corrected

**R217 — Late signed response accepted as Success.** Previously the
vote ledger's `authenticateResponse` permitted an otherwise valid
provider signature until `monitoringClose`, even when the response
deadline had passed. A provider could thus supply a valid but late
response and have it counted toward Success. The ledger now refuses
authentication once `block.timestamp > responseDeadline`. Failure
votes still require `block.timestamp >= responseDeadline`; the
deadline is inclusive for provider response. Existing valid on-time
response semantics remain.

**R218 — Late provider acceptance.** Previously a provider could
accept a still-assigned lease long after the committee confirmation
deadline, racing the cancellation path and keeping service funds
locked without timely acceptance. Acceptance now rejects
`block.timestamp > confirmationDeadline` or expired committee.
This is a frozen acceptance cutoff, not an assurance that the
provider will actually perform compute. Consumers may still cancel
a never-accepted lease after the deadline.

**R219 — Adversarial regressions.** New tests sign a valid provider
EIP712 digest, advance past the response deadline, assert that
authentication reverts and a Success vote remains impossible; also
assert a provider cannot accept after the frozen confirmation
deadline and that service/report escrow refunds remain available.

**R220 — New GitHub source-only CI.** A dedicated workflow runs
`forge build --sizes`, the V2 Foundry suite, mocked Python
chain-gate and deployment-audit tests, and the full Foundry suite.
It does not connect to real VM RPCs, create wallets, broadcast
transactions or alter the chain. No successful CI result has been
observed in this review; do not treat its presence as proof of
passing tests.

## Scientific and economic caveats still open

1. `SSEAdaptiveMarketV2` is not deployed or verified on the real
   original chain31340. Existing verified finality on VM4707 and
   VM4709 is a separate, older empirical result; do not conflate.
2. Bonded EOAs and a rotating 64-address snapshot do NOT prove
   independent physical operators, uniformly sampled candidates,
   Sybil resistance, or unbiased committee election. Future
   blockhash is proposer-biasable, NOT VRF.
3. A provider-signed response hash and monitor vote hash do NOT
   establish actual CPU/memory work, Docker resource limits or
   physical SLA truth. No real provider/monitor evidence pipeline
   has been integrated with V2 in a live end-to-end trial.
4. Bond lock is a participation constraint, not slashable
   collateral. No objective dispute-proof or slashing rule exists.
   Paying reports does not certify their correctness.
5. If quorum is inconclusive and the parties cannot agree on
   bilateral residual allocation, service funds can remain
   locked indefinitely. This liveness tradeoff is explicit.
6. Source must compile, respect EIP170 runtime size, and pass
   tests/security review before any owner-authorized deployment.
   No claim of audited or production-ready Solidity.

## Return-time verification

Use the **latest** PR #41 HEAD (not R216 SHA), follow
`docs/R210_V2_RETURN_VERIFICATION_RUNBOOK.md`, and run:
`forge build --sizes`,
`forge test --match-contract SSEAdaptiveMarketV2Test -vv`,
`forge test -q`,
and both `tests/test_sse_pos_r201_*` and `tests/test_sse_pos_r206_*`
mock-only unit tests. Check GitHub Actions run outcome independently.
If tests fail, repair through reviewed GitHub commits before touching
any VM runtime or transaction path.

Only after explicit operator approval, provision a separate
application-only TEST-ETH signer privately, deploy to the original
chain31340, verify actual finalized receipt/runtime hashes on
both hosts with R206, then perform independently measured real
provider Docker compute and monitor evidence/SLA experiments.
The legacy fixed-4/3 deployment is NOT the adaptive SSE V2.
