# V4 owner-run validation progress — 2026-11-27

Original immutable S1 checkpoint: 2c899f8591848bdc6948f98d6049f6f855ad5004.
Continuation branch: validation/v4-2026-11-27 (no PR, no merge into main, no live deployment).
Owner executes validation on VM4707 in ~/sse-v4-validation. Source changes via GitHub.
This is an execution overlay on MASTER_TASK_CHECKLIST.md and DEFERRED_RUNTIME_VALIDATION.md, not a replacement for either.
Only owner-observed results count as runtime evidence.

| Gate | Status | Evidence / next action |
|---|---|---|
| F01 Context recovery | Complete | Handoff and historical evidence recovered |
| F02 GitHub handoff | Complete | S1 remote matched exact SHA |
| F03 Isolated checkout | Passed | Owner verified exact SHA and clean worktree |
| F04 Dependency/toolchain | Passed | R429 and S1 identical pins; forge-std f3dae6e6ee381f25eb6a246f7da9b85c91a68219; OpenZeppelin cab19933c33c2ad1d4c7a84864a3601dddfd16f3; Forge 1.9.0, Python 3.12.3, Solc 0.8.24 |
| F05 Solidity compile | Failed on 68c6f4d | New stack-depth location at market line 239; DEV-004 source repair committed |
| F06 Compile/size repairs | Active | DEV-002/003 below; EIP-170/3860 measurements not available |
| F07 Full Foundry regression | Pending | After successful compilation |
| F08 Focused V4 tests/fuzz | Pending | Includes two new DEV-002 tests |
| F09 Python regression | V4 subset passed; full historical suite pending | Owner VM4707 at 68c6f4d: 46 V4 + 4 setup tests passed, zero failures |
| F10 ABI/EIP-712 parity | Partial | Independent Python residual digest test passed; compiled ABI checker and Solidity parity blocked by build |
| F11 Security/science review | Active; mandatory pre-use gate | Static remediation pass 1 committed; open findings in audit report; no certification |
| F12 Isolated deployment/lifecycle | Pending | Disposable keys, isolated RPC |
| F13 Consumer marketplace/UI | Source, unvalidated | Owner-run |
| F14 Provider bidding/execution/outputs | Source, unvalidated | Owner-run |
| F15 Monitor/standby/reporting | Source, unvalidated | Owner-run |
| F16 Agents/recovery | Source, unvalidated | Owner-run |
| F17 Explorer/node/validator/rewards UI | Source, unvalidated | Owner-run |
| F18 Installer/multi-role onboarding | Partial | Fresh-host test pending |
| F19 Public discovery/independence | Partial | Bootstrap and external participation unresolved |
| F20 Live V4 deployment | Not deployed | Explicit owner approval after gates |
| F21 E7 qualified negative evidence | Pending | Real controlled defect |
| F22 E9 scaling/concurrency | Pending | Actual gas/latency/throughput |
| F23 E10 independent deployment | Pending | Independent operators/fault domains |
| F24 Security/recovery/persistence | Pending | Secret scan and failure drills |
| F25 Consolidation/release | Pending | Preserve history/V3 |
| F26 Academic deliverables | Pending | Official rubric and original reports unavailable here |

## Incidents

DEV-001 (closed): initial fresh clone with --no-checkout was incorrectly checked for a clean tree before materialization. Owner verified empty index/worktree, checked out exact S1 SHA and reported V4_SOURCE_CHECKOUT_VERIFIED=true. No repository defect.

DEV-002 (open, source repair committed):
- Owner ran forge build --sizes with original compiler settings, 91 files, Solc 0.8.24. Both dynamic and native test linking failed. Error: Stack too deep, contracts/SSEMonitorRegistryV4.sol:193:50 (reservedByLease[leaseId]). Exit 1.
- Owner log: ~/sse-v4-validation-logs/2c899f8591848bdc6948f98d6049f6f855ad5004/01-build-sizes.txt.
- Source correction 03225209fba0a0d5fcaeeb5f0c626795bb9430a4: memory-only DrawInput, private read-only selection and private atomic reservation helper. ABI, draw hash/threshold/order/budget, authorization, persistent storage and events preserved by static review; compilation not yet demonstrated.
- Regression source f96b0ed41cfad30df538709ca4ff90809c1fdbac: exact first draw/attempt event, incomplete draw leaves no reservations. Not executed.
- Owner retry at 111265b passed the former compiler error location but failed elsewhere; DEV-002 remains pending regression validation.

DEV-003 (open, source repair committed): owner retry at 111265bd25fabbc0c0d751a8e1681bbba700a2cb failed stack too deep at SSEAdaptiveMarketV4.sol:475:46, exit 1. Residual verification and allocation split; no compiler setting changes. Further static fixes and regression source recorded in [audit pass 1](../audits/OWNER_VALIDATION_AUDIT_PASS_1.md). Mandatory audit and isolated validation before use; no live deployment authorization. Audit report commit 20ff4a150655e1b5a8978dde6eea680cc168cb2b.

Owner decisions unchanged: P-1 standby retainer rejected; P-2 keeper bounty and P-3 provable misconduct slashing remain undecided. Report2.pdf and Report3.pdf stay untracked. Preserve original chain31340/V3 and private wallet state.

## Consolidated owner validation at 68c6f4d0029723c6fa055d6378e7e1d62136f689
- Forge 1.9.0, Solc 0.8.24, Python 3.12.3, unchanged dependency pins and compiler settings. Clean source tree.
- 01-solidity-build exit 1, 91 files, stack too deep in SSEAdaptiveMarketV4.sol:239:18, accounting initialize call. DEV-004 source repair 4618b0f637e2318c542a48dc954c1fa864d6fa3f splits accounting initialization and event emission from lease recording; same atomic transaction, unchanged hash and funds. Unverified compilation.
- 02-v4-python-regression exit 0: 46 tests passed. 03-setup-regression exit 0: 4 tests passed. No skipped tests in these two runs. Historical full Python suite not executed.
- Compiled ABI and focused Foundry tests skipped because build failed. JavaScript syntax check not run because Node unavailable.
- Logs: ~/sse-v4-validation-logs/68c6f4d0029723c6fa055d6378e7e1d62136f689.
- Audit passes 2–4 added execution recovery, residual settlement backend/browser, and offline ABI checker. No live deployment. All unresolved audit blockers remain in force.
