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
echo "SSE: compile Python and rapidly check the previous Windows regressions first"
python -m compileall -q tools tests
for name in test_sse_mesh_broker_http.py test_sse_vm_role_setup.py test_sse_lab_release_handoff.py test_sse_ssh_identity_tunnel.py test_sse_funnel_pilot.py test_sse_experiment_evidence.py test_sse_qbft_validator_identity.py test_sse_qbft_vm_preflight.py test_sse_qbft_network_assembly.py test_sse_qbft_block_sample.py; do
  python -m unittest discover -s tests -p "$name" -v 2>&1 |
    tee ".local/manual-gate/${name%.py}.log"
done
echo "SSE: Foundry dependencies must have been installed using scripts/install-contract-deps.sh"
test -f lib/forge-std/src/Test.sol || {
  echo "Missing forge-std; run bash scripts/install-contract-deps.sh manually." >&2
  exit 2
}
echo "SSE: compile Solidity and check WP09Q before the longer Python regressions"
forge build 2>&1 | tee .local/manual-gate/forge-build.log
forge test --match-path "foundry/test/WP09QBatchedGlobalRecovery.t.sol" -vv 2>&1 |
  tee .local/manual-gate/forge-wp09q.log
echo "SSE: complete Python and Foundry regression suites"
python -m unittest discover -s tests -v 2>&1 | tee .local/manual-gate/python-tests.log
forge test -vv 2>&1 | tee .local/manual-gate/forge-all.log
echo "SSE_LOCAL_GATE_COMPLETED on $(git rev-parse HEAD)"
echo "Logs are local under .local/manual-gate; no live RPC was intentionally contacted by this wrapper."
