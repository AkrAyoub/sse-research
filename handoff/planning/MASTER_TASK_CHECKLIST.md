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
| A-10 | Standby retainer payment | — | NO — owner economics decision P-1 (DESIGN_DECISIONS) | — | — |
| A-14 | Keeper incentive: self-keeping of own leases by consumer/provider agents (D-09); on-chain bounty = owner decision P-2 | tools/sse_v4_agent.py step, installer selfKeep | NI, SR (self-keeping) | DRV-AGENT-V4 | pass 3 |
| A-11 | Provable-misconduct penalties for monitor bonds | — | NO — owner decision P-3 (equivocation-only proposal) | — | — |
| A-12 | Qualified negative evidence beyond conditional quorum (E7 adapter) | — | NO (design D-07) | E7 | — |
| A-13 | Stronger randomness (VRF/RSA adapters exist; not integrated with V4) | SSEVRFV25Adapter, RSA2048EntropyVerifier | NO for V4 | — | — |
| B-01 | Committee planner (quorum, exact cost, draw success probability, conservative risk, non-weakening alternatives) | tools/sse_v4_committee_planner.py | NI, SR, TW | DRV-PY-01 | 6d8bcfe |
| B-02 | V4 termsHash and EIP-712 digest encoders | tools/sse_v4_terms.py | NI, SR, TW | DRV-PY-01, DRV-V4-PARITY | 6d8bcfe |
| B-03 | V4 consumer UI (request builder, uploads→commitment, planner, bid comparison, award intents, lease tracking) | tools/sse_v4_console.py, tools/sse_v4_console_static/ | NI, SR, TW; output download/verify page NI (pass 3) | DRV-UI-V4, DRV-OUTPUTS-UI | b70f8b3, pass 3 |
| B-04 | V4 provider UI: marketplace browse/filter, bid intents; monitor registration/exit; account credits | same | NI, SR | DRV-UI-V4 | b70f8b3 |
| B-05 | V4 compute job runner + monitor prober (SHA256_CHAIN_8192, fail-closed otherwise) | tools/sse_v4_adapters.py | NI, SR; worker ET for V3 | DRV-AGENT-V4 | a2fd6ae |
| B-06 | Provider output service: /v1/compute serves stored output by requestHash; /v1/output consumer-signed (EIP-191, ≤10 min expiry, consumer read from finalized state) | tools/sse_v4_provider_outputs.py, systemd/sse-v4-provider-outputs.service.in | NI, SR, TW | DRV-OUTPUTS-V4 | bb6976e |
| C-01 | V4 role agents: finalized cursor, journal-before-broadcast, keeper/consumer/provider/monitor planners, signer unlock | tools/sse_v4_abi.py, sse_v4_state.py, sse_v4_agent.py, sse_v4_signer.py | NI, SR, TW | DRV-AGENT-V4 | a2fd6ae |
| C-03 | Provider auto-decodes consumer Terms from the finalized awardAndFund calldata (direct EOA calls; sender must be the lease consumer; accepted only if recomputed termsHash equals on-chain); contract-wallet consumers still need policy leaseTerms | tools/sse_v4_abi.py decode_award_and_fund, sse_v4_agent.py _decoded_terms | NI, SR, TW | DRV-AGENT-V4 | pass 3 |
| C-04 | Provider terms check for contract-wallet consumers: console recomputes termsHash from finalized views + handed-over Terms, emits policy snippet only on match | tools/sse_v4_console.py terms_check, Provider tab | NI, SR, TW | DRV-UI-V4 | pass 4 |
| B-07 | Bid pagination (offset/limit, bidCount) and page-local filters (valid only, max fee) for unbounded bid lists (SEC-05) | tools/sse_v4_console.py request, Marketplace tab | NI, SR | DRV-UI-V4 | pass 4 |
| A-15 | Gas-parametrized formation tests n∈{7,10}, s∈{2,4} with 15M per-call ceiling | foundry/test/SSEAdaptiveMarketV4.t.sol formationGas | TW (not executed) | DRV-V4-01 | 18351e9 |
| G-04 | Console POST hardening: same-origin JSON only; local mode requires loopback Host (CSRF/DNS rebinding) | tools/sse_v4_console.py do_POST | NI, SR | DRV-UI-V4 | pass 3 |
| C-02 | R424 reward collector dashboard integration: console reads collector latest.json (read only), per-validator attestation totals, block rewards, unavailable kept unknown, staleness flag | tools/sse_native_reward_collector.py (ET, R425); tools/sse_v4_console.py rewards(), Node tab | collector ET; integration NI, SR, TW | DRV-REWARDS-V4 | pass 3 |
| D-01 | Unified installer: V4 application roles + console services (chain clients still via R151/R358) | scripts/sse_v4_app_install.py, systemd/sse-v4-*.service.in | NI, SR (app layer); chain-client unification NO | DRV-INST-V4 | e8c1df1 |
| D-02 | Replaceable peer discovery hints in release manifest | release/chain31340-public-release.json | BL (owner infra) | — | — |
| E-01 | Explorer: blocks, txs + decoded V4 events, priority fee, eth_getProof MPT verification with path view | tools/sse_v4_proof.py, sse_v4_console.py | NI, SR, TW | DRV-EXPLORER-01 | b70f8b3 |
| E-02 | Node / validator page: EL peers, sync, head/safe/finalized, historical-state probe; validator balances via loopback beacon | tools/sse_v4_console.py (node, validators), static Node tab | NI, SR | DRV-NODE-V4 | bb6976e |
| F-01 | V3 experiments E1–E6, E8 | evidence/, STATE_AND_EVIDENCE.md | LV | — | historical |
| F-02 | E7, E9, E10 | — | NO / owner-run | REMAINING_EXPERIMENTS | — |
| G-01 | Secret scan of tree + history | — | BL (needs tool execution) → DRV-SEC-01 | DRV-SEC-01 | — |
| G-02 | Remove abandoned login surface (R399–R407 except R400) | tools/sse_pos_r399…r407 | NO (needs owner review of references) | — | — |
| G-03 | HAND_BACK.md | handoff/HAND_BACK.md | NI | — | see HAND_BACK |
