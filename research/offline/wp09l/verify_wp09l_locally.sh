#!/usr/bin/env bash
# WP09L local-only verification; intentionally NO GitHub, curl, npm or installs.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/local/sse-research-at-WP09E" >&2
  exit 2
fi
command -v forge >/dev/null || {
  echo "BLOCKED: Foundry forge not installed; no download attempted" >&2
  exit 2
}
TOOLROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$1" && pwd -P)"
for item in contracts/OpenMonitorCommittee.sol contracts/SSESettlement.sol foundry/test foundry.toml lib; do
  if [[ ! -e "$REPO/$item" ]]; then
    echo "BLOCKED: missing $item; no download attempted" >&2
    exit 2
  fi
done
WORK="$(mktemp -d "${TMPDIR:-/tmp}/wp09l-offline-XXXXXXXX")"
mkdir -p "$WORK/workspace"
cp -a "$REPO/contracts" "$WORK/workspace/contracts"
cp -a "$REPO/foundry" "$WORK/workspace/foundry"
cp -a "$REPO/lib" "$WORK/workspace/lib"
cp "$REPO/foundry.toml" "$WORK/workspace/foundry.toml"
python3 "$TOOLROOT/apply_wp09l.py" --repo "$REPO" --out "$WORK/patch-output"
cp "$WORK/patch-output/contracts/"*.sol "$WORK/workspace/contracts/"
cp "$WORK/patch-output/foundry/test/"*.sol "$WORK/workspace/foundry/test/"
export FOUNDRY_OFFLINE=true
cd "$WORK/workspace"
echo "Running Foundry offline in $WORK/workspace; original repo untouched"
forge build --offline
forge test --offline --match-contract VRFFeePolicyTest -vv
forge test --offline --match-contract VRFFeeGlobalMerkleTest -vv
forge test --offline -vv
forge test --offline --match-contract VRFFeePolicyTest --gas-report
printf 'Local EVM tests completed. Report and workspace: %s\n' "$WORK"
