# Manual integration regression checkpoint — Windows Git Bash — 2026-11-18

**User-executed transcript**, source checked out at Git commit
`a4ed50e41f09db0b29950f26909d03cedc06c1bd`
from branch `integration/r7-wp09q-wan-multivm-no-actions`.

The operator ran `bash scripts/manual_integrated_gate.sh` on native Windows with Python 3.12. The full Python suite executed **816 tests in 126.926 seconds**, reporting **19 errors and 9 skips**. The wrapper was `set -euo pipefail`, so it **stopped before any new Foundry build or targeted WP09Q test**. Do not call this a green integrated test.

Errors, independently classified from the uploaded log:
- `tests/test_sse_lab_release_handoff.py`: 2 errors, POSIX-only `os.geteuid()` used for SSH-key ownership on Windows.
- `tests/test_sse_ssh_identity_tunnel.py`: 2 errors, POSIX-only `os.geteuid()` for private known_hosts and key.
- `tests/test_sse_vm_role_setup.py`: 9 errors, POSIX-only `os.uname()` in test fixtures and `os.geteuid()` in Linux wallet directories.
- `tests/test_sse_mesh_broker_http.py`: 6 errors, SQLite database still open at TempDirectory removal on Windows (WinError 32).

Implemented follow-up on GitHub for **the next source revision**:
- Linux/POSIX permissions and machine-bound wallet tests are explicitly skipped on Windows, **not weakened** in the protected implementation. They still must execute fully on Ubuntu before release.
- Portable test fixture uses `socket.gethostname()` in place of unavailable `os.uname()`, so non-privileged economic / role-policy tests can still run on Windows.
- Both the enrollment WSGI endpoint and its fixture use `contextlib.closing(sqlite3.connect(...))` rather than relying on SQLite connection context-manager commit behavior. This prevents Windows file-delete locks.
- Manual runner now prioritizes six targeted regression modules and Solidity build/targeted WP09Q testing before rerunning the long full Python suite. All tests remain manual, no Actions.

**Status:** Source fixes committed only when the next integration branch commit is created. **No claim of passing tests until an actual rerun.** Python module `tools/sse_experiment_evidence.py` creates a hash/index manifest of reviewed logs; it does not copy logs, backup chain state or authorize VM deletion. No private key material should be added to GitHub.

## Following manual acceptance (in this order)
1. `git rev-parse HEAD` and clean/known source worktree.
2. Targeted 6 test modules, including broker Windows cleanup.
3. `forge build` and `forge test --match-path 'foundry/test/WP09QBatchedGlobalRecovery.t.sol' -vv` on the actual integrated source.
4. Full Python+Foundry tests, exact error trace and EIP-170 runtime/gas report.
5. Repeat Ubuntu-only permission/machine-binding tests on Ubuntu before VM onboarding, as native Windows skips do NOT satisfy their acceptance gate.
6. Actual external-host Tailscale + HTTPS funnel admission and four independent validator acceptance with immutable genesis and real receipts.
