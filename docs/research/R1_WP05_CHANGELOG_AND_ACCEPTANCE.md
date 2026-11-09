# R1 WP-05 changelog and evidence-backed acceptance state

**Date:** 2026-11-09
**WP focus:** asynchronous probe delays and partitions, honest vs Byzantine reports, off-chain/chain deadline differences, and source-traced existing-contract transition rules.

## New source

| Path | Contents | What it deliberately does not do |
|---|---|---|
| `tools/sse_async_contract_reference.py` | Four-monitor epoch state, exact observed chain-time gate predicates, EIP-712 authenticated-result placeholders, quorum, contract filters, delta-only financial credits, latency and clock intervals | Does not execute EVM or verify ECDSA/signature bytes; does not prove physical service truth |
| `tests/test_sse_async_contract_reference.py` | 45 tests covering boundary equality, voting auth, duplicate vote, quarantine, quorum, deltas, honest delayed probes, byzantine claim, time ambiguity, source-literal drift checks | Not an on-chain differential test; source guards are simple literal checks |
| `tools/sse_wp05_demo.py` | JSONL output with four conditional financial-unsoundness counterexamples and one uncertain-time illustration | Not a live cloud or blockchain exploit |
| `docs/research/R1_WP05_ASYNCHRONY_CLOCK_BYZANTINE_CONTRACT_MAP.md` | Low-level contract mapping, source-derived controls, evidence counterexamples, primary literature and design decisions | Does not approve service ontology or policy for deployment |

## Execution evidence

From the isolated WP-05 model tree with Python 3.13, using the unchanged `SSESettlement.sol` source from the original project archive for the two *source-literal* regression tests:

- `python -m unittest discover -s tests -p test_sse_async_contract_reference.py -v` => **45 tests passed, no failures**.
- Copied WP-02/03/04 model+tests into the isolated environment (19+26+30), then `python -m unittest discover -s tests -v` => **120 tests passed (0 errors, 0 failures)**.
- `python tools/sse_wp05_demo.py` => five JSONL records, generated and archived.

## What remains unverified

- Running the **full existing project** Python suite on this new work package, expected **226** cases if discoverable.
- Foundry compilation/tests on the updated checkout, previous R0/04 count 35.
- Hosted GitHub Actions on the new branch.
- **Foundry EVM-equivalent differential tests for the actual contract**; source-literal guards cannot replace bytecode invocation.
- Real cryptographic signature checks for the model, real asynchronous multi-VM deployment, trusted clock attestation, exhaustive security proofs or novel paper claim.

## Provisional progress increments

| Phase | Previous | New | Delta |
|---|---:|---:|---:|
| R1 | 43% | 50% | +7 pp |
| P0 | 32% | 35% | +3 pp |
| P1 | 40% | 46% | +6 pp |
| P2 | 15% | 20% | +5 pp |
| P3 | 25% | 30% | +5 pp |
| P4 | 10% | 12% | +2 pp |

All others unchanged, notably **R2 security-hardening remains 20%**; the source was not modified. Equal-phase arithmetic averages now: engineering 20%, research 20%, overall 20%. New evidence is *local model-only* pending host and hosted CI acceptance.
