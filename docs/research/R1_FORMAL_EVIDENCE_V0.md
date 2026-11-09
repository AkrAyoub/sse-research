# R1 — Provisional evidence semantics, world soundness, and settlement reference v0

**Status:** WORKING SCIENTIFIC SPECIFICATION, not approved contractual evidence policy. 2026-11-09.
**Artifact:** `tools/sse_formal_reference.py` + `tests/test_sse_formal_reference.py`.
**Relationship to existing implementation:** this is an independent *research oracle*, not a runtime replacement for `SSESettlement.sol`; no contract semantics or on-chain storage have been changed.

## 1. Motivation and definitions

The source implementation verifies EIP-712 provider acknowledgments (`submitAcknowledgment`), provider responses (`submitProviderResponse`), and selected-monitor votes (`submitMonitorVote`/`submitMonitorVoteDirect`). `sealMonitoring` assigns `Outcome.Success` for >=3 success votes, `Outcome.Failure` for >=3 failure votes, else `Outcome.None`. `settleEpoch` applies these observations to a three-bit set of histories. These are actual statements about **code transitions**, not proof that reports describe reality.

Let `W` be the possible *physical* histories of a single contractual epoch; let `h*` be the true physical history. Let `E` be an authenticated (and possibly incomplete) observation record, and let `I_A(E)` be an interpretation that depends on an explicit set of assumptions `A`. The indispensable financial-safety assumption is:

> `WORLD SOUNDNESS`: `h* in I_A(E)` for every admissible execution whose evidence is accepted by the policy.

The policy must also maintain `I_A(E) != empty`. Evidence alone does not prove the policy's assumptions.

### IMPORTANT: terminology reconciliation is still open

The existing reference describes `N` as **no verifiable provider receipt**. That is an epistemic state (a lack of proof), not necessarily a mutually exclusive physical event. For mathematically exclusive **physical** histories, this work package *provisionally* defines:

- `N`: provider did not actually receive the contractual request; provider entitlement `r` under a pre-agreed reservation-only fee rule.
- `F`: provider did actually receive the request, but did not satisfy the SLA's fulfillment predicate; provider entitlement `0`.
- `S`: provider received the request and satisfied the SLA's fulfillment predicate; provider entitlement `f`.

**ADR-001 unresolved:** the exact physical predicate `fulfilled` must be tied to each service SLA. It might mean response generated, authenticated response delivered to the consumer, response delivered before a measurable deadline, or actual compute/storage property; these are **not equivalent**. Likewise `N` cannot simply mean "no signed acknowledgment exists" if we want it to describe a physical history. This v0 interpretation is a candidate research refinement that needs review, not an approved alteration of the contract.

Under the illustrative SLA, `f=25`, `r=5`, `0 <= r <= f` and `V=f`:

```
Physical history   Request received?   Fulfilled?   Provider entitlement
N                  no                  no           r = 5
F                  yes                 no           0
S                  yes                 yes          f = 25
```

## 2. Observation schema and precise limitations

The v0 reference contains `Observations` with fields for `provider_signed_ack`, `provider_signed_response`, `no_response_observed`, `failure_votes`, `success_votes`, and hypothetical `certified_nonfulfillment`, `certified_fulfillment`.

**These fields mean that someone produced the corresponding bytes or statements, not that the physical state is established.** A signature establishes signer/key attribution and message binding under its cryptographic assumptions. It cannot certify send-to-receive delivery, truthful physical content, or an off-chain deadline. A local probe timeout may result from monitor isolation even when the provider fulfilled. A majority of signatures is not a proof of independent, physically truthful observations. A response hash is not evidence that the raw bytes remain available.

`certified_nonfulfillment` and `certified_fulfillment` are **formal placeholders** for a stronger independently validated certificate whose soundness remains an open R4 mechanism. Merely setting one of these booleans does not create a real proof. Never generate them from a vote quorum in production without a justified model, honest-fault assumptions, and a verification mechanism.

## 3. Versioned interpretation and trust assumptions

`Assumptions(version='R1-PROVISIONAL-0')` has three switches defaulting to `False`:

| Explicit assumption | Qualified observation | Excludes history | Why it cannot silently be enabled |
|---|---|---|---|
| `ack_proves_physical_receipt` | provider signed ACK | N | provider may sign without genuine delivery/receipt; what exactly is acknowledged? |
| `nonfulfillment_certificate_is_sound` | certified nonfulfillment | S | 3/4 timeouts or failure votes can occur during partitions even if S is true |
| `fulfillment_certificate_is_sound` | certified fulfillment | N, F | a signed response alone does not prove the negotiated fulfillment predicate |

If a switch is disabled, the corresponding observation **cannot exclude** a world.

```
I = {N, F, S}
if signed_ack AND honest-receipt assumption:    I = I intersection {F, S}
if failure_certificate AND soundness assumption: I = I intersection {N, F}
if success_certificate AND soundness assumption: I = I intersection {S}
if I is empty:                                   HALT (inconsistent evidence)
```

The policy does not treat `failure_votes=3`, a missing response, or `provider_signed_response=True` alone as conclusive. Under the all-False default, the admissible set stays `{N,F,S}` regardless of these inputs. This is **epistemically conservative**, but not a satisfactory practical service policy; useful conditional releases require independently defended additional assumptions.

## 4. Financial reference model and theorems

Let `A = I_A(E)` be nonempty, `e(h)` be entitlement in `[0,V]` and `V=f` for the restricted case. Define:

```
L = min(e(h) for h in A)              # guaranteed provider payment
U = max(e(h) for h in A)              # maximal provider entitlement
C = V - U                             # guaranteed consumer refund
X = U - L                             # unresolved funds / exposure
```

**Conservation**: `L + C + X = L + (V-U) + (U-L) = V` (algebraic identity).

**Conditional safety**: if `h* in A`, then `L <= e(h*) <= U`. Thus a provider credit of `L` is at most legitimate provider entitlement, and a consumer credit of `V-U` is at most `V-e(h*)`.

**Maximal guaranteed payment**: every provider payment safe across *all* histories in `A` must be <= the minimum entitlement `L`; similarly any consumer refund safe across all histories must be <= `V-U`. This establishes component-wise maximality **for a fixed admissible-history model**, not broader protocol optimality.

**Monotonic refinement**: if `A2` is a nonempty subset of `A1`, `min(A2) >= min(A1)`, `max(A2) <= max(A1)`, hence provider and consumer guaranteed payouts cannot decrease and `X(A2) <= X(A1)`. This is conditional on `h*` remaining in both sets. Reintroducing previously excluded histories can invalidate already released credits, so the progressive ledger rejects such a retraction.

**Budget safety by induction**: at admission, require `X_current + Delta_X_max <= B`. If the current sum is <= B and each new obligation adds no more than `Delta_X_max`, then immediately after admission the bound remains <= B. If admissible sets only refine monotonically thereafter, exposure can only decrease. A bad evidence interpretation can still violate economic correctness even if this numerical exposure limit holds.

For `f=25, r=5`, the expected histories and payments are:

| A | L | U | C | X |
|---|---:|---:|---:|---:|
| `{N,F,S}` | 0 | 25 | 0 | 25 |
| `{N,F}` | 0 | 5 | 20 | 5 |
| `{F,S}` | 0 | 25 | 0 | 25 |
| `{N,S}` | 5 | 25 | 0 | 20 |
| `{N}` | 5 | 5 | 20 | 0 |
| `{F}` | 0 | 0 | 25 | 0 |
| `{S}` | 25 | 25 | 0 | 0 |

`{N,S}` is included to test the **general mathematical model**, not to claim it is reachable through current `SSESettlement.sol` transitions.

## 5. Counterexamples: correct arithmetic over the wrong set

### Counterexample CE-01: partition and honest success

Physical history `h* = S`. The provider fulfilled the agreed SLA, but a network partition isolates three selected monitors. They each submit a validly signed failure observation. The current Solidity `sealMonitoring` makes `Outcome.Failure` once it receives three failure votes. `settleEpoch` then filters to `{N,F}` (assuming there is no signed acknowledgment). With `f=25,r=5`, it computes `C=20`, `X=5`.

But under the true `S` history the consumer entitlement is `25-25=0`: releasing 20 to the consumer is **unsafe**. The code can enforce its own vote-count policy without proving the physical-world assumption. Test `test_counterexample_unsound_failure_exclusion_overrefunds_consumer` isolates the formal failure mode; it is a **model counterexample**, not a demonstrated exploit on Ethereum or proof that the specified network partition always produces this outcome.

### Counterexample CE-02: signed acknowledgment without real receipt

A provider signs `ProviderAck` for a known lease/epoch digest even when the corresponding HTTP request did not actually reach its service. If the interpretation unconditionally treats a signature as evidence of physical receipt, it excludes `N`, although `h*=N`. This fails world soundness. A signature may still be useful evidence under a defined provider-honesty, key-handling, and protocol-meaning assumption; that must be stated, not inferred from ECDSA verification.

### Counterexample CE-03: contradictory hypothetical certificates

If both independently classified "certain failure" and "certain success" certificates are accepted under simultaneous soundness assumptions, applying both filters gives the empty set. `interpret()` raises `InconsistentEvidence`. It **does not** invent a winner or choose a payout. An actual dispute protocol must define how to quarantine, challenge, or treat inconsistent evidence; the sample implementation only fails closed.

## 6. Code map and validation contract

- `tools/sse_formal_reference.py`: stdlib-only `World`, `SLA`, `Observations`, `Assumptions`, `interpret`, `evaluate`, `world_sound`, `ProgressivePosition`, `admission_permitted`.
- `tests/test_sse_formal_reference.py`: 19 tests; exhaustive checks cover all seven nonempty subsets of `N/F/S`, all `1 <= f <= 15`, all `0 <= r <= f`, each true world in each set, every possible subset refinement, and 300 reproducible randomized integer examples. Specific negative tests cover false quorum inference, unsigned/no-response ambiguity, invalid parameter types, retraction, and inconsistent certificates.
- Run `python -m unittest discover -s tests -p 'test_sse_formal_reference.py' -v` in the repository. Tests validate *the reference code's mathematical properties for a finite restricted model*; they do not prove the physical evidence assumptions.

## 7. Code-to-research traceability and unresolved ADRs

| Source location | Behavioral fact from current source | R1 obligation |
|---|---|---|
| `SSESettlement.sol` `submitAcknowledgment` | signed ACK toggles `acknowledged` | ADR-001: physical semantics of the ACK, honesty/key compromise assumptions |
| `SSESettlement.sol` `submitProviderResponse` | EIP-712 response signature toggles `responseAuthenticated` | distinguish signed bytes from response delivery or successful execution |
| `SSESettlement.sol` `_recordAuthorizedVote` | selected monitor identity and one-vote-per-epoch; 3/4 counting later | ADR-002: monitor faults, correlated failures, and what a negative observation establishes |
| `SSESettlement.sol` `sealMonitoring` | >=3 votes decides success/failure, otherwise none | counterexamples for false definitive world exclusion |
| `SSESettlement.sol` `settleEpoch` | filters N/F/S then credits lower and `fee-upper` | independent finite oracle, world soundness needed for global financial safety |
| `SSESettlement.sol` `admitEpoch` | `currentExposure + epochFee <= exposureBudget` | ADR-003: show full-fee admission upper-bounds fresh uncertainty |
| `SSEBoundsPure.sol` `bounds` | bitmask arithmetic with f and r | differential comparison against the independent generic reference |

**ADR-001:** clarify event ontology and which party's receipt matters; reconcile reference's epistemic `N` with exclusive physical histories. **ADR-002:** define evidence-policy versions, fault assumptions and conditions under which any signed/quorum evidence excludes a history. **ADR-003:** formalize admission, irreversible allocation, no retraction and unresolved residual handling. **ADR-004 (later):** mapping between on-chain timestamps, externally observed clock values and user SLA deadlines.

## 8. Next proof/development gates

1. Review and approve physical contract semantics for HTTP/compute first, then storage/OCI. Separately specify all observation timestamps and message delivery predicates.
2. Define independent certificate validators and a concrete failure model that could justify *any* safe exclusion; design adversarial counterexamples for their assumptions.
3. Add a differential test against deployed or in-test `SSEBoundsPure.bounds` for **every valid history mask**, without copying Solidity bitmask logic into this reference evaluator.
4. Design independent physical trace generators (including delays/partitions, Byzantine monitors, and equivocation) and test `world_sound(h*, I(E))` across their traces; this is an empirical/model check only under generated scenarios.
5. Once assumptions are agreed, implement a *new* versioned policy boundary in the protocol rather than silently replacing the existing 3/4 quorum semantics.
6. For publication (P2), write formal statements with adversary and temporal assumptions, construct a mechanizable model, and distinguish proof from finite tests.
