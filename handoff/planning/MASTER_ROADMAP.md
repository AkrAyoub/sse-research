# Master roadmap (source-only era)

Order is by dependency. Every runtime step is owner-run (DEFERRED_RUNTIME_VALIDATION.md).
1. **Owner validation of S1 contracts** (DRV-01, DRV-V4-01..SIZE, DRV-PY-01, DRV-V4-PARITY). Fix any compile/test failures in
   source in the next session.
2. **Close contract gaps** A-09 keeper bounty, A-10 standby retainer (owner decision on economics), A-13 randomness option.
3. **V4 agents** C-01 on top of r351 journal; provider execution only from finalized EpochStarted.
4. **V4 UI** B-03/B-04 + E-01 explorer proofs, reusing the planner and encoders.
5. **Installer unification** D-01, D-02.
6. **Owner-run deployment** of V4 as a NEW version on chain31340 (or a fresh demo chain — owner decision), then E7/E9/E10.
History: original roadmap (handoff/ROADMAP_AND_ACCEPTANCE.md) remains the work-package definition; this file records order.
2026-11-27 change: execution items moved to owner; V4 contract integration done first because every agent/UI step depends on its ABI.
