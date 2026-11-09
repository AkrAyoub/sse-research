# R1 WP-03 — Service-specific conditions and evidence ontology

**2026-11-09 checkpoint.** A standard-library-only simulation model of service-specific physical traces, 26 local tests, and research documents have been created and packaged for delivery as `SSE_R1_WP03_Service_Conditions_and_Prior_Art_2026-11-09.zip`. **The source/test/doc files in that package have not yet been added to this remote branch.** No Solidity or live settlement behavior has been modified. Full Python suite and hosted CI for WP-03 are **not yet verified**.

## Research provenance

The provisional service taxonomy and architecture assignment (R1 physical semantics; R2 economics; R4 signed verification; R7 deployed workloads) were initially designed from SSE source inspection and general engineering reasoning, **not** copied from a completed systematic literature review. A subsequent focused primary-source check supports the need for service-specific objectives and measurement boundaries: ISO/IEC 19086-1 (https://www.iso.org/standard/67545.html), UNCITRAL cloud-contract SLA guidance (https://uncitral.un.org/en/cloud/sla), Akash SDL (https://akash.network/docs/developers/deployment/akash-sdl/syntax-reference/), Filecoin storage proofs (https://github.com/filecoin-project/filecoin-docs/blob/main/core-concepts/filecoin-virtual-machine/proofs.md), AWS S3 SLA (https://aws.amazon.com/s3/sla/) and academic AWESOME (https://doi.org/10.1186/s13677-022-00292-8). See the ZIP's `docs/research/P0_SERVICE_SLA_PRIOR_ART_WP03.md` for the precise claim-by-claim mapping, which is not yet merged into the repo.

## Model scope

The HTTP challenge and deterministic compute classifiers are **simulated ground-truth** functions with explicit receipt/fulfillment deadlines and generation-versus-delivery semantics. Storage, OCI and generic APIs are catalogued but explicitly *unsupported* by the current classifier, rather than silently inheriting incorrect rules. Signed statements and a monitor timeout are **observations**, not automatically trustworthy proof that the contracted physical event occurred. ADR-001 and ADR-002 remain open.

## Gates before this research increment is eligible for merge

1. Add the delivered files to this branch, run the new 26-test module and the full Python + Foundry regressions.
2. Push the commit, create a **draft PR** and verify GitHub Actions Python Ubuntu/Windows and Solidity jobs.
3. Review the physical-history ontology, service-specific SLA predicates, timestamp semantics and prior-work comparison. Merging research code does not make it an approved production payout policy.
4. WP-04 should compare a stipulated ground-truth classifier against evidence-derived admissible histories and seek counterexamples under network partitions and Byzantine reports.

**Provisional progress:** R1 35% (+10 pp), P0 25% (+5 pp), P1 30% (+10 pp), P3 20% (+5 pp); engineering about 19%, research about 13%, overall about 17%. These count authored/locally tested models and focused research, not hosted or production acceptance.
