# Security audit — 2026-11-27 (static, partial)

Scope reviewed this session: new V4 contracts and V4 Python encoders in full; other areas only by inventory.

| ID | Area | Finding | Status |
|---|---|---|---|
| SEC-01 | V4 contracts | No admin keys; module wiring immutable and verified | Statically reviewed |
| SEC-02 | V4 contracts | Pull payments with guards in market, registry, ledger | Statically reviewed |
| SEC-03 | V4 contracts | Replay: request hashes unique per lease (accounting), ack/response bound to lease/epoch/request + EIP-712 domain incl. chainId/contract; residual nonce | Statically reviewed |
| SEC-04 | V4 contracts | Duplicate payments: monitorBudgetTransferred flag, releaseAll once, accounts.close once, Phase gating | Statically reviewed |
| SEC-05 | V4 Board | Free unbounded bids (spam) — no on-chain iteration; UI must paginate and filter | Accepted risk, documented |
| SEC-06 | Execution | Bids never authorize work; provider agents must wait for finalized EpochStarted | Contract enforced; agent side Not implemented for V4 |
| SEC-07 | Secrets | No secrets added; scan of tree/history for secrets is a deferred owner task (DRV-SEC-01) since tooling cannot be run | Awaiting runtime validation |
| SEC-08 | Uploaded code | Arbitrary user code must stay disabled until microVM-grade isolation exists; Dockerfile.sse-compute unchanged | Not implemented |
| SEC-09 | Public dashboard | Must remain read-only; no change this session | Unchanged |
| SEC-10 | Sampling | Proposer bias / withholding of entropy block; Sybil via many bonded addresses | Documented limitation |
No production-security claim is made from static review.
