# R1 WP-04 — Observation equivalence, evidence soundness, and financial impact

**Date:** 2026-11-09. **Scientific status:** PROVISIONAL RESEARCH MODEL. This is not an approved on-chain evidence policy, cryptographic verifier, clock oracle, network monitor, remote resource attestation, or formal proof about arbitrary networks.

## 1. Research question and assumptions

**Question:** if a contractual event happens in the physical world, which alternative histories remain indistinguishable to the monitors under the permitted faults and evidence types? Can a policy release money safely when two histories give the monitors the same observation?

### Four different entities

- A **physical execution** `x` contains an explicit trace of what actually happened and a simulated network topology.
- The **service conditions** `T` stipulate the contractual fulfillment predicate; WP-03 supports `HTTP_CHALLENGE` and `DETERMINISTIC_COMPUTE` only, and distinguishes generating a correct result from consumer delivery. Timelines are logical ticks.
- An **observation** `o = π(x)` is a bundle of per-monitor views and an optional unverified client claim. WP-03's monitor projector reports only timeouts, seen result transmissions, seen ACK signatures and seen response signatures; it does **not** prove their physical meanings. The `connected` flag is a static toy topology, not a link-delay distribution.
- The **entitlement** function `e_T(h)` assigns money to physical history `h`. The existing restricted WP-02 model maps `N` to `r`, `F` to 0, `S` to `f`, with `V=f` and `0 <= r <= f`.

### Observable history set

Let `Ω` be an **explicitly enumerated** possible-execution universe. Two executions are observationally equivalent if they produce the same monitor report bundle:

```
x ~ y  <=>  π(x) = π(y)
A_Ω(o) = { world_T(x) | x ∈ Ω and π(x) = o }
L(o) = min { e_T(h) : h ∈ A_Ω(o) }
U(o) = max { e_T(h) : h ∈ A_Ω(o) }
ProviderCredit = L; ConsumerCredit = V - U; Held = U - L
```

This is *relative* soundness: if the actual physical execution `x*` **belongs to Ω** and produced observation `o`, then `world_T(x*) ∈ A_Ω(o)`. The proof is set membership, **not proof that Ω covers the actual network**. An incomplete universe may omit the true execution and authorize an unsafe payment. `test_missing_possible_execution_can_falsify_global_safety` makes this failure explicit.

### The indistinguishability limitation

Suppose two physically possible executions `x_F`, `x_S` have the *same* observation but different provider entitlements `e(F)=0` and `e(S)=25`. Any deterministic settlement algorithm that sees only this observation must output the **same** release for both histories. A provider release greater than zero is unsafe under F; a consumer refund greater than zero is unsafe under S. Therefore, unless the algorithm assumes extra trusted information or accepts an economic risk, it must hold all 25 in this example. This is a consequence of the pair of indistinguishable histories; no cryptographic complexity or blockchain count removes the ambiguity by itself.

## 2. The scenarios our simulator produced

All monetary values are illustrative wei: `V=f=25`, reservation `r=5`. `N` means **no qualifying provider receipt by the contract receipt cutoff** in the WP-03 model (not necessarily never received, and not merely 'not verifiably received'). `F` means timely receipt but contractual nonfulfillment. `S` means timely receipt and contractual fulfillment.

| Case | Simulated physical truth | Per-monitor projection | Compatible histories given selected universe | Financially safe allocation (provider, consumer, retained) |
|---|---|---|---|---|
| All four monitors partitioned | `S` (also `N`, `F` alternatives) | 4 timeouts | `{N,F,S}` | `(0,0,25)` |
| Three monitor partitions and one sees a transmission | `S` or `F` (result not delivered) | 3 timeouts + 1 observed transmission | `{F,S}` | `(0,0,25)` |
| All four see a transmission | `F` (correct result generated but consumer never receives) or `S` | 4 observed transmissions | `{F,S}` | `(0,0,25)` |
| A signed ACK is visible | `N` with ACK claim or `F` with ACK | signed ACK seen; no result | `{N,F}` *only in the deliberately limited universe* | `(0,20,5)` |

**Do not reinterpret the fourth row as authorization to refund 20 solely from an ACK!** A possible `S` execution with the same visible claim, especially with different network settings, may be absent from the illustrative universe. The existence of such omitted executions is a research warning, not an implementation detail.

### Unsafe-rule controls

The comparison module contains two functions whose names deliberately start with `unsafe_`:

- `unsafe_quorum_rule(view, quorum=3)` models the unsupported inference "3 timeout reports => no physical success", or "3 observed transmissions => success". It omits actual Solidity authorization, authentication, timing and storage guards and **must not be equated with a deployed exploit**.
- `unsafe_receipt_rule(view, trust_client_claim=True)` models treating a client-side completion claim as proof of successful delivery. This becomes sound only if the complete SLA predicate follows from a correctly verified, truthful, accurately timed, domain/lease/artifact-bound statement. A dishonest or compromised signer can falsify that assumption. Merely checking ECDSA is not enough.

`excess_credits()` uses *simulated omniscient ground truth* to show how much an overconfident allocation exceeds actual entitlements. A production monitor **cannot call this function to learn physical truth**.

## 3. The code and tests — exact responsibility

`tools/sse_observability_reference.py`:

- `Execution`: immutable stipulated physical trace + per-monitor connectivity + finite observation cutoff + potentially dishonest client claim.
- `Observation`: per-monitor `MonitorView` tuple, raw client completion claim flag, derived positive/negative counts. The source WP-03 projection sees `RESULT_SENT` but cannot establish correctness, fulfillment, or consumer delivery.
- `observation_equivalence_class()`: find every enumerated execution with identical observed projection; map them to `N/F/S` via the WP-03 *ground-truth classifier*; compute WP-02 financial bounds over the result.
- `finite_universe_sound()`: exhaustively checks inclusion **inside the given finite universe**. The procedure is not a formal proof of the physical assumption or network model coverage.
- `unsafe_quorum_rule()`, `unsafe_receipt_rule()`: *intentionally overconfident* baselines for counterexample tests; do not expose as settlement oracles.
- `excess_credits()`: compare hypothetical payouts to stipulated physical truth; a research diagnostic only.
- `projection_to_provisional_claims()`: maps the toy observation tuple to the WP-02 raw `Observations` schema. Its signing flags are **not cryptographically verified**, so this is only test integration and never a production adapter. WP-02's conservative all-False default does not exclude histories from these fields.

`tools/sse_wp04_demo.py` prints three examples that expose the true world, monitor reports, cautious allocation and over-credit caused by a naive rule. It is a teaching tool, not a runtime agent.

`tests/test_sse_observability_reference.py`: 30 new `unittest` cases, including N/F/S observation equivalence, delivered versus undelivered data, compute execution versus digest, correlated honest monitor failures, dishonest receipt claims, the risks of excluding unenumerated worlds, and invalid-clock/topology cases. WP-02 and WP-03 tests were combined in the local authoring tree; **75 tests passed** (19+26+30). Full production repository tests and GitHub Actions **have not yet run on the new WP-04 source**.

## 4. Recommended implementation decisions

### Near term — implement and test (R1, R2, R4)

1. **Versioned SLA manifest** with `serviceKind`, `fulfillmentMode`, specific verification predicate, `resourceProfileHash`, endpoint binding, receipt/fulfillment deadlines, measurement interval, fee/reservation, finality/clock assumptions, allowed fault model, and a public `evidencePolicyVersion`. Canonicalize and commit bytes by hash before economic obligations activate. The hash alone does not enforce the terms; the verifier must know and validate the preimage and version.
2. **Service-specific observation adapters** emit only typed, authenticated claims: `provider_signed_response`, `monitor_observed_valid_bytes`, `consumer_claimed_receipt`, `proof_verified`, `timeout_from_monitor`. Separate a raw observation from a sound certificate with a documented verifier and trust model.
3. **Three-way evidence state** of `established`, `refuted`, and `unknown` for a contractual predicate under stated assumptions. A network timeout normally maps to `unknown`, not `refuted`. Do not claim this three-valued logic is novel; it follows established runtime-verification research.
4. **Reference-model differential and adversarial testing**: for each generated physical world and network projection, assert that any accepted history interpreter retains the ground-truth world under the declared assumptions. Failure means an unsound exclusion, not a rounding error in the financial formula.
5. **Evidence/version gating in settlement**: no new on-chain financial release policy until ADR-001 and ADR-002 are reviewed. Existing v1 quorum inference must be described accurately as a *policy-assumption-based classification*, not a guaranteed proof of physical service failure.

### Conditional research integrations — adapt with caution

- **TLS provenance notaries** such as DECO or TLSNotary may prove origin of *some* HTTP bytes to a third-party verifier. They do not automatically verify the SLA semantics, consumer receipt time, or CPU availability. R4 integration may be worthwhile if its performance and threat model fit.
- **Verifiable computation** (e.g. zkVM receipt) can prove execution of specified code/output under a sound proof system; resource reservation and actual network delivery remain separate.
- **Persistent-storage proofs** (e.g. Filecoin PoRep/PoSt) illustrate temporal proof systems. Reimplementing a secure production PoSt scheme from scratch is out of R1 scope; R7 could use an existing verifier or a clearly limited periodic proof-of-retrievability experiment.
- **Hardware/TEE attestations** may bind software/configuration to attested hardware, under vendor and platform assumptions. Startup attestation does not guarantee arbitrary ongoing QoS or consumer-side delivery.

### Do NOT assert/automate without changed assumptions

- An arbitrary 3/4 timeout quorum establishes physical nonfulfillment in an asynchronous/partitionable network.
- A provider-signed ACK proves the HTTP service received a request at a trustworthy physical time.
- A hash response proves CPU/memory reservation; `docker inspect` on the provider machine proves independent remote execution.
- A notarized TLS transcript proves an application's business-level correctness or externally measured deadline.
- A single storage GET or digest proves retention throughout a long lease.
- All unresolved escrow can automatically be refunded to a consumer after a timeout **while simultaneously preserving financial safety for a possibly successful provider**. A dispute/liveness mechanism must specify who bears this risk (bilateral release, arbitration, collateral, bounded retention, or other explicit assumption).

## 5. Prior-work provenance and novelty boundaries

See `P0_WP04_EVIDENCE_MECHANISMS_AND_GAPS.md` for source-level citations. Short version:

- **Not new:** QoS resource manifests, SLA objectives, monitoring quorums/oracle networks, sound three-valued incomplete-observation semantics, failure-detector accuracy/completeness, cryptographic provenance of some TLS data, storage proofs, or zero-knowledge proofs of computation.
- **Candidate research contribution:** combine a service-specific, assumption-explicit evidence interpreter with *component-wise maximal guaranteed* provider/refund credits, unresolved-exposure accounting and safe admission/continuation. Need a complete closest-work and fair-exchange/partial-payment comparison before claiming novelty.
- **Potential negative result worth publishing:** show an observational equivalence class of physical histories with different economic entitlements; prove no observation-only classifier can safely allocate beyond common guaranteed bounds absent extra assumptions. The mathematical idea is elementary; originality depends on precise formalization and relation to prior literature.

## 6. Next acceptance work

1. Get WP-03 and WP-04 reference modules into a research Git branch, run full Python/Foundry suite and hosted CI. No production contract changes in this package.
2. Build a richer **eventual asynchronous message** model rather than a static `connected` bool; inject correlated partitions, reordering, clock drift, byzantine signatures, and transaction censorship.
3. Define the exact **HTTP signed/consumer receipt** schema and whether fulfillment is generation, delivery, or observed response, together with a trustworthy deadline model. Add the matching v2 policy verifier only after approval.
4. Differential-test the **actual `SSESettlement.sol` history filtering and `SSEBoundsPure`** against the independent reference across all seven masks; test failures for possible economically unsafe exclusions under modeled faults. The current `unsafe_*` functions are not contract-equivalent.
5. For each service kind, define separate contractual and measurement profiles: compute **correct output vs resource lease**, storage **retrievability vs ongoing persistence**, OCI **resource availability vs isolation**, API **valid response vs availability/latency**.

**Safety finding:** correct min/max settlement arithmetic cannot compensate for an unsound evidence-to-world interpretation. Economic conservatism is conditional on retaining the true contractual history.

### Related dispute-resolution alternative (R2 design option)

Optimistic fair-exchange protocols already use an exceptional-case arbiter or trusted third party to obtain fair termination when normal exchange breaks down. This is relevant to SSE's **liveness versus safety** tension: holding all unresolved funds may be safe but economically unacceptable. A later R2 option is explicitly invoked, auditable third-party arbitration, potentially with challenge windows, collateral and bounded retention. Such a policy must state the arbitral trust assumptions and cannot claim fully trustless settlement. See the new Asokan/Shoup/Waidner sources recorded in the P0 document.
