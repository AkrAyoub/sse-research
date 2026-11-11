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
