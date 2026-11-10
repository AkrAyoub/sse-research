# R1 WP-07 — Versioned evidence interpretation policy, draft 1

**Status:** SOURCE-PRESENT, PYTHON-MODEL-TESTED, SCIENTIFIC PROTOTYPE. NOT A PRODUCTION MONEY-RELEASING POLICY. 

**Scope:** HTTP delivery and an intentionally **different** on-chain publication service. This does not alter `SSESettlement.sol` or any other Solidity file.

**Research purpose:** Identify the *minimum truthful meaning* of each authenticated observation before it may reduce the set of contractual histories. Distinguish logical correctness from unverifiable assumptions about external reality.

## 1. Starting point: exact current SSE contract semantics

The deployed-source `SSESettlement.sol` supports provider-signed ACK and response; selected monitor signed Success/Failure votes; Success if at least 3 success reports; Failure if at least 3 failure reports; otherwise None. `settleEpoch` starts with `N|F|S` and intersects with `{F,S}` on ACK, `{S}` on Success, `{N,F}` on Failure. It credits `min(entitlement)` to provider, `fee-max(entitlement)` to consumer, and retains the gap. Real-EVM WP-06 tests demonstrate consequences of the existing rules with 17 Foundry tests. **The code authenticates votes; it does not verify the off-chain meaning of a monitor timeout.**

## 2. Service semantics must be declared before settlement

This WP contains two explicitly different contractual modes:

1. `PHYSICAL_DELIVERY`: the physical N/F/S model from WP-02/WP-03. N means the provider **did not physically receive** the request and receives the contractual reservation `r`; F means provider received request but not the *complete contracted fulfillment predicate*; S means provider received request and fulfilled, which **for this prototype includes correct delivery to the consumer by deadline**. N's physical-receipt interpretation is provisional, not identical to the original system's epistemic "no verifiable receipt". ADR-001 remains open.
2. `CHAIN_PUBLICATION`: success means the canonical chain contains a correct, epoch-bound response by the stipulated *chain* deadline. Failure means no such included event by deadline on an assumed complete and finalized canonical chain. The contractual outcome space is **{F,S} only**, not the historical N/F/S reservation scheme. This is NOT a replacement for rented CPU, storage, guaranteed remote delivery, or a typical cloud SLA. It would require separate SLA terms and new production implementation.

A marketplace must never offer the on-chain publication mode under a description claiming physical compute, storage durability, or consumer-side network performance.

## 3. Actors and trust boundaries

- Consumer: defines or agrees to a lease and sends service requests. Can report experience but can lie when money is at stake.
- Provider: may sign an ACK and a response. Authenticates an assertion under key integrity; does not mechanically prove truthful receipt or delivery.
- Monitor: reports locally observed event/timeout. Honest monitor = truthful reporting of its *local view*, not perfect world knowledge. Four such monitors can all be isolated from a successful provider.
- Evidence qualifier (NOT IMPLEMENTED): must independently verify an appropriate certificate and its semantics, scope, time interval, replay protection and uncertainty before producing a `QualifiedFact`. The Python caller can instantiate this class arbitrarily, so **qualification is a test-only assumption**, not an enforceable security boundary.
- Blockchain: determines what transactions appear in the canonical sequence and chain timestamps; does not observe off-chain service execution. Chain reorganization/finality/censorship and RPC completeness must be in the threat model.

## 4. A concrete versioned, bound policy manifest

`PolicyManifest(binding, mode, admission_time, deadline, assumptions, version)` stores `Binding(lease_id, epoch_id, sla_hash)` and requires `version == R1-EVIDENCE-POLICY-DRAFT-1`. We require canonical lowercase `0x` + 64 hex SLA commitments and reject a mismatched binding, e.g. a certificate for epoch 3 cannot justify a payout for epoch 2.

**Important**: This prototype treats `sla_hash` as a provided commitment; it does **not** compute or authenticate the Keccak commitment, canonical service manifest, EIP-712 signature, finality, or physical event. R4 must supply those mechanisms.

`RawObservation` is a signed/claimed ACK, response, monitoring success/timeout or consumer assertion. Raw observations are retained for audit and **never** automatically narrow history sets.

`QualifiedFact` is a *hypothetical* verified claim for the exact lease/epoch/SLA. It declares its required trust assumption and a verifier reference. A test may construct an invalid one; this is why we must never import the prototype into production transfer code.

## 5. Physical delivery inference table

| Evidence | Assumption | Allowed worlds after intersection | Reason |
|---|---|---|---|
| None, 0-4 monitor timeouts, 0-4 positive reports, ACK or signed response | No additional world truth guarantee | `{N,F,S}` | Signed statements and timeouts do not establish contracted fulfillment or failure |
| Externally qualified physical receipt | `RECEIPT_CERT_SOUND` | `{F,S}` | Only if the assumed validator cannot falsely assert receipt |
| Externally qualified full contractual nonfulfillment after deadline | `NONFULFILLMENT_CERT_SOUND` | `{N,F}` | Must exclude S for **all** admitted network histories, not merely demonstrate a failed probe |
| Externally qualified correct consumer delivery with certainly timely timestamp interval | `FULFILLMENT_CERT_SOUND` | `{S}` | Requires complete fulfillment + credible time bound, not merely signed output |
| Qualified correct delivery, but time interval straddles deadline | Even if same certificate kind | `{N,F,S}` | Cannot establish timely contractual fulfillment |
| Two qualified facts yield empty set | Regardless | **HALT** | Do not arbitrarily choose a winner or release money |

For `V=25,r=5` all worlds imply `(provider=0,consumer=0,unresolved=25)`; `{N,F}` implies `(0,20,5)`; `{F}` implies `(0,25,0)`; `{S}` implies `(25,0,0)`. These are *conditional* on actual history remaining in the set.

If an event-clock reading is `[t_min,t_max]` and the deadline is `D`, prove timely only if `t_max <= D`. If `t_min <= D < t_max`, remain unknown. A report of a *late* completion alone does NOT prove no earlier valid completion; a full nonfulfillment certificate needs stronger exhaustive coverage.

## 6. Monotonicity and contradictions

Let `A_0 = {N,F,S}`. Every valid certificate yields `A_(i+1) = A_i ∩ Restriction(c_i)`. Therefore `A_(i+1) ⊆ A_i`. For a fixed entitlement function, guaranteed provider payment `min F(A)` cannot decrease, guaranteed consumer refund `V-max F(A)` cannot decrease, and unresolved `max F(A)-min F(A)` cannot increase. This is a conditional mathematical fact.

The code accepts an ID replay only if it is byte-for-byte identical; reusing the same ID for a different report is rejected. The state is immutable: if qualification would produce the empty set, an exception is raised and the old state remains unchanged. It does **not** resolve the underlying evidence conflict.

**Necessary world-soundness condition**: the actual physical history `h*` must be in the starting set and every applied restriction. If the `NONFULFILLMENT_CERT_SOUND` assumption is false in an actual successful history S, the model still credits the consumer 20, and world soundness is violated. This is intentionally tested and demonstrated.

## 7. Separate on-chain-publication experiment

The alternative `CHAIN_PUBLICATION` mode starts with **{F,S}** because the purchased obligation is *specifically chain publication of a challenge response*, not physical request receipt or reservation. Its rule is:

- On an **assumed verified** canonical snapshot, if a correct response was included at a block timestamp <= deadline and the inclusion is finalized, refine to S.
- On an **assumed complete, finalized** chain view through the deadline, if no correct response is included by that deadline, refine to F.
- Before finality, retain `{F,S}`; if snapshots contradict an irrevocable previous decision, halt rather than reverse payouts.

This is a cleaner objective obligation but not a realistic proof of cloud resource rental. It is an **illustrative separate product**, not a semantics-preserving patch to existing N/F/S leases. On-chain censorship, gas spikes, private transaction visibility, finality and oracle truth assumptions still matter, even if the contract is defined purely in chain terms.

## 8. Threat model and exclusions

**Modeled in test:** dishonest provider/consumer assertions, 4/4 correlated monitor timeouts, contradictory qualified facts, cross-lease/epoch/SLA replay, ID duplication, chain-finality regression, mutable chain snapshots, clock uncertainty at deadline, missing or false certificate, adversarial candidate-history choices, conservation.

**Not modeled/implemented:** cryptographic signature verification for newly qualified facts, verifiable cloud delivery, TLS session proof, hardware attestation, decentralized trustless adjudicator, Byzantine-safe clock oracle, storage duration proofs, CPU/RAM reservation proofs, consensus finality verifier, cross-chain replay, network-level Sybil resistance, real telemetry security, real EVM execution of WP-07, R2 escrow-integration upgrade, security audit.

## 9. Implementation roadmap

1. **R1/P1:** approve physical receipt/fulfillment ontology and service-specific predicates (ADR-001); specify formal complete universe and the exact admissibility lemma for each qualification rule (ADR-002).
2. **R4:** canonical `ServiceManifestV1` and `EvidenceRecordV1` wire schemas, actual Keccak/EIP-712 signatures, replay/chain/contract/lease/epoch binding, source timestamps as intervals and evidence archives. Keep verifier registry separate from arbitrary reporter assertions.
3. **R2:** introduce a *new* policy version/registry or dedicated `SSEEvidencePolicyV1` contract subject to independent security and economic audit. Do not silently change the interpretation of funded old leases. Fail closed for unsupported certificates; integrate with existing min/max bounds and residual settlement.
4. **R7:** real HTTP/compute/storage/OCI/API policies only after separately chosen, measurable contractual predicates are specified. A correct compute digest is NOT proof of CPU rental.
5. **P2/P4/R9:** mechanizable proof obligations plus multihost partition, Byzantine and clock-uncertainty experiments. Compare conservative and conditional policies under explicit fairness and liveness metrics.
6. **P0:** systematic comparison against distributed runtime verification, fair exchange, SLA witnesses, storage proofs and on-chain settlement; novelty is not established by this prototype.

## 10. Primary-source grounding (not novelty claims)

- Basin, Klaedtke, Zălinescu, *Failure-aware Runtime Verification of Distributed Systems*, FSTTCS 2015: https://doi.org/10.4230/LIPIcs.FSTTCS.2015.590. Three-valued truth under incomplete/out-of-order messages is established work.
- Chandra & Toueg, *Unreliable Failure Detectors for Reliable Distributed Systems*, JACM 1996: https://www.cs.cornell.edu/info/people/sam/FDpapers.html. Timeout suspicion need not be accurate.
- EIP-712: https://eips.ethereum.org/EIPS/eip-712. Typed-data signing is about structured, domain-separated signatures; EIP-712 does **not** itself supply replay protection or off-chain factual truth.
- Asokan, Shoup, Waidner, *Asynchronous Protocols for Optimistic Fair Exchange*, IEEE S&P 1998: https://research.ibm.com/publications/asynchronous-protocols-for-optimistic-fair-exchange. Trusted third-party exceptional completion is relevant prior art to escrow residual liveness.

**Scientific status:** the proof-level safety theorem is conditional on sound qualifications and accurate contractual semantics. Tests give finite executable witnesses, not an unconditional proof of the universe.
