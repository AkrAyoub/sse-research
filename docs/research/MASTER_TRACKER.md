# SSE master engineering tracker — R0 through R11

**Snapshot update 2026-11-09 (external Git Bash verification):** WP-01 source repair and original manifest verification remain documented. Foundry 1.9.0 and Anvil 1.9.0 were installed on the user host; Solidity 0.8.24 compiled 42 files successfully and all 35 Solidity tests passed across five suites (including fuzz tests at 256 runs). Python full-suite verification, full clean-clone CI reproduction, and review of compiler lint warnings remain outstanding. R0 estimated 55% (+15 percentage points); no R phase is complete. Mark gates only with reproducible evidence, links/logs and commit hashes. Update this file in each implementation session.

| Phase | Status | Work | Exit gate | Evidence to save |
|---|---|---|---|---|
| R0 | **IN PROGRESS — FOUNDRY TESTED / NOT COMPLETE (55%)** | Canonical baseline, dependencies, import repair, test CI, source traceability | Fresh clone installs; Python imports/tests and Foundry compile/tests run with recorded results | Git SHA, lockfile, CI transcript, test logs, bytecode hashes |
| R1 | NOT COMPLETE | Formal physical histories, world-sound evidence policies, reference evaluator | Versioned spec, independent N/F/S vectors, counterexamples, policy soundness arguments | Proof notes, fixtures, ADR-001/002/003 |
| R2 | NOT COMPLETE | Settlement, economics, replay/fuzz/invariant, lifecycle, versioned policy | No excess payout; distinct reward pools; exact residual 2-party validation; clean closure | Foundry invariant/fuzz logs, gas metrics, state diagrams |
| R3 | NOT COMPLETE | Scalable open registry, unbiased selection, fault config, recovery | No 32-lifetime cap; auditable selection; no stranded bonds/confirmation lock | Adversarial committee test logs, proof/selection traces |
| R4 | NOT COMPLETE | Signed evidence/wallet/RPC SDK, authentic service receipt, archive | Canonical interoperable signing; independent remote monitors produce verifiable records | Typed-data vectors, event/record fixtures, receipt tests |
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

R0 Work Package 01 in `FIRST_FOUR_WORK_PACKAGES.md`: narrow change to import/package monitor agent, pin dependency setup, actual tests and CI. The full audit's A01–A42 findings must be ingested into issues rather than silently forgotten.

## Finding-level status tracking

`AUDIT_ISSUES_42.csv` contains all 42 source-audit observations, priority, location and recommended remediation. Update its `Status`, `Assigned Phase`, `Evidence Link` and `Resolution Commit` columns when a finding is fixed, deliberately accepted as a research limitation, or superseded. A phase is not complete while blocking P0/P1 findings remain without accepted ADR/limitations evidence.

## WP-01 session evidence (2026-11-09)

See `docs/research/R0_VALIDATION.md` and `docs/research/WP01_CHANGES.md`. Source patch commit `f31f2b4` after baseline tag `source-audited-2026-11-08`. Baseline manifest 56/56 matches, Python syntax compiles, 36 isolated existing tests pass, full suite blocked by missing network-only dependencies, no Foundry. Next: connected Python 3.12 + Foundry full regression, no R0 exit until then. P0 screening and R1 question framing in `docs/research/P0_R1_SCIENTIFIC_BOOTSTRAP.md` are drafts only.

## User-host Foundry validation update (2026-11-09)

- User-supplied Git Bash transcript: `foundryup` installed Forge/Anvil **v1.9.0**, Solidity **0.8.24** compiled **42** files, `forge build` exited successfully with warnings, and **35/35 Foundry tests passed** across five suites. The fuzz tests in `Contracts.t.sol` and `ProtocolEconomics.t.sol` used **256** runs each.
- Record: `docs/research/R0_FOUNDRY_HOST_VALIDATION_2026-11-09.md`. This is **external user-host evidence**, not a test executed in the inspection container; exact host repository commit has not been independently reconciled.
- Open R0 gates: complete Python 3.12 dependency installation and suite, new signed monitor adapter tests, CLI smoke, CI, clean-clone and dependency resolution provenance. Solidity warnings require R2 review and must not be silently dismissed.
- Provisional phase estimates (R0-R11, P0-P6) are recorded in `PHASES_TRACKER.csv`; weighted average not implied. Equal-weighted engineering **13%**, research **6%**, whole project **10%**, rounded.
