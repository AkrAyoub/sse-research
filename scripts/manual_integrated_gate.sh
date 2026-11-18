#!/usr/bin/env bash
# Developer-initiated LOCAL gate only: no GitHub Actions and no live-chain writes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo "SSE_MANUAL_INTEGRATION_SHA=$(git rev-parse HEAD)"
git status --short
python --version
if ! command -v forge >/dev/null 2>&1; then
  echo "Foundry is not available in this shell; on Windows run from Git Bash." >&2
  exit 2
fi
forge --version
mkdir -p .local/manual-gate
echo "SSE: compile Python and run the complete local suite"
python -m compileall -q tools tests
python -m unittest discover -s tests -v 2>&1 | tee .local/manual-gate/python-tests.log
echo "SSE: Foundry dependencies must have been installed using scripts/install-contract-deps.sh"
test -f lib/forge-std/src/Test.sol || {
  echo "Missing forge-std; run bash scripts/install-contract-deps.sh manually." >&2
  exit 2
}
forge build 2>&1 | tee .local/manual-gate/forge-build.log
forge test --match-path "foundry/test/WP09QBatchedGlobalRecovery.t.sol" -vv 2>&1 |
  tee .local/manual-gate/forge-wp09q.log
forge test -vv 2>&1 | tee .local/manual-gate/forge-all.log
echo "SSE_LOCAL_GATE_COMPLETED on $(git rev-parse HEAD)"
echo "Logs are local under .local/manual-gate; no live RPC was intentionally contacted by this wrapper."
