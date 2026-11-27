# HAND_BACK — session S1, 2026-11-27 (source-code-only) — FINAL (implementation closed by owner request)

**Honest summary:** nothing in this session was compiled, executed, tested, installed or deployed. All new work is
source + unexecuted tests + static review. No VM, chain, wallet or key was touched. Branch `handoff/claude-code-2026-11-27`,
local commits only (not pushed). Process deviation (pass 3, disclosed): the system `python3` interpreter was used three
times purely as a text editor (string replace on tools/sse_v4_agent.py); no project module was imported or run. Later edits
used sed/heredocs only. See logs/BUGS_AND_FIXES_LOG.md.

## Commits (on top of 394705a)
| Commit | Content |
|---|---|
| 94b7fac | Governing source-only instruction adopted (CLAUDE.md, AGENTS.md, GOVERNING_INSTRUCTION.md) |
| 5d5867b | Integrated V4 contracts (Board, Registry, Standby cancel, Ledger wiring, Market), deploy script, Foundry tests |
| 6d8bcfe | Committee planner + termsHash / EIP-712 encoders + Python tests |
| 1ea49d5 | Audits, master checklist, deferred owner-run runbook, logs, HAND_BACK |
| a2fd6ae | V4 agents: ABI layer, finalized read model, durable cursor, journal-before-broadcast, role planners, adapters |
| b70f8b3 | V4 console + explorer (marketplace/role pages, unsigned wallet intents, planner, eth_getProof MPT verifier) |
| e8c1df1 | Application-role installer, hardened systemd user units, manifest template |
| d4fc4e1 | Pass-2 docs; removed unreferenced abandoned R407 login module |
| bb6976e | Provider output service (consumer-signed download, never executes work); console Node/validator page |
| bc21914 | Provider decodes consumer Terms from funding calldata (hash-authenticated); consumer output download/verify page; console CSRF/DNS-rebinding guard |
| c8dced9 | Console native reward summary from the R424 collector (read only) |
| 7d47c4e | Self-keeping of own leases (D-09); economics proposals P-1..P-3 for the owner |
| 3bfc051 | Pass-3 audits/logs/HAND_BACK/WORK_LOG refresh |
| 18351e9 | Gas-parametrized formation tests n∈{7,10}, s∈{2,4} |
| a6eb47a | Provider terms check for contract-wallet consumers; bid pagination and filters |
| 189ad8d | One-entry-point setup orchestrator (plan first, per-step yes) over existing installers |
| 184af44 | Pass-4 docs refresh |
| 7770905 | Structured profile/policy/offer manifests; account balance/nonce/code and finalized history |
| 59f2ba7 | Requirements traceability refresh |
| 5fbc802 | Owner decisions recorded: no standby retainer (D-12); report PDFs stay untracked |
| (this)  | Final checkpoint: HAND_BACK and WORK_LOG closed |

## By status
- **Existing live-verified (unchanged):** native chain31340 PoS; V2/V3 deployments; V3 experiments E1–E6, E8; V3 read-only
  dashboard + tunnel; R424 reward collector (STATE_AND_EVIDENCE.md).
- **Previously execution-tested:** SSEStandbyCommittee (R429, before the new `cancel()`), ordered sampling (R427), V3 suite
  (R342e), R425 collector tests.
- **Newly implemented, statically reviewed, tests written but not executed (awaiting compilation / runtime validation):**
  - Contracts: SSEAdaptiveMarketV4, SSEServiceBoardV4, SSEMonitorRegistryV4, SSEStandbyCommittee.cancel, deploy script;
    39 Foundry tests.
  - Python: planner, encoders, ABI layer, state/cursor/journal, role agents (incl. Terms decoding, self-keeping), signer
    unlock, job runner/prober adapters, provider output service, MPT proof verifier, console (marketplace, request builder,
    lease, provider, monitor, account, explorer, node/validator, rewards, consumer outputs), installer + unit templates;
    43 Python tests (incl. tests/test_sse_setup.py).
- **Awaiting deployment:** all V4 contracts (new version; V3 stays at its addresses).
- **Owner decided (D-12):** no standby retainer; Report2/Report3 PDFs stay untracked.
- **Not implemented / owner decision pending:** on-chain keeper bounty (P-2), misconduct penalties (P-3),
  stronger randomness for V4, arbitrary uploaded code (needs microVM isolation), single-format installer output (the new
  scripts/sse_setup.py orders the existing installers but does not merge them),
  E7/E9/E10.

## What V4 does end to end (source)
Consumer builds a request in the console (uploads → content-addressed commitment, planner shows exact cost and draw
probability), providers bid, consumer awards and funds from their own wallet; anyone (or the parties' self-keeping agents)
draws the committee from the global monitor roster; standbys replace non-confirming seats; provider agent decodes and
verifies the exact Terms and accepts; consumer agent starts epochs within its exposure budget; provider runs only after a
finalized admitted epoch, signs the response, serves the output only to the consumer; monitors probe and vote (abstain when
inconclusive); keepers finalize and close evidence; the consumer downloads the output and the console verifies it against
the finalized on-chain responseHash. Details: audits/SMART_CONTRACT_AUDIT.md, audits/AGENT_AND_RUNTIME_SOURCE_AUDIT.md.

## Owner next steps
1. Run planning/DEFERRED_RUNTIME_VALIDATION.md Stages 0–3 (read-only, compile, tests) and record outputs in
   logs/BUGS_AND_FIXES_LOG.md; then a new source session fixes failures.
2. Decide P-2/P-3 (planning/DESIGN_DECISIONS.md; P-1 rejected, PDFs stay untracked), and provide the Milestone 4
   rubric if it exists.
3. Only after Stage 4 (isolated chain) passes: approve a chain31340 V4 deployment plan (Stage 5).

## Risks
Unknown bytecode size/stack depth (SC-13/14); proposer-biasable entropy; Sybil via bonded addresses; valueless TEST ETH;
hand-written ABI tables must match compiled ABIs (DRV-V4-ABI); console/agents never run in a browser or against a node yet.

## Final state (2026-11-27, session closed by owner: "no more implementation needed now")
- Branch `handoff/claude-code-2026-11-27`, local commits only, never pushed; V3 contracts, evidence and original reports untouched.
- Untracked by owner decision: handoff/references/Report2.pdf, Report3.pdf (never commit).
- Tests written, NOT executed: 43 Python, 39 Foundry. Nothing compiled, run, installed or deployed.
- Open owner decisions: P-2 on-chain keeper bounty (current design: self-keeping, D-09), P-3 equivocation-only slashing.
  P-1 standby retainer: rejected (D-12).
- First owner action: planning/DEFERRED_RUNTIME_VALIDATION.md Stages 0–3; return outputs for a new source session.
