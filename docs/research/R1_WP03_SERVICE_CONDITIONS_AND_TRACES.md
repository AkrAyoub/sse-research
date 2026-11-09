# R1 WP-03 — Service-specific SLA conditions and physical event traces

**Status:** R1-SERVICE-TRACE-PROVISIONAL-0. Scientific/design reference only, **not an approved settlement policy**. 2026-11-09.

## Provenance and relationship to prior work

The initial service taxonomy, trace classifier, and R1/R2/R4/R7 ownership were **original project design synthesis**, developed from the SSE repository and generic SLA engineering principles—not copied from a dedicated literature review. A subsequent focused **primary-source** check of ISO/IEC 19086-1, UNCITRAL cloud-contract guidance, Akash resource manifests, Filecoin storage proofs, the Amazon S3 SLA and the AWESOME academic marketplace supplies relevant precedents and design constraints. See `P0_SERVICE_SLA_PRIOR_ART_WP03.md` for exact URLs, what each source supports, and what remains unproven. In particular, defining service-specific objectives and using witness committees are **not** SSE novelty claims.

## 1. The fundamental architecture: what is leased vs what is observed

Every paid lease must commit to both **what service** is being purchased and **which observable/physical property defines fulfillment**. A generic quorum does not determine whether the purchased service was provided. A quorum merely aggregates reports. More detailed monitoring is justified only after the contractual objective is unambiguous.

Four logical layers must stay separate:

1. **Service specification / contract terms:** service kind, workload identifier, resource promises, quantities, end-user entitlement, boundaries, quality metrics, receipt cutoff, fulfillment deadline, accepted proofs and policies, fees. Signed or committed in advance.
2. **Physical history:** request transmitted, provider received, workload executed, output produced/correct, result sent, consumer received, storage persisted, container stayed available, etc. Some events may occur without producing any evidence.
3. **Observation / evidence:** monitor timeouts, HTTP status/bytes, signatures, chain inclusion, client receipt signatures, telemetry attestations. Provenance/consistency of these records is distinct from the truth of their contents.
4. **Financial settlement:** interpret evidence as a *sound* nonempty set of histories, then compute lower/upper provider entitlement, guaranteed refund, and escrow retained; enforce exposure budgets.

### Where the decisions belong in our roadmap

| Phase | Responsibility | Acceptance issue |
|---|---|---|
| **R1** | Define service taxonomy, physical predicates, contractual N/F/S histories, observation soundness and measurable deadlines before implementing more services | Each versioned SLA has an unambiguous fulfillment predicate and stated assumptions |
| **P1** | State adversarial capabilities, clock/network/receipt assumptions, service-specific observability limitations | Explicit physical-world model and fault/clock assumptions |
| **P3** | Formalize protocol messages, signed/committed SLA profiles and their service-specific semantics | Published protocol specification with cross-language traceability |
| **R2** | Bind financial release rules, reservation fee, penalties, deposit caps, delayed evidence, disputes and fees to the *approved* SLA policy | Value conservation + safe allocations for the actual chosen policy |
| **R4** | Implement canonical schema, profile hash, typed signatures, signed receipts/proofs, verifiers, archival and version negotiation | Monitor and consumer can independently verify an authenticated evidence package |
| **R7** | Implement real HTTP, deterministic compute, storage, OCI and general API workloads with their own probe and quality tests | Workload-specific remote, negative, ambiguous and adversarial tests |
| **R9/R10/P4** | Measure each kind's timeliness, receipt failure, partition ambiguity, cost, availability, and settlement outcomes | Repeatable comparative experiments and datasets |

Designing the service family exclusively in R7 would be **too late**: R2 payouts and R4 evidence format would already have embedded unchecked assumptions.

## 2. Repo-specific facts inspected (main, 2026-11-09)

- `contracts/SSESettlement.sol` stores `serviceEndpointHash`, `resourceProfileHash`, `slaPolicyHash`, `epochFee`, `reservationFee`, `responsePeriod`, `monitoringGrace`, `evidenceWindow` and exposure constraints. `admitEpoch` derives a deterministic challenge response hash and creates three deadlines from `block.timestamp`. The contract does **not** execute an arbitrary service-specific SLA interpreter on chain.
- `services/provider-agent/http_service.py` serves `POST /v1/challenge` on loopback and returns a deterministic response hash. It says it does not verify a lease, sign the result, or prove provider identity.
- `services/provider-agent/compute_http_service.py` offers `/v1/challenge` and `/v1/compute`. `tools/compute_workload.py` computes a deterministic SHA-256 chain. A correct digest is **not** proof of CPU reservation, hardware isolation, or requested CPU time.
- `services/provider-agent/resource_profile.py` commits `imageId`, `cpuMilli`, `memoryBytes`, `endpoint`, `slaMetric`, and `reservationBasis`; its supported `slaMetric` is `TWO_HONEST_MONITORS_TIMELY_VALID_RESPONSE_V1`. A matching profile hash proves declared-byte integrity, not resource delivery.
- `tools/sse_compute_docker.py` checks *local* Docker configuration and a deterministic result; it expressly disclaims trusted hardware attestation and independent remote monitor verification.

These source facts motivate the distinction between **service correctly answered a challenge** and **the leased resource was actually provisioned at the promised quality**. We have not changed the Solidity contract.

## 3. Service classes and conditions: provisional design catalog

| Service kind | What consumer buys | Example SLA fulfillment predicate (proposal) | What is *not* established by a generic HTTP ping |
|---|---|---|---|
| HTTP challenge | Timely and correct answer to a challenge | Correct bound answer generated or **delivered to consumer** before deadline, per selected mode | Proof that consumer received it; absence of network partitions |
| Deterministic compute | Execution/result of committed workload | Correct digest of committed workload plus contracted destination/deadline; CPU execution requires a separate validated execution fact | Real CPU time, reserved vCPU, image/container integrity |
| Object storage | Durable storage of a committed object | Correct PUT receipt, retention over contracted interval, authorized GET accessibility and integrity challenges | Durable storage from one successful GET |
| OCI container | Provisioned compute environment over time | Correct image digest, CPU/memory/isolation bounds, ready state, uptime across a time interval, optional job result | Memory/CPU availability from an application health response |
| General API | Defined request-to-response semantic behavior | Endpoint/method, allowed errors, response schema, correctness predicate, latency window, availability target and rate/volume | API accuracy or SLA compliance from a basic 200 response |

The last three service kinds are **reserved**, not implemented in the WP-03 classifier. They deliberately raise `UnsupportedService` until versioned definitions and trusted measurements exist. Even for compute, this WP-03 simulation cannot authenticate actual hardware execution.

### Minimum proposed versioned SLA manifest (future R4 schema)

- `serviceKind` and `slaVersion`, with explicit supported policy identifiers (never silently reinterpret old hashes).
- `provider`, `consumer`, chain ID, settlement address, lease ID/epoch ID and request identifier or committed request hash.
- `resourceProfileHash`, endpoint identity, immutable image or object digest when applicable.
- `acceptanceDeadline`, `fulfillmentDeadline`, and exact **which event / actor / clock** each applies to; allowed skew and latency assumptions.
- `fulfillmentMode` such as correct result generated vs correct result received by consumer, plus correctness predicate/version.
- `evidencePolicyVersion`, admissible evidence types, trust model and disputed/contradictory record procedure.
- `epochFee`, `reservationFee`, exposure cap, funds-retention and bilateral residual-settlement terms.

**Important:** no canonical hash or on-chain acceptance of this schema is claimed in WP-03. Designing compatibility with current `slaPolicyHash` is an R4/R2 task. A hash commits bytes; it does not validate semantics or enforce a hidden off-chain rule.

## 4. Ground-truth event ontology implemented in `tools/sse_service_trace_reference.py`

- Events carry `(kind, actor, at, artifact, valid_result)`.
- `actor` is consumer/provider and validated against the event kind; `artifact` matches the same result across produced/sent/delivered events.
- `at` is a **logical simulated tick**, not a signed UTC time, Ethereum block timestamp, or trusted delivery certificate.
- The physical trace is stipulated complete through `closed_through`. Without that completeness assumption, absence of an event cannot imply the physical event did not occur. Real monitors do not possess such omniscient traces.
- `REQUEST_SENT`: consumer transmitted the epoch request.
- `PROVIDER_RECEIVED`: provider physically received it, which is **not** inferred from an ACK signature.
- `WORK_EXECUTED`: ground truth (simulation) that a named compute job actually ran; it is not obtainable from the current digest alone.
- `RESULT_PRODUCED`: provider made an artifact; `valid_result=True` is a ground-truth correctness label supplied by the simulator, not a verified signature or remote attestation.
- `RESULT_SENT`: provider emitted bytes. A malicious provider could send junk without producing the correct result.
- `CONSUMER_RECEIVED`: consumer physically received the named artifact; delivery is distinct from provider send.
- `ACK_SIGNED`, `RESPONSE_SIGNED`: key produced a statement; neither event implies honest claims or actual delivery.

### Classification rules (finite closed-world toy SLA)

Define two **different** deadlines. `receipt_deadline` is the last time provider receipt qualifies under this contractual version. `fulfillment_deadline` is the last time the contracted result target must happen. Both are inclusive in this model.

- `N`: no qualifying physical receipt by `receipt_deadline`.
- `F`: there was qualifying physical receipt, but the chosen mode was not fulfilled by `fulfillment_deadline`.
- `S`: qualifying physical receipt and fulfillment of the chosen mode by `fulfillment_deadline`.

**N caveat:** this narrows the earlier v0 definition of N from "never physically received" to "not received by contractual acceptance cutoff." Late receipt can occur without changing N under the *provisional policy*. It is not yet approved, and it is distinct from the earlier *epistemic* "no verifiable receipt." ADR-001 is still OPEN. A final policy must settle whether the reservation fee still applies when the consumer sent a request late or the provider refused acceptance.

For HTTP challenge:
- `PROVIDER_RESULT`: valid `RESULT_PRODUCED` by deadline after timely receipt.
- `CONSUMER_DELIVERY`: valid produced artifact was also `RESULT_SENT` and `CONSUMER_RECEIVED` by deadline.

For deterministic compute, apply the same selected target **plus** `WORK_EXECUTED` for the same artifact between timely receipt and produced result. This is a *stipulated physical fact*, not an attestation available to monitors. A later service policy may instead contract for correct output only, explicitly allowing emulation. Do not claim this rule is enforceable now.

For storage, OCI and general API the classifier raises `UnsupportedService` rather than guessing that HTTP semantics apply.

### Structural validation vs real-world verification

The reference rejects impossible causal traces (receive before send, execute before receipt, consumer receives an artifact before provider sends it), type errors, events beyond the closed horizon, premature classification and unknown versions. It does not verify signatures, reconstruct clocks, run workloads or prove the asserted timeline is accurate. Its logical assumptions are *inputs* to the experiment.

## 5. Important counterexamples

**CE-04: Signed response but no consumer delivery.** If the provider signed a value at tick 3 but the consumer received nothing by tick 10, `CONSUMER_DELIVERY` is `F` even though a signature exists. A provider-generated contract might instead be satisfied if the correct artifact was generated before deadline. Different SLAs can legitimately assign different financial entitlements to the same physical execution.

**CE-05: Honest monitor timeout during network partition.** A provider produces and delivers a correct result (physical `S`) while the monitor is isolated (`connected=False`). The monitor reports timeout. A second history where the provider never responded (physical `F`) and the monitor was connected yields an identical monitor view. Hence the view cannot exclude `S` absent stronger assumptions.

**CE-06: Correct deterministic digest with unverified resource rental.** Provider can calculate the correct digest using an uncommitted environment. Observing the digest does not establish leased CPU/memory provisioning or uptime. A contract that rents *capacity* needs capacity evidence, not only result correctness.

**CE-07: Late receipt vs no receipt.** The chosen cutoff classifies a request physically received after the contractual acceptance deadline as `N`. Whether that warrants a reservation fee depends on actual contract wording. A late ACK or absent ACK alone cannot answer this question.

**CE-08: Incomplete physical timeline.** Before the fulfillment deadline and with no observed response, classification cannot safely become F. The code raises `IncompleteTrace` until the stipulated physical trace is closed through the deadline. Actual monitors cannot assume closed-world access without a justified trace-completeness/clock policy.

## 6. Interfaces to R1 WP-02 and production

WP-03 `classify(PhysicalTrace, ServiceConditions)` computes a **ground-truth candidate world in a simulator**. WP-02 `interpret(Observations, Assumptions)` computes **admissible candidate worlds from accepted evidence**. The scientific check is whether `classify(trace, terms)` stays a member of the set returned by the interpretation for **every allowed physical execution and observation projection**.

This comparison is not yet an executable cross-module property in the package; it is the next WP-04 integration task. Similarly, an on-chain EIP-712 vote does not certify the WP-03 physical trace. The current `SSESettlement.sol` history-bit filters remain unchanged.

## 7. Next gates and research questions

1. ADR-001: choose exact N/F/S meanings and receipt/fulfillment/deadline semantics for **HTTP challenge first**, with consumer/provider acceptance and reservation fee clarity.
2. ADR-002: specify monitor trust/fault model, network partitions and clock oracle model; determine whether any negative report can be soundly certified.
3. ADR-003: ensure early or irrevocable credits stay safe under evolving evidence and under lease-specific payout functions.
4. R4: agree canonical bytes and hash for service-specific SLA manifest, with EIP-712 cross-language vectors and actual verifiable certificates.
5. R7: define storage retention, OCI uptime and API correctness predicates; do not treat these as verified just because the code can parse their names.
6. WP-04: generate cross-product traces and network projections and compare their ground-truth worlds against WP-02 admissible sets and the contract's filtering behavior.
7. P2/P3: write conditional proofs and formal counterexamples; finite tests are not a formal proof or a hardware attestation.
