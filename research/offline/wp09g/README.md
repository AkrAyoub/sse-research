# WP-09G local-only handoff

**Nothing in this directory triggers GitHub Actions, performs `git push`, or makes network requests.** This is an offline research prototype and a **not-yet-compiled** Solidity patch candidate for the project's stacked WP09E draft. The user must disable GitHub Actions before any future repo push to avoid surprise billing.

## Run (Python only; no dependencies)

```bash
python -m unittest discover -s . -p 'test_*.py' -v
python run_experiments.py
```

## Files

- `WP09G_FINDINGS.md` — detailed scope, benefits, withholding and economic/security caveats
- `wp09g_recovery.py` — executable reference state machine and exact Keccak-based global sparse sampler
- `test_wp09g.py` — deterministic functional and adversarial state-machine tests
- `run_experiments.py` — exact finite-population/binomial availability comparison, two lease parties
- `metrics.json`, `liveness_comparison.csv` — reproducible output
- `apply_wp09g.py` — offline-only local Solidity source patch tool (`--check` first, then `--apply`)
- `test_patch_tool.py` — textual patch-guard regressions (NOT a Solidity compiler)
- `keccak.py` — Ethereum Keccak-256 stdlib-only implementation imported from the WP09F offline package

## Local code integration (only after disabling repository Actions)

```bash
python WP09G_offline/apply_wp09g.py --repo /path/to/checkout-of-PR26 --check
python WP09G_offline/apply_wp09g.py --repo /path/to/checkout-of-PR26 --apply
cd /path/to/checkout-of-PR26
forge build && forge test -vv && forge snapshot
```

**The environment used to produce this package has no `forge`, `anvil` or `solc`; the Solidity edit is uncompiled, unbenchmarked and must not be deployed until verified.**
