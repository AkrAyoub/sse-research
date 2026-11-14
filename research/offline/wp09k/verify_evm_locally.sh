#!/usr/bin/env bash
# WP09K strictly OFFLINE, disposable local Foundry runner.
# Never invokes GitHub, git push, curl, npm install, forge install, or an RPC.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/local/sse-research-at-WP09E" >&2
  exit 2
fi
command -v forge >/dev/null 2>&1 || {
  echo "BLOCKED: forge isn't installed. No network installation attempted." >&2
  exit 2
}
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(cd "$1" && pwd -P)"
for required in contracts/OpenMonitorCommittee.sol contracts/SSESettlement.sol foundry.toml foundry/test; do
  [[ -e "$REPO/$required" ]] || {
    echo "BLOCKED: missing $required in local checkout" >&2
    exit 2
  }
done
[[ -d "$REPO/lib" ]] || {
  echo "BLOCKED: Foundry library dependencies not installed locally" >&2
  exit 2
}
DEST="$(mktemp -d "${TMPDIR:-/tmp}/wp09k-offline-XXXXXXXX")"
echo "Disposable workspace: $DEST"
mkdir -p "$DEST/workspace"
cp -a "$REPO/contracts" "$DEST/workspace/contracts"
cp -a "$REPO/foundry" "$DEST/workspace/foundry"
cp -a "$REPO/lib" "$DEST/workspace/lib"
cp "$REPO/foundry.toml" "$DEST/workspace/foundry.toml"
python3 "$ROOT/apply_wp09k.py" --repo "$REPO" --out "$DEST/patch-output"
cp "$DEST/patch-output/contracts/"*.sol "$DEST/workspace/contracts/"
cp "$DEST/patch-output/foundry/test/"*.sol "$DEST/workspace/foundry/test/"
# Fail closed: --offline forbids an implicit compiler download.
export FOUNDRY_OFFLINE=true
cd "$DEST/workspace"
forge build --offline
forge test --offline --match-contract VRFAdapterIntegrationTest -vv
forge test --offline --match-contract VRFAdapterGlobalMerkleTest -vv
forge test --offline -vv
echo "LOCAL EVM TESTS COMPLETE; workspace: $DEST"
echo "Original checkout left untouched; nothing pushed or deployed."
