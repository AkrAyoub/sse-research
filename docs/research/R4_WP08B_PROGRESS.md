# WP-08B checkpoint — signed HTTP response → monitor observation → durable local archive

**Status:** WP-08B source artifact packaged for host integration; **NOT YET committed to this branch and NOT tested with real Ethereum cryptography in authoring container**. No production Solidity changes. The source ZIP is available in the linked conversation, not in this repository until manually extracted and committed.

## Goal, scope and limitations

- New `services/provider-agent/signed_http_service.py` is a **localhost-only** provider server that pre-signs one pinned lease/epoch/challenge with the existing Solidity V1 `ProviderResponse` EIP-712 message. It does not verify real chain lease state and only uses experiment keys passed via environment variable.
- New `tools/sse_http_signed_delivery_v1.py` fetches the bounded signed response (numeric 127.0.0.1 only; proxies/redirects refused), validates the provider signature, constructs and signs the separate WP-08A `SSEObservation`, verifies **both** signatures, and atomically archives exact HTTP bytes + monitor envelope in SQLite with lease/epoch/monitor/nonce uniqueness. Loading evidence re-verifies both signatures and payload commitment. The monitor authorization context remains caller-provided, not independently chain-authenticated.
- New `services/monitor-agent/evidence_capture.py` invokes the collector with synthetic development scope and monitor key from an environment variable.
- New `tests/test_sse_http_signed_delivery_v1.py`: **28** cases, including separate real OS processes on localhost, existing V1 signed_probe compatibility, malformed signatures/JSON, wrong lease/epoch/domain/provider, redirects, nonce reuse, archive persistence/corruption, missing provider, and no false physical-fulfillment inference.
- New `docs/research/R4_WP08B_SIGNED_HTTP_ARCHIVE.md` explains transport, cryptographic domains, economics limitations, reproducibility, and remaining R3/R4/P1 work.

## Verification checkpoint

- Authoring environment lacks `eth-account` and `pycryptodome` and cannot install them (DNS unavailable). **Python syntax/compileall passes for all new modules**.
- **5/5 non-cryptographic checks passed with deliberately substituted stub imports**, which do **not** validate signature cryptography or live HTTP exchange.
- **23/23 cryptography/network integration checks remain unexecuted**, rather than passed/skipped in the real suite.
- Existing WP-08A merged baseline: **309 Python tests** on Windows and Ubuntu CI, **52 Foundry tests** on Ubuntu, PR #6 merged.
- After extraction, expected full test discovery is **337 Python cases** (309+28), with **52** existing named Foundry tests, but no result is claimed until host and CI demonstrate it.
- Do **not** merge WP-08B or change escrow interpretation before full branch CI and test review.

## Follow-up gates

1. User checks out this branch and extracts the five-file ZIP to repo root preserving directory layout. Explicit `git add` of only five paths; never `git add docs/research/` if unrelated file deletions are present.
2. Run new 28 tests, full Python discovery and Foundry; verify **zero skipped crypto tests** on Windows and hosted CI.
3. Push the source/tests/docs, create a draft PR and review after all three CI jobs pass.
4. Later WP-08C: verify expected provider/committee/SLA against authenticated canonical chain state, externalize durable evidence commitments, and implement service-specific actual physical delivery qualification.
5. R3: replace lifetime 32-identity cap and fixed committee constraints with scalable Sybil-aware registry, unbiased selection and no-show recovery; this remains on the roadmap.

**No increase to numeric phase completion is justified yet.** R4 remains 15%; engineering 22%, research 26%, overall 23% (rounded equal-weight phase averages).

## Hosted validation checkpoint (later update)

- PR #7: https://github.com/AkrAyoub/sse-research/pull/7 (draft at this checkpoint).
- The initial hosted run https://github.com/AkrAyoub/sse-research/actions/runs/43086907371 passed Python Ubuntu **337/337** and Foundry **52/52**, but Windows had **one test-cleanup error**: `with sqlite3.connect(path)` commits/rolls back but does not close the connection, and Windows refused temporary database deletion. This was **not** a cryptographic validity or on-chain test failure.
- Commit `458c1caf0a437fdc33e3bcfe649564c5c6c103af` corrected that test using `contextlib.closing(sqlite3.connect(path))`, preserving transaction semantics and the tamper-detection assertion.
- Corrected hosted CI run https://github.com/AkrAyoub/sse-research/actions/runs/43087187187: **Python Ubuntu 337/337 passed, Python Windows 337/337 passed, Foundry 52/52 passed**; both the SQLite tampering test and two-process integration test executed. No failed or skipped tests were reported by the jobs.
- Source remains **research-only**: provider/monitor keys are experimental; addresses and authorization context are supplied by the caller; only numeric loopback HTTP is supported; SQLite is a local archive; neither signature establishes consumer-side physical delivery nor a sound `QualifiedFact`. The main chain payout code was not modified.
- **Phase estimate on this research branch:** R4 now **20% (+5 percentage points for WP-08B)**, subject to PR review and merge. Other percentages unchanged. Equal-weight totals: engineering `268/12 = 22.33%` → **22%**, research `180/7 = 25.71%` → **26%**, overall `448/19 = 23.58%` → **24%**. These are planning estimates, **not measured percentage of security correctness**.
- Remaining gates: review PR and merge; user host retest after pulling the final merged version; derive authorization from a trusted canonical chain view; replicate/archive evidence independently; handle remote TLS and source/RPC trust; define sound service-specific delivery certificates and future versioned monetary settlement; continue scalable open-monitor R3 design.
