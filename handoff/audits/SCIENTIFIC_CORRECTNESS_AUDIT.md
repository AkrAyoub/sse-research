# Scientific correctness audit — 2026-11-27 (static)

Reference model: handoff/REQUIREMENTS.md "Scientific invariants", proposal and Milestone 3 extracts (handoff/references/).
Report2.pdf / Report3.pdf are present but untracked and were not parsed in this session (owner may commit them).

| Invariant | Where implemented | V4 status |
|---|---|---|
| N/F/S histories, masks 1/2/4 | SSEHistoryPolicy, SSEEntitlementBounds (unchanged, V3-tested) | Reused verbatim |
| P = L = min admissible entitlement; C = V − U; X = U − L | SSEEntitlementBounds.calculate | Reused |
| Conservation P + C + X = V | SSEExposureAccounting.conserved | Reused; market totals statically argued |
| Monotone refinement, no reversal / double credit | Bounds.refine requires next ⊆ prior; market `_refine` early-returns after closure/allocation | Statically reviewed |
| Exposure-aware admission X + fee ≤ budget | Accounting.admit → Bounds.reserve | Reused |
| Evidence closure then bilateral residual consent (consent ≠ proof) | closeEpochEvidence, resolveResidual | Reused; mask preserved |
| Quorum is evidence only under explicit conditionalQuorumPolicy | market `_refine` | Reused |
| Missing response / timeout ≠ violation | Failure votes need quorum + explicit policy; None outcome keeps mask 7 | Test `testMissingResponseIsNotProofOfViolation` (unexecuted) |
| Signed response authenticates origin, not SLA correctness | authenticateProviderResponse | Unchanged meaning |
| Receipt admission only under explicit policy | NEW `responseAdmitsReceipt` term (V4 only) | Addresses E8 epoch-2 observation (mask7 instead of 6) without changing V3 |
| Native consensus distinct from monitors | No consensus code touched | — |

Open scientific items: E7 (qualified negative with real controlled defect), E9 (scaling), E10 (independent deployment) remain
**Not executed**; qualified-negative evidence still relies on conditional quorum; a stronger, independently verifiable negative
evidence format (e.g., signed wrong output against a deterministic reference) is designed only in prose (see DESIGN_DECISIONS D-07).
