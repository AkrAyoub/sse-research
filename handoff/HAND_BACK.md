# HAND_BACK — session S1, 2026-11-27 (source-code-only)

**Honest summary:** nothing in this session was compiled, executed, tested, installed or deployed. All new work is
source + unexecuted tests + static review. No VM, chain, wallet or key was touched. Branch `handoff/claude-code-2026-11-27`,
local commits only (not pushed).

## Commits (on top of 394705a)
| Commit | Content |
|---|---|
| 94b7fac | Governing source-only instruction adopted (CLAUDE.md, AGENTS.md, handoff/GOVERNING_INSTRUCTION.md, annotations) |
| 5d5867b | Integrated V4 candidate contracts, deploy script, Foundry tests |
| 6d8bcfe | V4 committee planner + terms/typed-data encoders + Python tests |
| (this)  | Audits, planning, logs, HAND_BACK, WORK_LOG |

## By status
- **Historically live-verified (unchanged):** native chain31340 PoS; V2/V3 deployments; V3 experiments E1–E6, E8; V3 read-only
  dashboard + tunnel; R424 reward collector (see STATE_AND_EVIDENCE.md).
- **Historically execution-tested:** SSEStandbyCommittee (R429, before the new `cancel()`), ordered sampling (R427), V3 suite (R342e).
- **Newly implemented + statically reviewed + tests written (not executed), awaiting compilation:**
  SSEAdaptiveMarketV4, SSEServiceBoardV4, SSEMonitorRegistryV4, SSEStandbyCommittee.cancel, DeploySSEV4Candidate31340,
  tools/sse_v4_committee_planner.py, tools/sse_v4_terms.py; 33 Solidity tests, 11 Python tests.
- **Awaiting deployment:** all V4 contracts (new version; V3 stays at its addresses).
- **Not implemented:** V4 agents, V4 UI, explorer proofs, unified installer, keeper bounties, standby retainer, misconduct
  penalties, stronger randomness for V4, E7/E9/E10.

## What V4 now does (source)
Consumer posts a request with explicit n seats, s standbys, fault bound b (n ≥ 3b+1), fixed or provider-proposed epochs;
providers bid (free, withdrawable, expiring); consumer awards any bid any time (no minimum bids) and funds service + exact
report budget; committee is drawn from a global append-only monitor roster with bounded unbiased rejection sampling at a future
blockhash, reserving capacity only for the n+s drawn; standby state machine handles confirmation and fixed-order promotion;
the confirmed committee is frozen in the ledger and the report budget transferred once; provider must accept the exact termsHash;
only an admitted epoch authorizes execution; V3 SSE accounting semantics preserved; every pre-service failure refunds in full and
releases reservations. Details: handoff/audits/SMART_CONTRACT_AUDIT.md.

## Owner next steps
Run handoff/planning/DEFERRED_RUNTIME_VALIDATION.md Stages 0–3 (read-only/compile/tests), record outputs in
handoff/logs/BUGS_AND_FIXES_LOG.md, then start a new source session to fix failures. Decide: standby retainer economics (D-05),
whether to commit Report2/Report3 PDFs, and provide the Milestone 4 rubric if it exists.

## Risks
Unknown bytecode size/stack depth (SC-13/14); proposer-biasable entropy; Sybil via bonded addresses; valueless TEST ETH.
