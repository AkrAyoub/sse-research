# WP-08A research checkpoint — scalable monitoring retained, first authenticated observation format

**2026-11-10. Status:** source/test/ADR ZIP **delivered**, source/test files not yet committed to this GitHub branch; full signature tests and hosted CI pending. No Solidity or production settlement changes.

## Design choices
- Keep original G1–G5 plus all R0–R11/P0–P6 milestones. R3 remains **expandable, open monitor registry** with verifiable sampling, configurable per-lease committee size/threshold, Sybil/economic assumptions, no-show reassignments and consumer-independent bond release.
- Fixed 32 lifetime identities and 3-of-4 outcomes are legacy **prototype choices**, not permanent protocol requirements.
- ADR-001 *proposes* an explicit HTTP consumer-delivery experiment, physical N/F/S receipt/delivery cutoffs and experimental reservation fee `r=0` until standalone availability entitlement is justified. This does **not** rewrite old leases.
- ADR-002 defines canonical raw evidence, signed/authorized observation and the still-UNIMPLEMENTED physical certificate qualifier as different security claims.
- ADR-003 makes registry/scalability and liveness measurable R3 requirements.

## WP-08A code artifact
`SSE_R1_R4_WP08A_Observation_SDK_2026-11-10.zip`, SHA-256 `cb8876086d22145fd82710ac63e7ef9be84d98b3d4f50b0dfad644dee0d2b395`. It includes `tools/sse_evidence_wire_v1.py`, `tests/test_sse_evidence_wire_v1.py`, three ADRs and install/validation docs. The observation schema uses exact canonical JSON, Keccak-scoped payload/record hashes, EIP-712 off-chain signatures, bound chain/settlement/lease/epoch/SLA/resource/request identifiers, and reporter-claimed clock bounds. Authorization context and non-durable replay ledger are explicitly *experimental*. Verified monitor reports bridge only into WP-07 `RawObservation` and **cannot become `QualifiedFact`**.

**Local authoring test:** 33 cases discovered, **18 structural tests passed, 15 Ethereum-cryptography/replay tests skipped** because eth-account / pycryptodome are unavailable in the authoring container (no DNS package access). Full integrated suite projected at 309 Python and 52 Foundry cases; **NOT YET VERIFIED** on this branch. Existing user's main validation: 276 Python passed, 52 Foundry passed, 3/3 hosted CI green.

## Next validation gate
1. User extracts ZIP into this branch in original repository and runs all 33 tests with **no skips**, full Python suite, Foundry.
2. Commit and push source/docs; create draft PR, verify Python Windows + Ubuntu and Solidity Ubuntu checks.
3. Do not merge or invoke `sign_observation` with deployed key-custody secrets before confirming signature verification and signer-authority semantics. This is a research SDK, not a hardened production verifier.
4. WP-08B: provider-side signed challenge path, independent monitor client, persisted evidence archive and chain-authorized committee context.
5. R2/R3: independent policy-version and scalable-monitor redesign after threat model and soundness review.

**Provisional unchanged phase percentages:** R0 100, R1 62, R2 26, R3 15, R4 10, R5 10, R6 5, R7 15, R8 10, R9 5, R10 0, R11 0, P0 37, P1 55, P2 29, P3 39, P4 20, P5 0, P6 0. Equal-phase rounded engineering 22%, research 26%, overall 23%. New work is documented but not counted as accepted until integrated validation.

## WP-08A hosted CI milestone (research branch only)

Draft PR #6: https://github.com/AkrAyoub/sse-research/pull/6 . The `BadSignature` recovery failure was fixed without weakening the test. At commit `ec7be1d`, Ubuntu Python **309/309**, Windows Python **309/309**, and Ubuntu Foundry **52/52** passed in Actions run https://github.com/AkrAyoub/sse-research/actions/runs/43079326699 . All 15 additional signing and replay tests ran; no skips were reported in either Python job. Later commits are documentation/tracker only and must also pass their own CI checks.

**Provisional research-branch progress:** R4 advances **10% → 15% (+5pp)** for canonical signing and portable verification tests. This does not indicate an approved physical certificate verifier. R1 62%, R3 15%, P1 55%, P3 39% unchanged. Equal-weight averages: engineering **22%**, research **26%**, overall **23%**. The `main` branch tracker does not receive this update until PR #6 is merged.

**Remaining acceptance gates:** host retest against final commit; PR review/merge; independently authenticated chain committee/lease context; durable replay and raw-evidence storage; provider-signed challenge response; monitor/process integration; physical certificate qualification; on-chain policy versioning and proper R3 monitor scaling.
