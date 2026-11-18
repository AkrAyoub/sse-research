# WP09Q engineering decisions (14 November 2026)

## Verified inputs

- User's WP09P Foundry test: 134 passed, zero failed, 18 test suites.
- Deployed `SSESettlement` runtime measured with `address(settlement).code.length` = 22,400 bytes with Foundry optimizer runs 200; matches artifact exactly. EIP-170 headroom = 2,176 bytes.
- Prior Foundry gas-report 23,661 byte discrepancy remains unexplained but is not authoritative for the measured WP09P deployment.
- GitHub `main` source anchors of `OpenMonitorCommittee.sol`, `GlobalRosterSampler.sol`, and `SSESettlement.sol` were inspected in read-only mode; WP09Q's replacement anchors match each exactly once.

## Threats and mitigations

| Threat | Mitigation in candidate | Residual risk |
|---|---|---|
| Relayer chooses candidates | Verifies exact seed-determined global indices in order | If relayer withholds, request times out |
| Merkle proof tampering | Frozen root and position-specific proof verification | Historical proof data must be available |
| Replay or skipped batch | Cursor + per-index proof check | High on-chain storage/gas cost |
| Candidate exits between batches | Four provisional seats increment `activeAssignments` | Lock griefing until completion/cancel/timeout |
| Consumer closes partial assignment | `closeLease` unconditionally cancels unfinalized committee; pool unlocks | Cross-contract interaction merits reentrancy review |
| Timeout mid-proof | `expire` releases all provisional locks and seed | Keeper transaction needed |
| Fewer than four survivors | Fail closed and release partial locks | Lease liveness unavailable; refund follows closure |
| More than ten exits among sampled 40 | More eligible standbys may remain | Targeted 37 of 40 can still force expiry |
| Seed withholding | None; same immutable seed and expiry | VRF coordinator economics, proof availability still open |

## Priorities after local compile

1. Measure all five actual transaction-call gas deltas; a unit-test gas number for complete setup includes 40 bond registrations and is NOT the proof-call gas.
2. Verify deployed `OpenMonitorCommittee` runtime length after adding WP09Q (20,697 bytes prior, size may approach EIP-170).
3. End-to-end gas breakdown for N=160 with exactly 40 proofs: create + request VRF + callback + apply + five finalization batches + four confirmations + voting.
4. Audit the now-expanded `closeLease` cancellation behavior for every existing entropy mode; reentrancy state ordering remains important.
5. Add independent relayer proof availability and keeper deadline tests before proposing adoption.
