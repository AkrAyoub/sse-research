# Milestone III implementation alignment

This is a **research demonstrator**, not a production intercloud marketplace. The supported scientific mechanism is fixed N/F/S conservative financial settlement with authenticated EIP-712 role messages and exposure-aware epoch admission.

## Changes from the uploaded SSE.zip

- Clarified protocol contract NatSpec: 3-of-4 is a **demo evidence policy**, not a permissionless blockchain consensus rule, not an SSE requirement; randomness seed is trusted.
- Corrected `OpenResourceBoard.sol` documentation (it now has atomic funded-lease creation).
- Added seven Foundry tests in `foundry/test/Milestone3Protocol.t.sol` for role boundaries, quorum behavior, settlement progression and exposure admission.
- Added a read-only evidence auditor `tools/m3_evidence_audit.py` with nine Python regression tests. This validates saved evidence hashes and optionally their on-chain inclusion; **not** evidence truth or independent monitor control.
- Added milestone-specific architecture, threat model, state/role explanation, workflow, pseudocode and official requirements checklist under `docs/`.
- Improved `.gitignore` for local experimental artifacts and Windows environments.

**No behavioral change to the deployed Solidity protocol, on-chain storage layout, public function signatures, fee math, or existing monitor selection.** Solidity must be rerun with Foundry locally; the current preexisting Anvil deployment does not need redeployment because only comments and tests changed.

## Run acceptance tests

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
forge build
forge test -vv
```

Count expected from source: **91 Python test methods, 24 Solidity test functions** (17 original + 7 new). Forge fuzz cases/runs are not additional independent test functions.

## Audit real saved evidence (read-only)

```bash
python tools/m3_evidence_audit.py --run .local/sse-e2e-runs/lease-3/run.json
python tools/m3_evidence_audit.py --run .local/sse-e2e-runs/lease-3/run.json --rpc-url http://127.0.0.1:8545
```

The second command also needs the same live Anvil chain and contract deployment. Restarts may reset state. `offlineCommitmentsVerified` does not mean `onChainCommitmentsVerified` or `truthOrIndependenceProven`.

## Milestone article and submission

Use `docs/MILESTONE3_SYSTEM_DESIGN.md` to write the required system design and implementation subsections; combine with the existing revised Milestone II introduction/literature review. Fit **6 pages maximum**. Include a current implementation architecture figure, workflow sequence diagram and contract pseudocode. Describe Anvil and permissionless participation accurately. Add AI disclosure immediately before References, highlight AI-generated portions, and disclose AI-generated figures.

The `scripts/package_milestone3.py` command checks that the final PDF is at most 6 pages and contains an AI Usage Disclaimer before References, then packages **only** the PDF and `.sol` files. It cannot verify whether AI-generated text is highlighted or figure disclosure is truthful; check those manually.

When the final paper PDF has been revised, highlighted, and checked:

```bash
python scripts/package_milestone3.py --pdf path/to/Final_Milestone3.pdf --out Milestone_III_Submission.zip
```

The packager checks the PDF is 1–6 pages and contains a textual AI Usage Disclaimer before the References section. It **does not** automatically determine which passages were AI-generated or confirm that highlights/figures disclose all assistance; the author must verify these manually.
