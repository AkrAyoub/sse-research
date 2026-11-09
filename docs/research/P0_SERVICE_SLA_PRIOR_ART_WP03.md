# P0 — Service-specific SLA and evidence mechanisms: focused prior-art check

**Review date:** 2026-11-09. **Scope:** selective primary-source review, **not** a systematic literature search or a novelty conclusion. The WP-03 service taxonomy and R1/R2/R4/R7 division were designed primarily from first-principles and inspection of the SSE implementation. The references below were checked *after* the initial WP-03 draft to evaluate, challenge and contextualize that design.

## Sources checked and precise implications

| Source | Verified point | Implication for SSE | Not demonstrated by that source |
|---|---|---|---|
| ISO/IEC 19086-1:2016, cloud SLA framework — https://www.iso.org/standard/67545.html | Provides common SLA terminology/building blocks; deliberately does **not** mandate a universal list of service-level objectives for all cloud services | Service kinds must bind to explicit versioned objectives and measurements | Does not prescribe SSE evidence histories or financial bounds |
| UNCITRAL, *Notes on the Main Issues of Cloud Computing Contracts*, SLA discussion — https://uncitral.un.org/en/cloud/sla | SLAs address capacity, latency, persistence, uptime and measurement methodology; importantly distinguishes performance at the point of provision from the point of consumption | Separate provider-side generation, output transmission and consumer-side receipt; define interval, reference point, measurement and audit procedures | Does not cryptographically prove transport receipt or remove network partitions |
| Akash Network, *Deployments & Lifecycle* — https://akash.network/docs/learn/core-concepts/deployments/ and SDL syntax — https://akash.network/docs/developers/deployment/akash-sdl/syntax-reference/ | Deployments advertise resource/price/placement requirements; compute manifests express CPU/memory/storage; accepted bids form leases | SSE resource profiles should specify exactly what is rented, distinct from what a one-shot probe can observe | A manifest by itself does not prove host delivered the specified CPU/memory |
| Filecoin documentation, storage proofs — https://github.com/filecoin-project/filecoin-docs/blob/main/core-concepts/filecoin-virtual-machine/proofs.md | Distinguishes initial Proof-of-Replication from Proof-of-Spacetime for continued storage | A storage SLA needs temporal durability/accessibility predicates and periodic verification, not simply an HTTP success at one instant | Filecoin's proofs are specialized to its storage protocol and cannot be casually reused for arbitrary OCI or HTTP service |
| Amazon S3 SLA — https://aws.amazon.com/s3/sla/ | Service commitment based on monthly uptime and service credits contingent on defined thresholds | A service SLA may involve aggregate measurement windows and non-binary remedies rather than one epoch's all-or-nothing outcome | Commercial service credits are not the same as SSE's cryptographic escrow safety |
| *AWESOME: an auction and witness enhanced SLA model for decentralized cloud marketplaces* (2022), DOI: https://doi.org/10.1186/s13677-022-00292-8 | Already combines customizable SLAs, auctions, a witness committee, monitoring and contract-based refunds/payments | Witness-based monitoring and SLA marketplace features are not novel by themselves | The abstract/description reviewed do not establish whether the paper handles SSE-style safe partial bounds under incomplete evidence; full protocol analysis remains necessary |

## Provenance of WP-03 choices

- **Borrowed high-level ideas / accepted practice:** service-specific objectives, explicit resource profiles, fixed measurement windows, distinguishing provision-side from consumption-side quality, service-type-dependent evidence.
- **Our design synthesis, not copied from one paper:** organize the work into R1 physical ontology, R2 economics, R4 authenticated evidence and R7 heterogeneous services; introduce the provisional `ServiceConditions` trace evaluator and its HTTP/compute-specific classifier.
- **Unvalidated SSE research hypothesis:** that a sound map from heterogeneous service observations to a conservative admissible-history set, followed by component-wise maximal guaranteed monetary allocation and bounded unresolved exposure, contributes something not already established. A systematic mechanism-by-mechanism prior-art comparison is required before claiming novelty.

## Concrete gap register for P0/P1/R1

1. Compare trustworthy-service oracle models with arbitrary service-specific proof mechanisms; trace what *exact* event they authenticate.
2. Survey formal semantics of SLA outcomes when consumer delivery is blocked but provider processing succeeded, including client responsibility and network-fault allocation.
3. Find closest work on partial settlement under disputed or missing observations (fair exchange, payment channels, contingent contracts, multi-party disputes), not just cloud witnesses.
4. Distinguish verifiable output, verifiable resource reservation, verifiable capacity over time, storage persistence, and point-of-consumption availability.
5. Document evidence-to-world soundness assumptions and whether each source provides a proof, a game-theoretic equilibrium, a service credit definition, or only an implementation.

This file records a **focused research check**, not an exhaustive systematic review. No historical claim that the original WP-03 model was derived from these papers is made.
