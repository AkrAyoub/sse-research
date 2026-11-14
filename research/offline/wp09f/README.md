# WP-09F — Offline adversarial monitor election experiments

**Execution method:** local Python 3, standard library only. **Zero GitHub Actions, zero hosted CI minutes, zero network/API calls, zero GitHub repository changes.** This directory is a standalone, self-contained, unmerged research artifact.

## Run from any OS (Windows Git Bash/PowerShell, Linux, macOS)

```bash
cd WP09F_offline
python -m unittest discover -s . -v
python wp09f_experiments.py --rounds 50000 --seed 20261114 --output .
```

If your machine uses `python3`, replace `python` with `python3`. The script saves `results.json` and `metrics.csv` **locally**. Running it does not connect to GitHub or to a blockchain. No external Python dependencies are required.

## Contents

- `wp09f_experiments.py`: deterministic exact WP09E-style sparse Fisher–Yates sampler with Keccak-256 and ABI `uint256` encoding; exact hypergeometric/binomial analytical models; seeded Monte Carlo ideal-entropy comparisons; optional CSV/JSON export.
- `keccak.py`: tiny standalone Ethereum Keccak-256 implementation reused from the local WP09D reference and checked against the Ethereum empty-input test vector. NIST SHA3-256 is NOT interchangeable.
- `test_wp09f.py`: 11 local unit tests, including sparse-versus-dense exact protocol draw for various roster sizes, draw scope, out-of-64 reach, analytical cases, cursor-window concentrations, 5000-round Monte Carlo cross-check, and proof-withholding effects.
- `results.json`: 50,000-round experiment output, fixed seed, explanatory model caveats.
- `metrics.csv`: compact machine-readable output.
- `WP09F_FINDINGS.md`: methodology, numbers, attack implications, and research/engineering next steps.

## Scope and limitations

This runs independently of the private repository and **does not build or test Solidity/Foundry contracts**. The exact Keccak selection mechanics are mirrored from the WP09E prototype and cross-validated against an independent dense shuffle in Python; all probability experiments additionally use an ideal uniform sampling oracle, **not** the experimental RSA key holder or live block producers.

The 50,000-trial Monte Carlo is diagnostic; exact combinatorial probabilities are the authoritative results for the scenarios described. No proof of unbiased or independent operator selection is claimed. An exit, proof-withholding or cancellation attack is modeled, not demonstrated against a deployed blockchain.

## Github Actions billing protection

Before any later push/PR change, repository owner should disable repository GitHub Actions:
**Repository Settings → Actions → General → Actions permissions → Disable Actions → Save**.
Also configure an Actions budget with **Stop usage when budget limit is reached** under GitHub billing if available. The assistant cannot currently change those account/repository settings through its GitHub connector. This artifact has **not** been pushed or attached to a GitHub PR.
