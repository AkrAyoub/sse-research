# Initial codebase audit — 2026-11-27 (source-only session S1)

Method: static reading only (no compile, no execution). Baseline HEAD 394705a (= R430 98c4b49 + handoff docs).
Status labels per handoff/GOVERNING_INSTRUCTION.md §3.

## Inventory (top level)
| Area | Size / location | Historical status (from STATE_AND_EVIDENCE) | This-session finding |
|---|---|---|---|
| Solidity contracts | 21 files, 5457 lines in contracts/ | V2 + V3 market/ledger Existing live-verified on chain31340; R428 standby + R426 ordered sample Previously execution-tested (R429 10/10); R430 V4 ledger and R411 V4 market never compiled | V4 candidate was disconnected from standby/sampling/capacity helpers |
| Foundry tests | 28 files in foundry/test | R342e 36 tests (V3), R429 standby/sampling 10 tests | No tests existed for V4 market or V4 ledger |
| Python tools | 192 files in tools/ (many R-numbered one-off gates) | Many execution-tested on VMs | Heavy duplication of VM-specific one-shot scripts; V3-only agents; no V4 ABI support |
| Python tests | ~100 files in tests/ | R425 6/6 etc. | Not re-run (prohibited) |
| Installers | scripts/sse_install.py + ~35 shell scripts, systemd/ | R358 validator installer live-tested with manual steps; R147 full-node installer refuses other roles | Not unified; VM-specific paths remain (see INSTALLER_AUDIT) |
| Dashboard | tools/sse_pos_r384_v3_dashboard.py, r388/r389/r392, R398 tunnel | Live-verified read-only V3 dashboard | V3-only; no marketplace request builder, no explorer proofs (see DASHBOARD_AND_UI_AUDIT) |
| Docs | docs/ (~190 R-numbered), evidence/ JSON | Historical | Headings often stale; handoff/STATE_AND_EVIDENCE.md is authoritative |

## Classification summary
- **Existing live-verified:** native chain31340 PoS (3 validators), V2/V3 market+ledger deployments, V3 lease experiments E1–E6, E8, read-only V3 dashboard + public tunnel, native reward collector R424.
- **Previously execution-tested (not deployed):** SSEStandbyCommittee (R429), SSEGlobalCommitteeSample.drawOrdered (R427), risk model R412/R417.
- **Candidate only, never compiled:** SSEAdaptiveMarketV4Candidate (R411), SSEAdaptiveVoteLedgerV4Candidate (R430), SSEMonitorCapacity library.
- **Disconnected:** SSEStandbyCommittee, SSEGlobalCommitteeSample, SSEMonitorCapacity were not used by any market. Legacy OpenMonitorCommittee / GlobalRosterMerkle / GlobalRosterSampler / SSESettlement (V1) are prior designs.
- **Obsolete/duplicated:** V1 SSESettlement fixed 4/3; V2 superseded by V3 (kept: deployed); V4Candidate superseded in this session by SSEAdaptiveMarketV4 (kept for provenance). Abandoned owner-login components R399–R407 (except R400 pause) per STATE_AND_EVIDENCE.
- **Contradicting requirements (V3/V4Candidate):** seats chosen implicitly as min(eligible, gas bound, payable) rather than explicit consumer n; award only after bidding window; bounded rotating eligibility window instead of global sampling; all window candidates locked at funding; no standby/promotion; signed response not usable as receipt even by agreement.
- **Unimplemented:** V4 agents, V4 UI request builder/bid comparison, storage/hosting services, explorer eth_getProof verification UI, unified installer for all roles, faucet deployment, keeper bounties, standby retainer, provable-misconduct penalties.

## Converted into tasks
See handoff/planning/MASTER_TASK_CHECKLIST.md (single authoritative status list).
