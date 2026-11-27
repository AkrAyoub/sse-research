# Architecture audit — 2026-11-27

## Intended final architecture (from REQUIREMENTS.md)
Native PoS chain (EL/CL, validators) ← independent of → application layer: Board (requests/bids) · Registry (monitor
bonds/capacity/sampling) · Standby (formation) · Ledger (votes/rewards) · Market (escrow + SSE accounting) ← role agents
(consumer/provider/monitor/keeper, event-driven, durable journals) ← node console (role-capability UI, explorer) ← installer.

## Current vs intended
| Layer | Current (source) | Gap |
|---|---|---|
| Contracts | V3 deployed; V4 integrated candidate added this session (5 modules) | Compile/size/tests deferred; keeper bounty, standby retainer, misconduct proofs absent |
| Agents | V3 tools R349–R380, r351 journal, r353 policies | No V4 event decoders/agents; planner + encoders added (tools/sse_v4_*.py) |
| UI | V3 read-only console + unsigned intents | No V4 request builder/bid comparison/committee planner UI |
| Explorer | R384/R8 read-only explorer | No eth_getProof verification view |
| Installer | sse_install.py + role-specific scripts | Not unified across roles; VM-specific paths |

## Dependency map (V4)
market → {board, registry, standby, ledger} (immutable, verified at construction); ledger → AdaptiveMonitorQuorum;
standby → AdaptiveMonitorQuorum; market → SSEExposureAccounting → SSEEntitlementBounds; market → SSEHistoryPolicy,
SSEAuthenticatedEvidence, OpenZeppelin EIP712/ECDSA (submodule pin; verify DRV-01).
SSEGlobalCommitteeSample and SSEMonitorCapacity are now unused by V4 (superseded by registry sampling); kept, flagged for
removal after review (REFACTORING_LOG R-02).
