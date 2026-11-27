# Design decisions (append-only)
- D-01 (2026-11-27) Split V4 into Board/Registry/Standby/Ledger/Market modules wired by precomputed CREATE addresses, no admin.
  Why: EIP-170 headroom (V3 runtime 23753 B) and separation of funds. Alt: single market (rejected: size), factory (more initcode).
- D-02 Sample at draw time from an append-only roster with population cut frozen at award; reserve only n+s seats.
  Why: avoids R411 lock-all griefing, gives global sampling. Alt: Merkle snapshot of eligible set (needs off-chain builder, more
  trust); rotating window (not global).
- D-03 Bounded attempts (8/seat, ≤512) with fail-closed full refund. Why: bounded gas; never weakens n/b.
- D-04 Consumer fixes n, s, b in the request; quorum q = n − ⌊(n−1)/3⌋ (n ≥ 3b+1 ⇒ 2q−n > b, q ≤ n−b).
- D-05 Unpromoted standbys unpaid for now (owner economics decision pending); listed as A-10.
- D-06 `responseAdmitsReceipt` is an explicit bilateral term, default false (V3 semantics) — no retroactive change.
- D-07 Qualified negative evidence: keep conditional quorum; proposed future format = provider-signed response whose output
  digest differs from a deterministic reference recomputation committed in the policy (only for deterministic workloads).
- D-08 Cancel before provider acceptance: consumer any time, anyone after acceptDeadline; no penalty either side (no work done).
- D-09 (pass 3) Keeper incentive without a contract change: consumer and provider agents "self-keep" (draw, advance,
  activate, finalize, close evidence) ONLY their own leases, zero-value, within owner gas caps (`selfKeep`, installer default
  true, absent = false). Why: each party is paid by its own lease progressing; avoids a bounty that would enlarge the
  near-EIP-170 market and change consumer cost. A third-party keeper role remains optional and unpaid.
- D-10 (pass 3) Provider learns the consumer's Terms by decoding the finalized `awardAndFund` calldata, accepted only when
  the recomputed termsHash equals the on-chain value and the tx sender is the lease consumer. Contract-wallet consumers
  (calldata not direct) must hand Terms to the provider out of band (policy leaseTerms). No new event field (size).
- D-11 (pass 3) Consumer outputs: delivered off-chain by the provider (`/v1/output`, consumer EIP-191 authorization,
  ≤10 min), fetched by the owner-local console only from the URL whose keccak equals the bid's endpointHash, and verified
  against the finalized responseHash. Public console verifies pasted outputs only (no server-side fetch → no SSRF surface).

## Economics proposals awaiting the owner (NOT implemented; recorded so the decision is explicit)
P-1 Standby retainer (A-10/SC-09). **OWNER DECISION 2026-11-27: REJECTED — no standby retainer; unpromoted standbys stay unpaid (D-05 final).** Former option A: consumer pre-funds `standbys × perReportReward` once at
award; each unpromoted standby that stayed reserved until activation may withdraw one report reward at lease close.
Cost to consumer is bounded and visible in the planner; contract change ≈ one mapping + one loop over ≤60 standbys in
`activateCommittee` (size risk: market is the largest module; would likely need moving retainer accounting into
SSEStandbyCommittee). Option B: no retainer; rely on monitors valuing selection probability (status quo).
P-2 Keeper bounty (SC-10). Option A (status quo + D-09): self-keeping. Option B: fixed per-transition bounty from a
consumer-funded keeper pool, paid to msg.sender of draw/activate/finalize/closeEvidence; needs griefing analysis
(front-running is harmless, but the pool must be bounded and refundable). Recommended: A until E9/E10 show stalls.
P-3 Misconduct penalties (SC-11). Only provably attributable faults are eligible: (i) a monitor signing two different
outcomes for one epoch (equivocation, verifiable from two EIP-712 signatures), (ii) a provider signing two different
responseHash values for one epoch. Penalty = forfeit bond to the harmed party. Not implemented: needs a slashing path in
the registry and new audit; would change monitor risk and should be an explicit owner decision.
- D-12 (2026-11-27, owner) No standby retainer (P-1 rejected). handoff/references/Report2.pdf and Report3.pdf stay untracked; never commit them.
