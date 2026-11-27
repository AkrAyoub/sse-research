# Work log — resume checkpoint

Date: 2026-11-27. Initial source baseline R430 98c4b49aaa6ffef04d5071aa46e0db4965751299. Handoff commits documentation only. No deployed state changes. Most recent live user test: R429 (56557b0992b1dfbd2ecdcc9180150f8b75f4c716) on VM4707, Forge1.9.0 Solc0.8.24: 7 standby lifecycle tests + 3 ordered sampling tests, 1024 fuzz runs, 10 passed 0 failed 0 skipped. R430 candidate vote ledger has not been compiled/tested. R424 collector running and R425 6/6 Python tests passed.

## Next exact task
1. Inspect clean local checkout, pinned dependency configuration and actual source. Run baseline tests using available platform-compatible tooling; record compiler, dependency revisions, test outputs and sizes.
2. Implement V4 market integration with standby lifecycle and preconfirmed vote ledger, capacity reservations, deadline/refund paths, and full integration/invariant tests. Do not just add another isolated helper. Preserve V3. Address EIP170/EIP3860 limits if needed.
3. Continue through ROADMAP_AND_ACCEPTANCE.md, prioritizing P0 vertical slices and owner UI requirements. Review actual report before negative evidence policy changes.

## Resume discipline
Append dated entries with current SHA, files/changes, exact commands and results, blockers, next step. On context reset read CLAUDE.md and this file, resume without redoing completed tasks. If tool quota/process stops, cannot actually continue until restarted; leave durable checkpoint. Do not claim live testing or deploy to VM. Produce HAND_BACK.md before handback. Record any assumptions and tradeoffs. Keep source committed on handoff branch only. No merge/main changes.

## Owner-only follow-up
Original Milestone4 rubric and earlier reports not retrieved; copy originals locally into handoff/references/ and reconcile. Live VM logs/evidence remain on hosts; collect sanitized copies later with owner. Do not import wallets, secrets or signer state. Owner to review new source and execute staged real VM tests.
