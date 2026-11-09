# R1 WP-03 — Implementation, limitations and test log

- Date: 2026-11-09; status: locally tested provisional research increment, **not merged or hosted-CI verified** at authoring time.
- Added `tools/sse_service_trace_reference.py` — stdlib-only service-specific finite physical timeline model. No production contract/source changes.
- Added `tests/test_sse_service_trace_reference.py` — 26 unit tests for HTTP/compute event ordering, deadlines, generation vs delivery, correct vs incorrect results, incomplete traces, N/F/S classification, monitor partition indistinguishability, and unsupported service kinds.
- Added `docs/research/R1_WP03_SERVICE_CONDITIONS_AND_TRACES.md` — detailed service taxonomy, four-layer distinction, SLA manifest draft, physical event meanings and phase ownership.
- Local command: `python -m unittest discover -s tests -p 'test_sse_service_trace_reference.py' -v`. **26 tests passed**, 0 failures/errors; Python in the work-package runtime. Full existing suite, Foundry, and CI for this new increment were **not** run here.
- Three unimplemented service types (`object_storage`, `oci_container`, `general_api`) intentionally raise `UnsupportedService`; HTTP/compute classification is based on simulated ground truth, not a verifiable remote evidence policy.
- No on-chain settlement rule, live monitor, SLA policy hash, cryptographic verifier, production resource attestation or EIP-712 representation was changed or supplied.
- ADR-001 remains open; do not conflate no *qualifying* physical receipt, no physical receipt ever, and no *verifiable* receipt.
- Existing `R1-PROVISIONAL-0` formal interpreter and new `R1-SERVICE-TRACE-PROVISIONAL-0` are two separate research artifacts. Cross-comparison is a future WP-04 gate.

## Integrating this work package

From the repository root, on a new branch based on the latest `origin/main`, extract this archive preserving `tools/`, `tests/`, `docs/research/`, then run:

```bash
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p 'test_sse_service_trace_reference.py' -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
forge build
forge test -vv
git diff --check
git status --short
```

Expect **26 tests in the new module** and **151 total Python cases** if the existing 125 from R1 WP-02 are all discovered, plus 35 unchanged Solidity cases. These are **expected**, not independently confirmed, CI counts. Review diff then commit/push branch and verify the hosted checks before merging.

- Subsequent focused P0 literature check added `P0_SERVICE_SLA_PRIOR_ART_WP03.md`; source distinctions and original-design provenance are documented. This was performed after the initial WP-03 model; no claims of prior systematic research.
