# WP-07 study and integration guide

This package contains a **non-production** scientific evidence-policy simulator. It does NOT modify Solidity settlement code.

## What to study in order

1. Read `R1_WP07_EVIDENCE_POLICY_SPEC.md`, especially the distinction between `PHYSICAL_DELIVERY` and `CHAIN_PUBLICATION`.
2. Read `Binding`, `PolicyManifest` and `TimeInterval` in `tools/sse_evidence_policy_v1.py`.
3. Trace `PhysicalPolicyState.with_raw`: how reports become audit records without altering the possible histories.
4. Trace `PhysicalPolicyState.with_fact`: how the assumed verifier/clock fact permits one monotone intersection; why contradictory claims raise exceptions.
5. Trace `ChainPolicyState.advance`: how a chain publication promise makes finality-conditioned success/failure mechanically verifiable **for that different promise**.
6. Read the tests for false certificates, all four timeouts, uncertain deadline, replay/mismatched SLA and conflicting canonical snapshots.
7. Run `tools/sse_wp07_demo.py` and interpret the seven JSON-lines examples.

## Git Bash host integration

Repository: `AkrAyoub/sse-research`. Branch: `research/r1-evidence-policy-wp07` (created remotely for this increment).

From the SSE Git Bash project root:

```
git status --short
git fetch origin
git switch research/r1-evidence-policy-wp07
```

Extract the WP-07 ZIP into the repository root, preserving the `tools/`, `tests/` and `docs/research/` directories. Review the changed filenames before staging. It contains no production Solidity changes.

```
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p 'test_sse_evidence_policy_v1.py' -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -v
./.venv-r0/Scripts/python.exe tools/sse_wp07_demo.py
forge build
forge test -vv
git status --short
```

The existing project previously reported 106 Python test cases, and WP-02 through WP-05 previously reported 120 research cases, but the isolated authoring tree discovered 118 older tests (one skip) plus 50 new. **Do not infer an exact full hosted total until your repository/CI runs.** The Foundry suite should still have the existing 52 named tests, since WP-07 changes no Solidity or Foundry source.

If all checks pass:

```
git add tools/sse_evidence_policy_v1.py tools/sse_wp07_demo.py
git add tests/test_sse_evidence_policy_v1.py
git add docs/research/
git diff --cached --stat
git commit -m 'R1: add versioned conditional evidence-policy research reference'
git push -u origin research/r1-evidence-policy-wp07
```

Open a **draft PR targeting `main`**, confirm Python Ubuntu, Python Windows and Foundry jobs pass, review and merge only the research artifacts. Do NOT claim this changes the on-chain evidence policy or verifies remote service fulfillment.
