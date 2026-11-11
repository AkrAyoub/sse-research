# ADR-002 (WP-08) — Evidence authenticity is not contractual truth

**Status:** PROPOSED research architecture, not an approved security proof or authority for production payouts. **Date:** 2026-11-10.

## Chosen trust-boundary pipeline

1. **Raw payload bytes**: bounded, content-addressed and archived. A digest does not guarantee the bytes remain available.
2. **Canonical observation**: exact schema, time *claim* interval, chain ID, settlement address, lease, epoch, SLA and resource commitments, request hash, nonce, observation type and payload hash.
3. **Cryptographic attribution**: EIP-712 signed record, recovered EOA signer, exact expected domain and message binding.
4. **Role authorization**: selected/confirmed monitor membership supplied by an independently verified canonical chain state (the first SDK version takes it as a *trusted context input* and does not fetch/verify the chain).
5. **Authenticated RAW report**: passes steps 1–4, but remains only the monitor's *statement*. It cannot automatically become `QualifiedFact`.
6. **Qualified physical claim**: separate soundness mechanism must establish actual contractual receipt/delivery/nonfulfillment under the manifest's explicit assumptions. **NOT IMPLEMENTED.**
7. **World-sound history exclusion**: only an independently justified qualified claim can intersect `{N,F,S}` to reduce uncertainty; contradictory reductions halt.
8. **Irreversible monetary release**: generic min/max entitlements and monotonicity checks from WP-02; keep unresolved funds if fact is inconclusive.

## Versioning and binding

WP-08's experimental off-chain EIP-712 domain is `SSEEvidenceObservation`, version `1`, with `chainId` and `verifyingContract`. The EIP-712 payload includes `recordHash`, nonce, lease, epoch, SLA policy, resource profile and request. `recordHash` commits to strict sorted-key ASCII JSON, and `payloadHash` commits to the original raw evidence bytes with distinct Keccak domain prefixes. The SDK **requires a nonzero SLA policy hash**. Legacy direct leases without one are not qualified under this interface.

WP-08 signatures are **not compatible with** the deployed `SSESettlement` V1 `MonitorVote` domain and must not be submitted directly as on-chain V1 votes. The binding to the settlement address in this experimental off-chain domain is scope separation, not proof that the contract recognizes the new schema.

## Important missing dependencies

- `VerificationContext.authorized_monitors` is **provided by the calling process**, not established by this package from finalized chain state. A malicious caller could lie about its context.
- `VerifiedObservation` is a Python dataclass and can be manually fabricated; Python does not establish a process security boundary. A privileged verifier service/SDK and controlled call graph are needed.
- In-memory `EvidenceLedger` detects duplicate signer/epoch nonce reuse only **within one process**. Production requires durable atomic storage or replay checks bound on-chain.
- This SDK does not establish whether event timestamps are authentic, monitors are independent, a result was physically delivered, a storage object persisted, or a machine reserved specified CPU/RAM.
- EIP-712 domain signing itself does **not provide replay protection**; application nonce tracking is separate (EIP-712 specification).

## Evidence inference requirements

| Authenticated item | Possible admissible histories without stronger assumptions |
|---|---|
| 4/4 local timeouts | N, F, S |
| 4/4 observed responses | N, F, S for *consumer-delivery SLA* |
| provider signed result | N, F, S without sound receipt/delivery guarantee |
| externally sound provider physical receipt | F, S |
| externally sound full contractual nonfulfillment after deadline | N, F |
| externally sound correct timely consumer receipt | S |
| conflicting justified certificates | HALT, no new automatic release |

## Next qualification gate (R4/R2)

Integrate the WP-08 SDK with independently running monitor and provider services; verify the exact expected on-chain committee and lease state against a trusted or multi-endpoint finalized chain view; archive raw bytes and signatures; then design *service-specific* physical attestations. Formally prove that each such attestation's allowed-world restriction always contains the true physical history under an explicit fault/clock model. Do not wire the current SDK to live funds.
