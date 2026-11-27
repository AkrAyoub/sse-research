# Agent and runtime source audit — 2026-11-27 (inventory level)

- V3 agents are a chain of R-numbered single-purpose tools (r349 sample session, r351 transaction journal, r352 provider
  signed reply, r353 confirmation/vote plan, r355 monitor vote, r367 compute wire, r370 monitor session, r371 consumer
  response, r375 residual, r377 epoch session, r379 ack, r380 interrupt). They target V3 ABIs and VM-specific paths.
- r351 transaction journal is the right foundation for idempotent, non-blind-retry sending; reuse for V4.
- No V4 event decoder, cursor, or role agent exists. Added this session: tools/sse_v4_terms.py (termsHash, EIP-712 digests)
  and tools/sse_v4_committee_planner.py (pure planning), both unexecuted.
- Required V4 agent design (Not implemented): durable cursor over finalized blocks; per-(lease,epoch) task IDs; provider starts
  execution only on finalized EpochStarted for an accepted lease; monitor confirms on Standby, re-checks phase after reorg;
  keeper calls drawCommittee/advance/activateCommittee/finalizeEpoch; all sends through r351-style journal with owner spending cap.

## Pass 2 update (2026-11-27)
V4 agent now exists in source (a2fd6ae): see tools/sse_v4_agent.py docstring for the safety model. Static review notes:
- Task ids include a round key so repeated identical calls (standby advance) are not deduplicated away.
- Journal statuses SIGNED/UNKNOWN/BROADCAST_ERROR/NONCANONICAL block further sends from the wallet; CANONICAL_* and BROADCAST
  do not (node pending nonce sequences them). Absent receipt is never permission to resend.
- Provider jobs are persisted QUEUED→RUNNING→DONE before/after execution; a crash during RUNNING leaves the job RUNNING and it
  is NOT re-executed automatically (owner inspects) — conservative choice, may lose an epoch rather than double-execute.
- Monitor probe records are written once per (lease, epoch); a transient network error yields an abstention, not a retry.
- Open: no reorg handling is needed below finalized, but the agent halts (exit 3) if its cursor block stops being canonical.
- Open: provider acceptance requires the consumer's Terms locally (policy.provider.leaseTerms); decoding them from the
  awardAndFund calldata automatically is NOT implemented.
