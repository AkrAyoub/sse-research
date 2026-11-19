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
for name in test_sse_mesh_broker_http.py test_sse_vm_role_setup.py test_sse_lab_release_handoff.py test_sse_ssh_identity_tunnel.py test_sse_funnel_pilot.py test_sse_experiment_evidence.py test_sse_qbft_validator_identity.py test_sse_qbft_vm_preflight.py test_sse_qbft_network_assembly.py test_sse_qbft_block_sample.py test_sse_qbft_fleet_evidence.py test_sse_qbft_genesis_canary.py test_sse_ubuntu_security_gate.py test_sse_r9_host_setup.py test_sse_r9_release_update.py test_sse_r9_firsthost_script.py test_sse_validator_mesh_broker.py test_sse_validator_mesh_join.py test_sse_validator_headless_policy.py test_sse_open_role_requests.py test_sse_role_request_create.py test_sse_external_transport.py test_sse_qbft_role_authority.py test_sse_monitor_role_authority.py test_sse_r9_canary_lab.py test_sse_r10_observation_campaign.py test_sse_r10_paper_evidence.py test_sse_qbft_host_env.py test_sse_qbft_real_genesis_canary.py test_sse_pos_devnet_plan.py test_sse_pos_end_to_end_static.py test_sse_pos_validator_deposit.py test_sse_pos_prepare_launch.py test_sse_pos_launch_preflight.py test_sse_pos_deployment_order.py test_sse_pos_deploy_receipts.py test_sse_pos_live_roles.py; do
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
