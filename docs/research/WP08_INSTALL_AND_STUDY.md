# WP-08A — Install, execute, and study the signed-observation SDK (Windows Git Bash)

## Summary and limits

**33 new unittest cases** in `tests/test_sse_evidence_wire_v1.py`. They test a canonical monitor-observation message and EIP-712 sign/recover, not physical evidence soundness. This is a research-only *off-chain* domain; DO NOT submit these signatures to the current Solidity `SSESettlement` V1. Old contracts remain unchanged.

## Integration into the original repository

From your SSE repository root in Git Bash, on the `main` branch with a clean working tree:

```bash
git status --short
git fetch origin
git switch --track origin/research/r1-r4-evidence-qualification-wp08
```

If you already created this local research branch, use `git switch research/r1-r4-evidence-qualification-wp08` instead of the last command.

Extract `SSE_R1_R4_WP08A_Observation_SDK_2026-11-10.zip` into the repository root, **preserving the `tools/`, `tests/` and `docs/research/` folders**. The zip includes only new first-party files; it does not overwrite the existing Solidity contracts.

Then:

```bash
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p "test_sse_evidence_wire_v1.py" -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
forge build
forge test -vv
git status --short
```

Expected if dependencies are installed: **33 WP-08A tests** with **zero skips**, **309 total Python tests** (previously 276), and **52 Foundry tests**. These counts are projections, not verified results for the branch. If a test fails, do not push/merge until inspected. Require no skipped signing tests.

After validation:

```bash
git add tools/sse_evidence_wire_v1.py tests/test_sse_evidence_wire_v1.py docs/research/
git diff --cached --stat
git commit -m "R4 WP08: canonical signed monitor observation reference and ADRs"
git push -u origin research/r1-r4-evidence-qualification-wp08
```

Create a **draft pull request** targeting `main`; check Python Ubuntu+Windows and Solidity Ubuntu GitHub Actions, then review the policy limitations before merging research-only code.

## Low-level call flow

```
Physical probe event (locally observed, possibly wrong about remote reality)
    |
    v
Canonical payload bytes -> payload_commitment() [Keccak with payload-specific prefix]
    |
    v
ObservationRecord(EvidenceScope, kind, result hash, payload hash, untrusted time interval, nonce)
    |
    v
canonical_bytes() -> record_hash() [distinct domain prefix]
    |
    v
EIP-712 typed_data(... chainId, verifyingContract, lease, epoch, SLA/resource/request hashes ...)
    |
    v
sign_observation(record, monitor private key) [development/agent signer]
    |
    v
verify_observation(envelope, VerificationContext(expected scope + confirmed monitor identities))
    |
    v
VerifiedObservation   [AUTHENTICATED RAW OBSERVATION ONLY]
    |
    v
to_wp07_raw(item) -> PhysicalPolicyState.with_raw(...) [NO WORLD EXCLUSION]
    |
    v
Physical outcome remains {N,F,S} without independently qualified physical evidence
```

The authorization context is provided by the caller rather than obtained from verified chain state. This API is not a hardened security boundary. `EvidenceLedger` is process-local and has no durable replay protection. The producer must independently archive the raw observation payload and signature. Separate R4/R2 integration must define real chain-state binding and physical attestation before releasing escrow.

## Monitor scalability is NOT postponed or cancelled

R3 will scale an eligible monitor pool independent of each lease's committee size. The present 32 lifetime identities and fixed 4-member committee are not final specifications. ADR-003 lists registry, randomness, no-show, bond, Sybil and recovery acceptance gates. Scaling headcount does not make timeout votes sound physical evidence.
