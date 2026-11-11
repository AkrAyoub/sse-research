# WP-08 (increment A): canonical signed monitor-observation SDK — validation checkpoint

**Date:** 2026-11-10. **Status:** research branch candidate, no production payout logic modified.

## Scope

- `tools/sse_evidence_wire_v1.py`: canonical, bounded observation record, nonzero chain/contract/lease/epoch/SLA/resource/request scope, distinct Keccak commitments for evidence payload and record, EIP-712 sign/recover, externally provided authorized monitor set, local nonce replay ledger, raw-only bridge to WP-07.
- `tests/test_sse_evidence_wire_v1.py`: structural/encoding and cryptographic/replay scenarios.
- ADR-001: chosen first physical HTTP delivery semantics, `r=0` experiment-only until availability reservation has sound entitlement.
- ADR-002: precise boundary from signed monitor observation to independently qualified physical fact.
- ADR-003: preserve scaled open-monitor roadmap without claiming it is already implemented.
- Existing `contracts/SSESettlement.sol` and on-chain V1 wire type are **unchanged**.

## Test results and constraints

Authoring container Python 3.13.5 has no `pycryptodome` / `eth-account`; installation attempt failed due unavailable DNS. **33 new tests discovered; 18 structural tests passed, 15 cryptographic/replay tests explicitly SKIPPED (not claimed passing).** On user's Windows venv and hosted Python 3.12 CI, existing pinned dependencies are installed; run the full new suite and verify all 33 pass. The original 276 Python tests and 52 Foundry tests are not yet rerun with these new files in this authoring container.

Future hosted and user's host results must be recorded here before integration/acceptance. Do not interpret no regressions or signature verification as established by this container alone.

## Security limitations

- The raw signed record does not prove physical service delivery, true timestamps, independent monitors, or sound negative evidence.
- EIP-712 is a new off-chain observation domain; not the deployed Solidity V1 `MonitorVote` typed message.
- The supplied authorization context is not cryptographically authenticated against chain state by this module.
- The replay ledger is process-local and not durable.
- The SDK does not produce or authorize WP-07 `QualifiedFact`, nor a real chain-finality `ChainSnapshot`.
- No production escrow release or committee redesign is included.

## Reproduction

```
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p 'test_sse_evidence_wire_v1.py' -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
forge build
forge test -vv
```

The full Python count is expected to grow from 276 to 309 if all 33 cases are discoverable; confirm observed counts rather than presuming success. Hosted CI on Ubuntu and Windows is required.

## Hosted CI after actual EIP-712 execution

**Acceptance evidence for the research-only observation SDK (not for physical SLA truth):** In PR #6, GitHub Actions run https://github.com/AkrAyoub/sse-research/actions/runs/43079326699 executed at corrected commit `ec7be1df444bfeed4195d5069a53b36d591f2553`:

- Python on **ubuntu-latest**: **309 tests passed**; the `SigningTests.test_malformed_signature_rejected` case executed and passed; **no skips reported**.
- Python on **windows-latest**: **309 tests passed**; the same malformed-signature case executed and passed; **no skips reported**.
- Foundry on Ubuntu: **52 tests passed**, no failures or skips.

The first Ubuntu test run failed because `eth-keys` raised `BadSignature` from malformed ECDSA recovery, which was not translated into the SDK's `AuthenticationError`. The verifier now explicitly catches `eth_keys.exceptions.BadSignature`; **the existing test detected the issue and passed unchanged after the fix**. This corrects error handling, not observation truth or external authorization.

**Still pending:** manual review/merge of PR #6, user's local Windows retest of the final commit, durable replay state, verified committee/lease state, remote provider-signed messages, preserved raw evidence, and physical SLA evidence qualification. The success of CI does **not** justify production escrow releases or prove `QualifiedFact` soundness.
