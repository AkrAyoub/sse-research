#!/usr/bin/env bash
# Start a pinned, SELF-OWNED Ethereum PoS research devnet, with NO real ETH.
# Never modifies historical Anvil31337 or QBFT31338 VMs. No Actions or sudo.
set -euo pipefail
: "${SSE_POS_CONF_DIR:=$HOME/sse-pos-secrets}"
: "${SSE_POS_UPSTREAM_DIR:=$HOME/sse-pos-ethereum-package-d3014d6d23d6}"
readonly UPSTREAM_SHA="d3014d6d23d683362025b9e23a0d69de49e77cca"
readonly UPSTREAM_URL="https://github.com/ethpandaops/ethereum-package.git"
readonly ENCLAVE="sse-pos-research01"

MODE="${1:---plan}"
if [[ "$#" -gt 1 || ( "$MODE" != "--plan" && "$MODE" != "--apply" ) ]]; then
  echo "Usage: bash scripts/sse_pos_launch.sh [--plan|--apply]" >&2
  exit 2
fi
if [[ "$SSE_POS_CONF_DIR" != /* || "$SSE_POS_UPSTREAM_DIR" != /* ]]; then
  echo "SSE_POS_REFUSED: absolute secret/upstream paths required" >&2
  exit 2
fi
CONFIG="$SSE_POS_CONF_DIR/network_params.yaml"
if [[ ! -f "$CONFIG" || -L "$CONFIG" || -L "$SSE_POS_CONF_DIR" ]]; then
  echo "SSE_POS_REFUSED: create protected network_params.yaml first" >&2
  exit 2
fi
if [[ "$(stat -c '%a' "$SSE_POS_CONF_DIR")" != 700 ||
      "$(stat -c '%a' "$CONFIG")" != 600 ]]; then
  echo "SSE_POS_REFUSED: private directory 0700 and args 0600 required" >&2
  exit 2
fi
# The new one-host R13 genesis MUST set Fulu AND five dependent BPO
# epochs to far future, and match its protected manifest SHA exactly.
# Never mix old R12 genesis files with this R13 bootstrap.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! python3 "$SCRIPT_DIR/../tools/sse_pos_launch_preflight.py" \
  --output-dir "$SSE_POS_CONF_DIR" --verify-only >/dev/null; then
  echo "SSE_POS_REFUSED: new R13 genesis failed pinned fork/BPO/source checks" >&2
  exit 2
fi
if ! command -v kurtosis >/dev/null 2>&1; then
  echo "SSE_POS_REFUSED: operator must install/verify Kurtosis >=1.23.0" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "SSE_POS_REFUSED: dedicated deployment host needs reviewed Docker access" >&2
  exit 2
fi
if [[ "$(id -u)" == 0 ]]; then
  echo "SSE_POS_REFUSED: do not run as root" >&2
  exit 2
fi
echo "SSE_POS_CHAIN_ID=31339"
echo "SSE_POS_ENCLAVE=$ENCLAVE"
echo "SSE_POS_UPSTREAM_PACKAGE=$UPSTREAM_URL"
echo "SSE_POS_PINNED_SHA=$UPSTREAM_SHA"
echo "SSE_POS_CONFIG_SHA256=$(sha256sum "$CONFIG" | cut -d' ' -f1)"
echo "SSE_POS_NO_REAL_ETH=true"
if [[ "$MODE" == "--plan" ]]; then
  echo "SSE_POS_DRY_RUN=true; no repo cloned, no containers started"
  exit 0
fi
if [[ -e "$SSE_POS_UPSTREAM_DIR" && ! -d "$SSE_POS_UPSTREAM_DIR/.git" ]]; then
  echo "SSE_POS_REFUSED: upstream target exists but isn't a Git checkout" >&2
  exit 2
fi
if [[ ! -d "$SSE_POS_UPSTREAM_DIR" ]]; then
  git clone "$UPSTREAM_URL" "$SSE_POS_UPSTREAM_DIR"
fi
if [[ "$(git -C "$SSE_POS_UPSTREAM_DIR" remote get-url origin)" != "$UPSTREAM_URL" ]]; then
  echo "SSE_POS_REFUSED: wrong upstream Git origin" >&2
  exit 2
fi
git -C "$SSE_POS_UPSTREAM_DIR" checkout --detach "$UPSTREAM_SHA"
if [[ "$(git -C "$SSE_POS_UPSTREAM_DIR" rev-parse HEAD)" != "$UPSTREAM_SHA" ||
      -n "$(git -C "$SSE_POS_UPSTREAM_DIR" status --porcelain)" ]]; then
  echo "SSE_POS_REFUSED: upstream source not at pristine reviewed SHA" >&2
  exit 2
fi
# Enclave name is unique to this chain; NEVER 'kurtosis clean -a'.
if kurtosis enclave inspect "$ENCLAVE" >/dev/null 2>&1; then
  echo "SSE_POS_REFUSED: existing enclave present; will not replace or destroy" >&2
  exit 2
fi
echo "SSE_POS_STAGE=START_PINNED_ETHEREUM_POS_DEVNET"
kurtosis run --enclave "$ENCLAVE" "$SSE_POS_UPSTREAM_DIR" \
  --args-file "$CONFIG"
echo "SSE_POS_STAGE=RUNNING_CHECK_WITH_kurtosis_enclave_inspect"
kurtosis enclave inspect "$ENCLAVE"
