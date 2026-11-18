# WP-09N — Local gas benchmarks and runtime-size sweep

**No GitHub Actions, no remote push, no RPC, no contract deployment.** All operations are local and use only your already-installed Python 3.12, Forge 1.9.0, solc 0.8.24 and repository's Forge dependencies. No dependencies will be downloaded; the tool sets `FOUNDRY_OFFLINE=true`.

### Install

Extract the ZIP **into the root of your existing SSE repository**, where `foundry.toml` and `contracts/` live. The package contains only NEW files:

- `foundry/test/WP09NGasBench.t.sol`
- `foundry/test/WP09NWithdrawalReentrancy.t.sol`
- `tools/wp09n_local.py`
- `tests/test_wp09n.py`
- `docs/research/WP09N_FINDINGS.md`
- `README_WP09N.md` and a small evidence summary

The ZIP does **not** modify existing contracts, Foundry settings, or prior test files. In Git Bash in that repository:

```bash
python -m unittest discover -s tests -p 'test_wp09n.py' -v
python tools/wp09n_local.py all
forge test -vv
```

`all` runs four optimizer builds (1, 50, 200, 500) in separate `.local/wp09n/optimize_runs_*/` artifact/cache folders, then 15 new success-gas tests and one withdrawal-reentrancy test. It writes:

- `.local/wp09n/optimizer_sweep.csv` (size/headroom per optimizer profile)
- `.local/wp09n/wp09n_foundry_bench.log` (raw test output)
- `.local/wp09n/success_call_gas.csv` (16 success-only gas deltas)
- `.local/wp09n/wp09n_security_test.log` (attack-regression outcome)

If any benchmark fails, its CSV is not produced. The `sweep` subcommand may return nonzero if a profile violates EIP-170; that is a finding, not a reason to skip the other tests. Use individual commands if needed:

```bash
python tools/wp09n_local.py sweep
python tools/wp09n_local.py bench
python tools/wp09n_local.py security
```

**Do not commit or push until the local tests pass.** We must not trigger billable GitHub Actions without verifying repo settings.

### What to send back

Upload `.local/wp09n/optimizer_sweep.csv`, `.local/wp09n/success_call_gas.csv`, and any failed-test logs. Include the final `forge test -vv` summary. We will select a measured compiler profile or prepare a source refactor only after these results exist.

### Measurement caveats

- Benchmark `gasleft()` deltas exclude EOA transaction intrinsic gas and actual Chainlink VRF charges.
- A single sample per scenario is NOT a p50/p95 distribution.
- `MockVRFV25Coordinator` does not check VRF cryptographic proofs.
- The report's 117/117 prior Foundry passes were on the user's machine and precede these new tests.
