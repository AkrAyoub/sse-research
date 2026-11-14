# WP09H: offline quorum-withholding research package

This package performs **NO GitHub Actions or GitHub writes**. It does not use paid hosted runners, external network calls or a blockchain RPC.

## Results

- 28 Python tests: passing
- 8 scenarios x 50,000 locally simulated ideal committee elections = 400,000
- Genuine Ed25519 authenticated *participation receipts*, NOT threshold-VRF shares
- Honest-quorum and malicious last-share withholding analyzed by exact probability and reproducible Monte Carlo

## Run

```bash
cd WP09H_offline
python -m unittest discover -s . -p 'test_wp09h.py' -v
python wp09h_experiments.py --trials 50000 --output .
```

Requires Python 3.11+ and `cryptography` (Ed25519). No GitHub setup required. See `WP09H_FINDINGS.md` for assumptions and limits.

## Code

- `wp09h_policy.py`: frozen scope, Ed25519 signer receipt quorum, expiry and *mocked* unique-proof gate
- `wp09h_experiments.py`: exact probability / Monte Carlo attack model
- `test_wp09h.py`: 28 isolated tests, including WP09G batch-election integration
- `wp09g_recovery.py`, `keccak.py`: copied WP09G reference dependencies
- `results.json`, `threshold_bias_metrics.csv`: full results

**Security**: A signer receipt quorum is not a cryptographic threshold VRF. The unique-proof verifier is only an abstract externally injected test oracle; replace it with independently reviewed technology before any deployment. Latest recorded project progress remains 26% total, R3 38%.
