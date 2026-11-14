# WP-09I — offline VRF coordinator policy and research package

## Short version

- A **verified-VRF coordinator adapter design**, not a self-verified VRF, threshold-VRF implementation, or deployed contract.
- Local Python **state-machine tests**; no EVM node, chain RPC, GitHub Actions or money spent.
- A manually reviewable, **uncompiled Chainlink VRF v2.5 integration draft** requiring settlement hook, correct package/network settings and local Foundry tests.
- One attempt per lease: timeout/refund and **no automatic reroll or blockhash fallback**.
- Immutable per-request coordinator/keyHash provenance; authenticated source, scoped request ID and late-callback handling; explicit migration risk.

## Run locally

```
cd WP09I_offline
python -m unittest -v test_wp09i.py
python wp09i_reroll_experiments.py
```

The test suite uses only Python standard library and the bundled Keccak implementation (already independently exercised in preceding offline packages). `wp09g_recovery.py` is bundled read-only for integration tests.

## Files

- `wp09i_vrf_policy.py` — executable offline lifecycle/reference model
- `test_wp09i.py` — local tests and WP09G integration
- `wp09i_reroll_experiments.py` — exact analytical grinding comparison
- `reroll_attack_metrics.csv`, `experiment_results.json` — results
- `WP09I_VRFV25_ADAPTER_DRAFT.sol` — uncompiled future EVM integration sketch
- `WP09I_FINDINGS.md` — security boundary, architecture, threat model, next steps
- `wp09g_recovery.py`, `keccak.py` — bundled local reference dependencies
- `test_results.txt` — local test output

**No repository modifications were made.** GitHub Actions remain prohibited for this project. Disable Actions in repository settings before any future pushes, or keep all work local as done here.
