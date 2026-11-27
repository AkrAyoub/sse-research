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
| F05 Solidity compile | Passed at cabaa2b | Owner build --sizes exit 0, unchanged compiler settings; revalidate new checkpoint |
| F06 Compile/size repairs | Passed at 374cce8 | All five modules within limits; market runtime 22986 bytes; size test passed |
| F07 Full Foundry regression | Passed at 374cce8 | 305 passed, zero failed/skipped, 32 suites |
| F08 Focused V4 tests/fuzz | Passed at 374cce8 | 52 passed, zero failed/skipped; three fuzz tests 1024 runs each |
| F09 Python regression | Passed offline baseline at 374cce8 | 1606 offline passes plus all 3 separately executed opt-in integration tests passed; V4 lifecycle still pending |
| F10 ABI/EIP-712 parity | Partial | Compiled ABI checker passed at 374cce8; cross-language Solidity digest parity pending |
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

DEV-002 (closed at 374cce8; historical incident details):
- Owner ran forge build --sizes with original compiler settings, 91 files, Solc 0.8.24. Both dynamic and native test linking failed. Error: Stack too deep, contracts/SSEMonitorRegistryV4.sol:193:50 (reservedByLease[leaseId]). Exit 1.
- Owner log: ~/sse-v4-validation-logs/2c899f8591848bdc6948f98d6049f6f855ad5004/01-build-sizes.txt.
- Source correction 03225209fba0a0d5fcaeeb5f0c626795bb9430a4: memory-only DrawInput, private read-only selection and private atomic reservation helper. ABI, draw hash/threshold/order/budget, authorization, persistent storage and events preserved by static review; compilation not yet demonstrated.
- Regression source f96b0ed41cfad30df538709ca4ff90809c1fdbac: exact first draw/attempt event, incomplete draw leaves no reservations. Not executed.
- Owner retry at 111265b passed the former compiler error location but failed elsewhere; DEV-002 remains pending regression validation.

DEV-003 (closed at 374cce8; historical incident details): owner retry at 111265bd25fabbc0c0d751a8e1681bbba700a2cb failed stack too deep at SSEAdaptiveMarketV4.sol:475:46, exit 1. Residual verification and allocation split; no compiler setting changes. Further static fixes and regression source recorded in [audit pass 1](../audits/OWNER_VALIDATION_AUDIT_PASS_1.md). Mandatory audit and isolated validation before use; no live deployment authorization. Audit report commit 20ff4a150655e1b5a8978dde6eea680cc168cb2b.

Owner decisions unchanged: P-1 standby retainer rejected; P-2 keeper bounty and P-3 provable misconduct slashing remain undecided. Report2.pdf and Report3.pdf stay untracked. Preserve original chain31340/V3 and private wallet state.

## Consolidated owner validation at 68c6f4d0029723c6fa055d6378e7e1d62136f689
- Forge 1.9.0, Solc 0.8.24, Python 3.12.3, unchanged dependency pins and compiler settings. Clean source tree.
- 01-solidity-build exit 1, 91 files, stack too deep in SSEAdaptiveMarketV4.sol:239:18, accounting initialize call. DEV-004 source repair 4618b0f637e2318c542a48dc954c1fa864d6fa3f splits accounting initialization and event emission from lease recording; same atomic transaction, unchanged hash and funds. Unverified compilation.
- 02-v4-python-regression exit 0: 46 tests passed. 03-setup-regression exit 0: 4 tests passed. No skipped tests in these two runs. Historical full Python suite not executed.
- Compiled ABI and focused Foundry tests skipped because build failed. JavaScript syntax check not run because Node unavailable.
- Logs: ~/sse-v4-validation-logs/68c6f4d0029723c6fa055d6378e7e1d62136f689.
- Audit passes 2–4 added execution recovery, residual settlement backend/browser, and offline ABI checker. No live deployment. All unresolved audit blockers remain in force.

## Owner validation at cabaa2b0a842e1403b20c3ab5a0e51c64b2067d3
- Full Solidity build --sizes exit 0. DEV-004 compile blocker closed at tested SHA. DEV-002 registry regression tests and 1024-run reservation fuzz passed. DEV-003 residual lifecycle tests still blocked by market setup.
- Focused Foundry: 22 passed, 2 failed; full Foundry: 275 passed, 2 failed, 0 skipped. Both failures are StringTooLong in ledger constructor; market lifecycle suite did not execute. Do not interpret denominator as full intended coverage.
- Compiled ABI exit 1: ledger Withdrawal parameter name mismatch. Other checker assertions passed within its stated scope. Logs ~/sse-v4-validation-logs/cabaa2b0a842e1403b20c3ab5a0e51c64b2067d3.
- DEV-005: corrected undeployed ledger domain to SSEAdaptiveCommitteeVotesV4 in Solidity (4f19aeb) and Python (025a4db); added regression fixture (90d54f8). Old candidate domain signatures invalid under new domain. No V3 change.
- DEV-006: same Solidity commit normalizes Withdrawal indexed parameter name to account. Event topic/types/values unchanged. ABI checker not weakened.
- Next: rerun build, ABI, Python V4 tests, focused Foundry with 1024 fuzz runs and full Foundry. Inspect full size report and retain lint warnings for triage. No deployment authorization.

## Owner validation at 374cce84d71496e5d8acde892d8ccb30034fffec
All six checks exit 0: build, V4 Python (47), compiled ABI (zero mismatches), focused Foundry (52), full Foundry (305 across 32 suites), explicit size test (1; overlaps other suites). No failed/skipped tests in these runs. Focused fuzz runs 1024 each for conservation, reservation accounting and ordered sampling. Full suite uses default 256 fuzz runs. DEV-002/003/004/005/006 closed for observed failures at this checkpoint. Clean checkout. Runtime/initcode bytes: market 22986/24530, ledger 11023/11762, registry 6409/6664, board 6226/6408, standby 4636/4821. Market runtime margin 1590 bytes. Formation gas draw/activate: n7 s2 1064197/1015140; n7 s4 1229028/1044562; n10 s2 1373128/1255686; n10 s4 1541745/1287010. Foundry measurements only; E9 distributed experiment remains pending. Logs ~/sse-v4-validation-logs/374cce84d71496e5d8acde892d8ccb30034fffec. Full Python regression, browser validation, actual cross-language digest parity, resource enforcement, public endpoint security, installer readiness, qualified negative evidence, independent participation and isolated rehearsal remain open. No deployment approval.

## Full Python regression at 374cce84d71496e5d8acde892d8ccb30034fffec
Owner VM4707: 1609 tests in 21.407 seconds, exit 0, no failures/errors, 1606 passed, 3 skipped. Skips: test_sse_direct_delivery_anvil and test_sse_node_marketplace_anvil (explicit SSE_RUN_ANVIL_INTEGRATION opt-in); test_sse_docker_sla_live (explicit SSE_RUN_DOCKER_INTEGRATION opt-in plus local immutable worker image). These are historical integration paths, not V4 end-to-end proof. Keep their skipped status visible until individually executed. Clean source. Log ~/sse-v4-validation-logs/374cce84d71496e5d8acde892d8ccb30034fffec/07-full-python-regression.log. F09 offline baseline passed; F12/F14 retain integration acceptance requirements. No deployment approval.

## Historical opt-in integration checks at 374cce84d71496e5d8acde892d8ccb30034fffec
Owner VM4707: node marketplace Anvil test passed in 3.544s; direct delivery Anvil test passed in 3.722s with Docker disabled. Both exit 0. Anvil 1.9.0 pinned. Docker CLI 29.1.3, context unix:///var/run/docker.sock, DOCKER_HOST unset; daemon access and image identity not yet established. One of the original three integration skips remains (real Docker worker). Historical V1 integration evidence only, not V4 lifecycle. Clean source. Logs 08-node-marketplace-anvil.log and 09-direct-delivery-anvil.log under the existing 374cce8 log directory. F12 active, F14 pending actual resource validation. No live deployment approval.

## Real Docker worker validation at 374cce84d71496e5d8acde892d8ccb30034fffec
Owner VM4707: DEV-007 ordinary user Docker socket permission denied; existing sudo access verified, no membership or socket changes. Local Linux Docker 29.1.3, cgroup v2 systemd driver. Compute image built from source at tested SHA, image ID sha256:30ce70710b3088092bfdffb30f27877e756b5323e76d56a435e918e618416b8b, runtime UID/GID 10001, linux/amd64, size 46162494 bytes. Base pull digest sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b. Build definition uses mutable base tag; reproducibility hardening pending. Temporary local sudo Docker CLI wrapper, Python unprivileged. Real Docker worker test passed in 10.756s, exit 0; temporary worker removed; original three chain containers remained running, EL healthy. Logs 10-docker-build.log and 11-docker-live-regression.log in original validation log directory. All 1609 Python tests accounted for across offline run and separate opt-in runs. This verifies historical restricted worker configuration and correct output, not guaranteed CPU capacity, kernel-level measurements or V4 aggregate provider admission. F14 remains partial. DEV-007 closed for isolated test via existing authorization. No live deployment approval.

## Provider resource remediation (source-only, after validated 374cce8)
- b2f384a, 889d03a, 522b4dd, 9f26f87, add3cfd, 240aae8: committed profile/offer preimages, exact terms approval, strict immutable worker inspection, pending acceptance safety, queued job binding, regression fixtures and fail-closed installer defaults.
- 2ebbdaa, 6390140, 110f554, 55f1f4b, 6ac61f8: per-lease worker configuration keyed by decimal lease ID, aggregate CPU/memory/count limits across all accepted nonterminal leases and per offer; distinct worker names and canonical loopback endpoints; block provider planning until finalized event cursor catches up; inspect candidate worker before automatic acceptance; one new acceptance per snapshot and existing pending acceptance gate. Installer capacity defaults to zero. Tests written for two leases, memory overcommit, duplicate endpoint and capacity release. No tests executed after baseline.
- Policy provider.capacity requires positive integer cpuCores, memoryMiB and maxConcurrentLeases (maximum 64); provider.profiles and provider.offers contain exact canonical manifest preimages keyed by their commitments; provider.workers maps decimal lease IDs to imageId, container, url, dockerSocket. This supersedes temporary profile-keyed worker configuration. No automatic migration or provisioning. Owner must supply explicit resource budgets and rootless worker configuration. Existing VM4707 Docker test used rootful daemon and does not validate rootless V4 execution.
- Limitations: static owner budgets not independent hardware attestation; no writable storage; no automatic worker provisioning; existing job loop sequential; no cross-wallet host allocator; no guaranteed CPU reservation; no new runtime evidence. F14/F16/F18 remain partial. Next: bounded parallel execution with durable per-worker recovery and preflight resource observations; then owner-run regression and isolated V4 integration. No deployment authorization.

## Parallel provider execution and early response relay (source-only)
- ed6f9f6, 41d656c, bcb91ec, a9f8695, 163b699: bounded thread pool, durable RUNNING before work, per-worker quarantine of uncertain outcomes including after closure, immutable worker binding hash, consumer SLA upper bound correction, response ownership and commitment checks, explicit maxParallelJobs default 1 (range 1–64); regression fixtures written, not run.
- 8b2d6e6, 3e0155c: coordinator-only completion callback after persisted DONE, serialized journal reconciliation and response send while other worker threads continue. Failed early relay retains durable DONE and normal retry path. Regression fixture uses synchronization event to assert fast completion callback occurs before slower worker returns. No runtime or measured latency claims.
- Architecture unchanged: existing native PoS chain, V4 contracts, roles and SSE science. Provider local execution path strengthened. Remaining: rootless provisioning, operator-controlled quarantine reconciliation, kernel-level measurements, cross-wallet host accounting, writable storage, full runtime validation. Batch still waits for worker completion before next discovery/monitor cycle; transport timeout is not a hard process kill. F14/F16/F18 partial; all new sources untested. No deployment authorization.


## Owner validation at 559bc462 (2026-11-27 15:05 UTC)
- VM4707 hardware inventory: 4 vCPU, 11 GiB RAM (10 GiB available), 96G root filesystem (90G available); no swap. Exact source and dependency pins verified; Forge 1.9.0, Python 3.12.3.
- Build failed at foundry/test/SSEAdaptiveMarketV4.t.sol:473 because the silence regression function declaration was omitted. Focused Python: 55 collected, one failure and one import error; full Python: 1617 collected, same failure/error, 3 opt-in skips. The parity test contained a stray quote and the vote rejection test used a nonzero hash (Z=0x11 repeated) as its alleged zero-response fixture. JavaScript check not run (Node absent). Logs: ~/sse-v4-validation-logs/559bc46234fdb021f31043d459456c8bb07fe0d0.
- DEV-008/009/010: restore the test declaration, remove the stray quote, use an actual zero bytes32 in the negative fixture. No production logic, protocol or dependencies changed. All repairs await owner rerun; no claim of passed compilation or tests yet. Preserve the native chain and existing V3 evidence; use disposable isolated rehearsal resources instead of destroying existing VMs.

## Owner validation at 75bc0d7 (2026-11-27)
- All 306 Foundry tests across 32 suites passed; focused V4 53 passed with 1024-run fuzz; compiled ABI and size gate passed (market 22986 B); focused Python 57 passed; full Python 1619 collected, 1616 passed, 3 opt-in skips. DEV-008/009/010 resolved for tested SHA. No live deployment.
- Standalone parity export invocation matched zero tests due to anchored test name; Forge returned 0 but verifier correctly refused missing exports. Focused suite contains the actual successful test export. Run verifier directly against its 03-v4-foundry.log (not empty 06-parity-export.log); parity remains pending actual owner verifier output.
- New owner-run tools/sse_v4_isolated_rehearsal.py starts/stops its own fresh local Anvil, deploys via actual five-CREATE script and checks wiring, actual contract terms, standby promotion, signed vote transactions, silence rejection, exposure admission, residual consent and withdrawal. It uses explicit public test fixtures and accelerated isolated time; not actual distributed SLA evidence. Source not executed by assistant. Keep original V3 and live VMs intact. Fresh role hosts needed for installation and actual standby experiment; no live deployment authorization yet.

## Owner isolated V4 transaction rehearsal at 9dd2044 (2026-11-27 15:16 UTC)
- Owner ran actual five-CREATE deployment and isolated full contract transaction lifecycle on VM4707; exit 0, original live network unchanged. Isolated Anvil genesis 0x0eb66877e9d1da89ba616b1a676cc6c6a53a91c84d0b8c1804f59bfdc9a1b3df; five modules wired, market runtime 22986 B. Forge estimated deployment gas 14853886 (not measured native deployment gas).
- Actual focused Solidity export independently verified by Python: all four checks true (raw/reconstructed termsHash, market/ledger EIP712 domains). Deployed terms recomputation and provider plus monitor EIP712 signatures accepted in actual isolated transactions. No live SLA evidence inferred from fixture votes.
- Eight monitor registrations, 4+2 formation, one deliberately omitted confirmation followed by standby promotion (105275 gas); draw 736473 gas, activation 728564 gas. Success mask 4: P=1000000000000000 C=0 X=0; qualified failure without receipt mask 3: P=0 C=800000000000000 X=200000000000000; silence mask 7: P=C=0 X=1000000000000000. Silence-as-failure rejected InvalidPhase; fourth admission rejected ExposureExceeded. Three-epoch closure, evidence closure, bilateral allocation preserving history masks, withdrawal and zero market/ledger outstanding balance passed. Final service allocation P=1600000000000000 C=2400000000000000 X=0; 4e15 service funding conserved. Actual isolated tx receipts stored locally; no production state mutation.
- Artifacts: ~/sse-v4-validation-logs/9dd2044743116546d6747b86f008bcf26a3282fd/rehearsal-20261127T151600Z/ (receipts.jsonl, modules.json, deploy.log, broadcast). Owner reported 4 fresh 2-vCPU/4-GB VMs and 1 fresh 4-vCPU/12-GB VM; identities/disk/network not yet inventoried. Existing chain and V3 fleet preserved.
- Next gates: native-chain read-only deployment quote, authorized new V4 deployment alongside V3, finalized deployment verification and manifest, real provider/monitor/consumer agent execution, fresh installation and onboarding. Isolated rehearsal covers contract mechanics only, not integrated agent/worker lifecycle, browser, native-chain liveness or external independent operators.

## Fresh fleet inventory (owner observed 2026-11-27 15:19–15:20 UTC)
- VM4717, VM4718, VM4719, VM4720: each 2 vCPU, 3.8 GiB total / 3.3 GiB available RAM, 40 GB disk (38G filesystem, 35G free); proposed initial monitor, monitor, monitor+consumer, monitor+keeper respectively.
- VM4721: 4 vCPU, 11 GiB total / 10 GiB available RAM, 100 GB disk (96G filesystem, 93G free); initial native nonsigning full node, later provider subject to measured remaining capacity. No new validator keys authorized.
- All Ubuntu 24.04.4 LTS x86_64, Intel Core Ultra 9 285K, Python 3.12.3, cgroup v2, no swap; git/curl/Docker/systemd present, ZeroTier and Node absent. Distinct SSH host fingerprints observed. Shared private subnet and common VM platform; not independent operator evidence. Do not publish private LAN addresses or host fingerprint inventory unnecessarily.
- New app-only prerequisites script reuses pinned R152 ZeroTier package and R361 pinned TLS adapter. Does not pull native node images on small VMs. Existing R361 relay availability must be observed; fixed experimental relay is an optional transport, not independent RPC discovery. Native deployment result not yet received. New script source-only until owner run. Existing unified setup planner forces full node for application-only roles and has a privilege mismatch; do not apply it blindly on 4GB hosts. Fresh full-node install on VM4721 uses reviewed R147/R151 directly.
