# ADR-001 (WP-08) — First physical HTTP SLA and reservation entitlement

**Status:** PROPOSED for the first paper-core experiment, not approved for Solidity V1 or existing funded leases. **Date:** 2026-11-10.

## Original goals preserved

G1 escrow without a trusted marketplace settlement operator, G2 authenticated lease/epoch reporting, G3 monotone conservative partial settlement, G4 bounded exposure, G5 reproducible prototype. The later service catalogue (compute, storage, OCI, API), permissionless registry, independent processes, and multi-host experiments remain roadmap requirements.

## Chosen first physical service (paper experiment)

`HTTP_DELIVERY_EXPERIMENT_V1`: a correct deterministic response to a specific, unique request must **reach the contracted consumer** by the agreed physical delivery deadline `D_f`. Define `D_r <= D_f` as the provider's physical request receipt cutoff. Timing is measured with explicit uncertainty intervals when possible; an HTTP status, monitor response, signature, or blockchain inclusion time is not interchangeable with physical consumer receipt.

- **N**: no qualifying physical provider receipt at or before `D_r`.
- **F**: qualifying physical provider receipt occurred at or before `D_r`, but correct consumer delivery did *not* occur at or before `D_f`.
- **S**: qualifying physical provider receipt and correct consumer delivery both occurred at or before their respective deadlines.
- Unknown while the physical delivery deadline has not elapsed and evidence is incomplete: **retain all compatible worlds**; do not invent an F verdict from a timeout.

The **evaluation's stipulated ground truth** uses independent instrumentation. Live SSE cannot access ground truth automatically.

## Financial design choice

For the first *delivery-only* experiment, set reservation payment **`r=0`** in the physical N/F/S model. That avoids granting compensation just because the provider did not receive or may have refused a request. A separately purchased availability/reservation obligation can later have nonzero `r` **only after the contract states and independently justifies that entitlement**. The general SSE `F(N)=r`, `F(F)=0`, `F(S)=fee` model remains useful in research; no global removal of reservation fees is authorized.

This is a different *new SLA agreement* from existing funded Solidity V1 leases. Do **not** retroactively reinterpret V1's `N` ('no verifiable receipt') as physical N.

## Trust assumptions and measurability

- Consumer can lie about nonreceipt (refund incentives); provider can lie about receipt or execution (payment incentives); honest monitors can have incomplete/partitioned views.
- A signed report binds bytes to a key, not to remote physical delivery or honest clock time.
- A physical success certificate requires a separately defined and justified method for *correct consumer receipt* and *timely delivery*, not just the provider signing a digest.
- A nonfulfillment certificate requires a complete argument excluding **every** timely successful delivery, not just one monitor's timeout.
- A consumer cooperation/receipt signature can provide an **assumption-explicit** path to more settlement, but a consumer may withhold signatures. Liveness requires a separate dispute/termination rule.

## Unresolved before approval

1. Specify exact creation of challenge/request/response bytes and consumer receipt evidence.
2. Decide admissible clock/transport bounds, whether a consumer receipt witness can be dishonest, and the equivalent failure model.
3. Write formal soundness predicates for each proposed certificate. In unrestricted asynchronous networks, a finite timeout cannot establish absence of delivery.
4. Pre-register tests of both physically fulfilled-but-monitor-partitioned and failed-but-validly-signed scenarios.
5. Decide how unused/unresolved funds terminate fairly when no trustworthy receipt exists. Do not silently use a trusted arbitrator while claiming no trust.

**Acceptance gate:** signed service agreement and verifier specification with testable timing, trust, incentive and evidence definitions; only then modify R2 production policy in a new version.
