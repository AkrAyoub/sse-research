# SSE master engineering tracker — R0 through R11

> **NEWEST CHECKPOINT — WP-08D hash-pinned signed provenance (2026-11-13, stacked draft PR #19):** [4/4 green CI](https://github.com/AkrAyoub/sse-research/actions/runs/43417690921) verifies **359/359 Python on Ubuntu, 359/359 on Windows, 52/52 Foundry, and fresh Anvil integration**. On `--rpc-url` capture, all state reads now use EIP-1898 canonical block-hash selector, the monitor signs a separate domain-scoped EIP-712 `SSEChainSnapshot` linking the observation evidence ID to block number/hash/time, and SQLite inserts the signed anchor with the original raw bytes atomically. Strict archive re-read verifies the raw/provider/monitor/anchor and current RPC's old block by height and hash; live `evm_revert` invalidates retrieval. **R4 25% → 30% (+5 pp); R5 unchanged 10%.** Equal-weight phase estimates: Engineering **23% (278/1200)**, Research **26% (180/700)**, Overall **24% (458/1900)**. **Not solved:** independently authenticated finalized-chain proof, cross-host archive availability, truthful physical fulfillment or monitor-independent observation. PR #19 stacks on still-draft PR #18; neither merged. See `R4_WP08D_SNAPSHOT_PROVENANCE.md`. Do not mistake an RPC's self-consistent canonical history for consensus/finality.

> **HISTORICAL CHECKPOINT — WP-08C live integration (2026-11-13, draft PR #18):** The isolated [four-job GitHub Actions run](https://github.com/AkrAyoub/sse-research/actions/runs/43412029509) passed **347/347 Python on Ubuntu, 347/347 Python on Windows, 52/52 Foundry, plus a genuine fresh Anvil integration job**. The integration deployed and wired the three SSE contracts; registered five bonded candidates; created a real marketplace request/bid and funded lease; confirmed four selected monitors; admitted a real epoch; launched separate signed HTTP provider and monitor-capture processes; verified saved raw evidence and signatures; rejected an unselected monitor; and asserted zero on-chain votes/payouts. Anvil lab keys/time, trust in a single RPC, consumer delivery and independently operated clouds are NOT solved. The raw archive and run manifest are saved as a 14-day CI artifact. **R4 increases from 20% to 25% (+5pp); R5 stays at 10%.** Equal-weight phase estimates: **Engineering 23% (273/1200), Research 26% (180/700), Overall 24% (453/1900)**. These are tracked planning estimates, not proof or percentage of production security correctness. **Next WP-08D: independent chain finality/state provenance, block-hash-pinned evidence, remote transport/retention and conditional physical-evidence certification review.** PR #18 remains draft, not merged.

> **HISTORICAL WP-08C SOURCE-ONLY checkpoint (superseded by live integration above):** Read-only chain-derived capture context and opt-in `--rpc-url` CLI binding now reject wrong lease/epoch/provider/commitment, incomplete 4/4 committee, and closed monitoring windows. Added mock-inspector refusal tests and `R4_WP08C_CHAIN_BOUND_CAPTURE.md`. WP-08B PR #7 has merged; its hosted 337/337 Python on both OSes and 52/52 Foundry remain the last validated baseline. WP-08C draft PR #18 now has [3/3 green hosted CI](https://github.com/AkrAyoub/sse-research/actions/runs/43410654263): 347 Python on Ubuntu, 347 on Windows, 52 Foundry; real funded Anvil capture integration, finality review and production acceptance remain pending. **R4 remains 20%** (no acceptance inflation); no Solidity money-rule changes, canonical finality proof, physical-delivery certificate, or multi-cloud node claims.

> **WP-07 provisional checkpoint (2026-11-10; research branch only):** A versioned conditional evidence-policy reference for PHYSICAL_DELIVERY and a distinct CHAIN_PUBLICATION SLA was authored and locally tested (50/50 new tests; 168 research tests discovered, 1 skipped from prior source-dependent module). Its assumptions do not provide actual certificate verification, canonical chain proof, or production monetary authority. The downloadable ZIP source still needs host/CI integration. Provisional R1 62%, P0 37%, P1 55%, P2 29%, P3 39%, P4 20%; engineering 22%, research 26%, total 23%. See `R1_WP07_PROGRESS.md` and `PHASES_TRACKER.csv`. Do not infer that R1's evidence soundness or new production payout policy is accepted.

> **CURRENT CHECKPOINT — WP-06 (2026-11-09):** [Draft PR #4](https://github.com/AkrAyoub/sse-research/pull/4) adds 17 real-EVM Foundry adversarial tests without modifying production Solidity. [Hosted CI on latest branch head](https://github.com/AkrAyoub/sse-research/actions/runs/42714597598) passed **52/52 Foundry**, **226/226 Python Ubuntu** and **226/226 Python Windows**. EIP-712 provider/monitor signatures, committee selection, timestamps, account credits and conservative arithmetic execute in the real test EVM. True physical fulfillment/delivery is still **stipulated by test scenarios** and no unconditional physical soundness, live attack or production policy approval follows. Provisional R1 **56%** and R2 **26%**; P0 **35%**, P1 **50%**, P2 **25%**, P3 **32%**, P4 **18%**. Overall phase arithmetic: engineering **21%**, research **23%**, whole project **22%**. **Next: R1 evidence-policy/certificate soundness under explicit network assumptions and R2 residual/risk policy.** Earlier dated checkpoint entries below are historical, not current status.

> **CURRENT ACCEPTANCE STATUS (2026-11-09): R0 ACCEPTED — 100%.** Commit `375b6ec0f2af233542f9235179f7e545b9d44279` passed GitHub Actions workflow #1 on `main`: Python Ubuntu, Python Windows, and Solidity Ubuntu (3/3 green, overall Success, 53s), as shown in the user-provided screenshot. A separate fresh clone also passed 106/106 Python and 35/35 Foundry tests, with dependencies installed from scratch. Initial source SHA manifest matched 56/56 entries. R0 is closed under its reproducible-source-baseline acceptance gate; this does **not** validate real distributed execution, evidence world-soundness or audit findings assigned to later phases. GitHub Actions reported nonblocking Node.js 20 deprecation/Ubuntu runner migration notices: handle during CI maintenance. **Next: R1 formal evidence policy and P0 novelty analysis; R2 security review follows evidence assumptions.** Progress: engineering 17%, research 6%, overall 13% (rounded equal-phase means). The dated checkpoints below preserve historical progress and must not be read as current status.

**Source Git checkpoint — 2026-11-09 (user-host evidence):** A Git repository was initialized on branch `main` in the validated working folder and an initial root commit `45689eaeaac0f4f65b16f3e06e60c0133925ab59` was created: `91 files changed, 8038 insertions(+)`. `git rev-parse HEAD` returned that SHA, and the final `git status --short` printed no entries, indicating a clean user-host working tree. The virtual environment `.venv-r0/` was added to `.gitignore`; no Python virtual environment or Foundry `lib/` sources appear in the staged file list. This is a **new snapshot history**, not the recovered historical project commits. No GitHub remote or CI execution has been demonstrated. **R0: 90% (+10 percentage points)**; remaining: clean-clone reproducibility, CI evidence, final gate review. This evidence is a user-provided transcript; it was not independently verified on the host.

**Previous snapshot update 2026-11-09 (external Python + Foundry host validation):** WP-01 source repair and original manifest verification remain documented. On the user host, Foundry 1.9.0/Anvil 1.9.0 passed Solidity 0.8.24 compilation (42 files) and **35/35 Foundry tests**. Python **3.12.10** with pinned requirements passed `pip check`, `compileall`, and **106/106 Python unittest cases**, including typed-evidence fixtures and CLI smoke. `git rev-parse HEAD` and `git status` initially failed before Git initialization; the newer Git checkpoint above supersedes that outcome. Clean-clone CI reproduction and real blockchain/network end-to-end verification remain outstanding. R0 was previously estimated at **80% (+25 percentage points)**; no R phase is complete. Test evidence is user-supplied, not independently rerun here. Update this file after meaningful increments.

| Phase | Status | Work | Exit gate | Evidence to save |
|---|---|---|---|---|
| R0 | **ACCEPTED — CLEAN CLONE + 3/3 HOSTED CI PASSED (100%)** | Canonical baseline, dependencies, import repair, test CI, source traceability | Fresh clone installs; Python imports/tests and Foundry compile/tests run with recorded results | Git SHA, lockfile, CI transcript, test logs, bytecode hashes |
| R1 | **IN PROGRESS — WP06 EVM TESTS PASSED / EVIDENCE SOUNDNESS OPEN (56%)** | Formal physical histories, world-sound evidence policies, reference evaluator | Versioned spec, independent N/F/S vectors, counterexamples, policy soundness arguments | Proof notes, fixtures, ADR-001/002/003 |
| R2 | **IN PROGRESS — SETTLEMENT CONTROLS TESTED / PRODUCTION POLICY OPEN (26%)** | Settlement, economics, replay/fuzz/invariant, lifecycle, versioned policy | No excess payout; distinct reward pools; exact residual 2-party validation; clean closure | Foundry invariant/fuzz logs, gas metrics, state diagrams |
| R3 | NOT COMPLETE | Scalable open registry, unbiased selection, fault config, recovery | No 32-lifetime cap; auditable selection; no stranded bonds/confirmation lock | Adversarial committee test logs, proof/selection traces |
| R4 | **IN PROGRESS — WP08D SNAPSHOT SIGNATURE AND REORG CI PASS (30%); EXTERNAL FINALITY / PHYSICAL SOUNDNESS OPEN** | Signed evidence/wallet/RPC SDK, authentic service receipt, archive | Canonical interoperable signing; independent remote monitors produce verifiable records | Typed-data vectors, event/record fixtures, receipt tests |
| R5 | NOT COMPLETE | Autonomous consumer/provider/monitor/executor node and UI | Independently running processes transact without one central harness | Multi-process E2E, process logs, key isolation |
| R6 | NOT COMPLETE | Signed releases, zero-manual-IP Ubuntu installer, discovery/gateway | Fresh VM auto-joins existing network with role selection and eligibility status | Install transcript, screenshots, TLS/manifest proofs |
| R7 | NOT COMPLETE | Compute, storage, OCI containers and API workloads | Remote leases/probes for each with fault, negative and inconclusive outcomes | Service metrics, container digests, evidence archives |
| R8 | NOT COMPLETE | Chain event indexer, local UI and global observatory | Rebuild finance from chain; never dashboard authority over payouts | Reindex logs, accounting reconciliation, role UI checks |
| R9 | NOT COMPLETE | Real multi-VM adversarial experiments | Repeatable success/N/F/S/missing receipt/churn/latency/cost datasets | Experiment manifests, tx receipts, raw datasets |
| R10 | NOT COMPLETE | Quantitative evaluation linked to publishable manuscript | All empirical claims data-backed; baselines comparable, assumptions explicit | Analysis scripts, statistical plots, manuscript review |
| R11 | NOT COMPLETE | Independent public release, artifact replication | Unaffiliated test installation reproduces representative experiments | Tagged release, external replication checklist |

## Suggested parallel tracks

- R0 first, while **R1 + P0** start immediately for formal semantics/novelty.
- R2 and R3 follow enough of R1 to avoid encoding bad assumptions.
- R4 shared SDK precedes R5 real agents; R3/R4/R5 unlock R6 onboarding.
- R7 workloads require R4/R5; R8 indexer can begin alongside agent work.
- R9 data and P4 experiment methodology start before P5 final results prose.
- R10/R11 follow evidence-backed R9; some release/testing documentation can be incrementally built earlier.

## Status vocabulary

`PLANNED`, `DESIGNED`, `SOURCE PRESENT`, `COMPILED`, `TESTED`, `DEPLOYED`, `MEASURED`, `ACCEPTED`, `BLOCKED`. Do not use `DONE` without a gate and evidence.

## Immediate next checkpoint

**WP-07:** formalize service-specific, assumption-explicit evidence certificate validation, admissible-world update rules, timeliness interpretation and counterexample-resistant settlement policies. Compare alternatives with the actual WP06 Foundry traces; **do not modify production payouts until the adopted policy has defensible world-soundness assumptions and a reviewed economic fallback.** R2 must also classify pending Solidity security/lint findings. The full source audit A01–A42 remains tracked.

## Finding-level status tracking

`AUDIT_ISSUES_42.csv` contains all 42 source-audit observations, priority, location and recommended remediation. Update its `Status`, `Assigned Phase`, `Evidence Link` and `Resolution Commit` columns when a finding is fixed, deliberately accepted as a research limitation, or superseded. A phase is not complete while blocking P0/P1 findings remain without accepted ADR/limitations evidence.

## WP-01 session evidence (2026-11-09)

See `docs/research/R0_VALIDATION.md` and `docs/research/WP01_CHANGES.md`. Source patch commit `f31f2b4` after baseline tag `source-audited-2026-11-08`. Baseline manifest 56/56 matches, Python syntax compiles, 36 isolated existing tests pass, full suite blocked by missing network-only dependencies, no Foundry. Next: connected Python 3.12 + Foundry full regression, no R0 exit until then. P0 screening and R1 question framing in `docs/research/P0_R1_SCIENTIFIC_BOOTSTRAP.md` are drafts only.

## User-host Foundry validation update (2026-11-09)

- User-supplied Git Bash transcript: `foundryup` installed Forge/Anvil **v1.9.0**, Solidity **0.8.24** compiled **42** files, `forge build` exited successfully with warnings, and **35/35 Foundry tests passed** across five suites. The fuzz tests in `Contracts.t.sol` and `ProtocolEconomics.t.sol` used **256** runs each.
- Record: `docs/research/R0_FOUNDRY_HOST_VALIDATION_2026-11-09.md`. This is **external user-host evidence**, not a test executed in the inspection container; exact host repository commit has not been independently reconciled.
- Open R0 gates: complete Python 3.12 dependency installation and suite, new signed monitor adapter tests, CLI smoke, CI, clean-clone and dependency resolution provenance. Solidity warnings require R2 review and must not be silently dismissed.
- Provisional phase estimates (R0-R11, P0-P6) are recorded in `PHASES_TRACKER.csv`; weighted average not implied. Equal-weighted engineering **13%**, research **6%**, whole project **10%**, rounded.

## User-host Python validation update (2026-11-09)

- Python **3.12.10** in `.venv-r0`; all pinned requirements installed; `pip check`: **No broken requirements found**.
- `python -m compileall -q apps services tools tests`: exited without diagnostic output.
- `python -m unittest discover -s tests -v`: **Ran 106 tests in 15.890s; OK**. Covers EIP-712 signed monitor adapter, authenticated signed probe, rejection of unsigned/mismatched responses, simulated controller state machine, Docker inspection, and existing utility tests.
- The `FullControllerFlowTest` uses a **fake chain**, not a real independently operated EVM or VM. No live multi-node or byzantine test can be inferred.
- `git rev-parse HEAD`, `git status --short`: originally failed before Git initialization; see latest Git checkpoint above for the new root commit. Do not claim clean-clone validation.
- Full transcript summarized in `R0_PYTHON_HOST_VALIDATION_2026-11-09.md`.
- Keep `.venv-r0/` excluded from version control (the original `.gitignore` excludes `.venv/` and `.venv-1/` but not `.venv-r0/`). Recover authoritative Git remote/history if present, otherwise initialize a new source snapshot with provenance recorded.
- Remaining R0 exit gates: source/release provenance, exact clean-clone GitHub CI run, and complete reproducibility under documented dependency tool versions. Review Solidity warnings during R2.
- Provisional progress: R0 **80%** (+25 pp); engineering **15%**, research **6%**, overall **12%**, with equal-weight arithmetic averages across R0–R11 and P0–P6.

## User-host Git source checkpoint (2026-11-09)

- Initial `find .. -maxdepth 4 -type d -name .git -prune -print`: no `.git` found at inspected depths.
- `.venv-r0/` added to `.gitignore` before staging.
- `git init -b main`, then `git add -A`: staged 91 files, including five Solidity contracts, Python apps/services/tests, Foundry tests and project tracking docs; no `.venv-r0/` or `lib/` staged in displayed inventory.
- `git commit -m "Establish validated SSE R0 source baseline"` succeeded as a new root commit: `45689eaeaac0f4f65b16f3e06e60c0133925ab59`.
- Final `git status --short` emitted no file entries. LF/CRLF warnings on staging are informational but line-ending normalization should remain consistent.
- Note: `R0_PYTHON_HOST_VALIDATION_2026-11-09.md` does **not** appear in the 91-file commit listing; this checkpoint documentation package includes it for incorporation into the next repository commit.
- Next gate: independent clean clone with fresh Python virtual environment, dependency retrieval, complete Python and Foundry tests, saved host logs, then a verified CI run if a remote is configured. Do not mark R0 accepted until then.
- R0 now **90% (+10 pp)**. Equal-weight engineering **16%**, research **6%**, full project **12%** rounded.
