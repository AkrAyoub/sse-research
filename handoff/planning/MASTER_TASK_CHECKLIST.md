# MASTER TASK CHECKLIST — single authoritative status list

Status labels: LV Existing live-verified · ET Previously execution-tested · NI Newly implemented · SR Statically reviewed ·
TW Automated tests written but not executed · AC Awaiting compilation · AR Awaiting runtime validation · AD Awaiting deployment ·
BL Blocked · NO Not implemented. Commits are on branch handoff/claude-code-2026-11-27.

| ID | Task | Files / symbols | Status | Runtime validation | Commit |
|---|---|---|---|---|---|
| G-00 | Adopt source-only governing instruction in CLAUDE.md/AGENTS.md/handoff | CLAUDE.md, AGENTS.md, handoff/GOVERNING_INSTRUCTION.md | NI, SR | — | 94b7fac |
| A-00 | Baseline compile + full test run | whole repo | BL (prohibited this session) → DRV-01 | DRV-01 | — |
| A-01 | V4 integrated market: award+fund, draw, standby formation, activation, epochs, closure, all cancel paths | contracts/SSEAdaptiveMarketV4.sol | NI, SR, TW, AC | DRV-V4-01..04 | 5d5867b |
| A-02 | Public request/bid board with explicit n/s/b, fixed or provider-proposed epochs, early award, bid withdrawal/expiry | contracts/SSEServiceBoardV4.sol | NI, SR, TW, AC | DRV-V4-01 | 5d5867b |
| A-03 | Capacity-backed monitor registry, global unbiased bounded sampling, reservations, exit/top-up | contracts/SSEMonitorRegistryV4.sol | NI, SR, TW, AC | DRV-V4-01, DRV-V4-GAS | 5d5867b |
| A-04 | Standby cancel() for unaccepted leases | contracts/SSEStandbyCommittee.sol `cancel` | NI, SR; rest ET (R429) | DRV-V4-01 (re-run R429 tests) | 5d5867b |
| A-05 | Confirmed-committee ledger integration (R430) | SSEAdaptiveVoteLedgerV4Candidate `freezeConfirmedCommittee` | SR (unchanged code), TW via market tests, AC | DRV-V4-01 | 5d5867b |
| A-06 | EIP-170 / EIP-3860 size gate | foundry/test/SSEMonitorRegistryV4.t.sol `testBytecodeSizeLimits` | TW, AC | DRV-V4-SIZE | 5d5867b |
| A-07 | V4 deployment script (owner-run, nonce-predicted wiring) | script/DeploySSEV4Candidate31340.s.sol | NI, SR, AD | DRV-V4-05 | 5d5867b |
| A-08 | Explicit response-as-receipt term (V3 unchanged) | market `responseAdmitsReceipt` | NI, SR, TW | DRV-V4-01 | 5d5867b |
| A-09 | Keeper bounties for permissionless transitions | — | NO | — | — |
| A-10 | Standby retainer payment | — | NO (design D-05) | — | — |
| A-11 | Provable-misconduct penalties for monitor bonds | — | NO | — | — |
| A-12 | Qualified negative evidence beyond conditional quorum (E7 adapter) | — | NO (design D-07) | E7 | — |
| A-13 | Stronger randomness (VRF/RSA adapters exist; not integrated with V4) | SSEVRFV25Adapter, RSA2048EntropyVerifier | NO for V4 | — | — |
| B-01 | Committee planner (quorum, exact cost, draw success probability, conservative risk, non-weakening alternatives) | tools/sse_v4_committee_planner.py | NI, SR, TW | DRV-PY-01 | 6d8bcfe |
| B-02 | V4 termsHash and EIP-712 digest encoders | tools/sse_v4_terms.py | NI, SR, TW | DRV-PY-01, DRV-V4-PARITY | 6d8bcfe |
| B-03 | V4 consumer UI (request builder, uploads, planner, bid comparison, award, tracking, outputs) | — | NO | — | — |
| B-04 | V4 provider UI/marketplace | — | NO | — | — |
| B-05 | Real compute adapter for V4 (reuse SHA256_CHAIN_8192 Docker worker) | tools/sse_compute_docker.py (V3) | ET for V3; NO for V4 wiring | — | — |
| C-01 | V4 role agents with durable cursor/journal | — | NO | — | — |
| C-02 | R424 reward collector dashboard integration | tools/sse_native_reward_collector.py | ET (R425); integration NO | — | — |
| D-01 | Unified one-command multi-role installer | scripts/sse_install.py | partial ET; unification NO | — | — |
| D-02 | Replaceable peer discovery hints in release manifest | release/chain31340-public-release.json | BL (owner infra) | — | — |
| E-01 | Explorer eth_getProof verification | — | NO | — | — |
| F-01 | V3 experiments E1–E6, E8 | evidence/, STATE_AND_EVIDENCE.md | LV | — | historical |
| F-02 | E7, E9, E10 | — | NO / owner-run | REMAINING_EXPERIMENTS | — |
| G-01 | Secret scan of tree + history | — | BL (needs tool execution) → DRV-SEC-01 | DRV-SEC-01 | — |
| G-02 | Remove abandoned login surface (R399–R407 except R400) | tools/sse_pos_r399…r407 | NO (needs owner review of references) | — | — |
| G-03 | HAND_BACK.md | handoff/HAND_BACK.md | NI | — | see HAND_BACK |
