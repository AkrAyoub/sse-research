#!/usr/bin/env bash
# Fully headless phase-1 bootstrap for NEW, owner-provisioned Ubuntu validator
# machines. Requires a previously pinned reviewed private Git checkout or
# verified signed release and a ROOT-ONLY one-time invitation injected by a
# trusted provisioner at /run/sse/validator.invitation.
#
# This is NOT the public installer for arbitrary untrusted machines: it
# must only run AFTER a recorded operator invitation. No Anvil31337 changes.
# No wallet keys printed, RPC calls, Docker start, validator votes, or Actions.
set -euo pipefail
if [[ $# -lt 4 || $# -gt 6 ]]; then
  echo "Usage: bash scripts/r9_headless_validator_bootstrap.sh validator-N local-user approved-40hex-sha https://broker.ts.net [--apply] [--use-existing-tailnet]" >&2
  exit 2
fi
NODE_ID="$1"
OWNER="$2"
REV="$3"
BROKER="$4"
APPLY=false
EXISTING=false
shift 4
for ARG in "$@"; do
  case "$ARG" in
    --apply) APPLY=true ;;
    --use-existing-tailnet) EXISTING=true ;;
    *) echo "SSE_HEADLESS_REFUSED: unknown option" >&2; exit 2 ;;
  esac
done
if [[ ! "$NODE_ID" =~ ^validator-[1-4]$ ||
      ! "$OWNER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ||
      ! "$REV" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SSE_HEADLESS_REFUSED: invalid validator identity, username or Git SHA" >&2
  exit 2
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "SSE_HEADLESS_REFUSED: apply only as Ubuntu root; use --dry-run script first" >&2
  exit 2
fi
if ! grep -Eq '^ID="?ubuntu"?$' /etc/os-release ||
   grep -Eiq 'microsoft|wsl' /proc/sys/kernel/osrelease; then
  echo "SSE_HEADLESS_REFUSED: native Ubuntu required" >&2
  exit 2
fi
if ! id "$OWNER" >/dev/null 2>&1; then
  echo "SSE_HEADLESS_REFUSED: dedicated checkout user missing" >&2
  exit 2
fi
HOME_DIR="$(getent passwd "$OWNER" | cut -d: -f6)"
REPO="$HOME_DIR/sse-r9"
if [[ -z "$HOME_DIR" || "$HOME_DIR" == "/" || ! -d "$REPO/.git" ||
      -L "$REPO" || -L "$HOME_DIR" ]]; then
  echo "SSE_HEADLESS_REFUSED: expected owner-controlled ~/sse-r9 checkout" >&2
  exit 2
fi
if [[ "$(runuser -u "$OWNER" -- git -C "$REPO" rev-parse HEAD)" != "$REV" ]] ||
   [[ -n "$(runuser -u "$OWNER" -- git -C "$REPO" status --porcelain --untracked-files=no)" ]]; then
  echo "SSE_HEADLESS_REFUSED: source not at clean approved GitHub commit" >&2
  exit 2
fi
# No chance of accidentally deploying over the historical Anvil RPC.
if ss -lnt | grep -Eq '(:8545|:18545|:18559)[[:space:]]'; then
  echo "SSE_HEADLESS_REFUSED: existing Anvil/Besu RPC detected" >&2
  exit 2
fi
runuser -u "$OWNER" -- python3 "$REPO/tools/sse_validator_mesh_join.py" \
  --node-id "$NODE_ID" --broker-url "$BROKER"
if [[ "$APPLY" == false ]]; then
  echo "SSE_HEADLESS_DRY_RUN: no enrollment, identity, chain or Docker changes"
  exit 0
fi
# Root operation exclusively for a FIRST-TIME Tailscale invite. Existing
# joined devices cannot be silently reauthenticated or retagged.
if tailscale status --json | python3 -c \
  'import json,sys; x=json.load(sys.stdin); sys.exit(0 if x.get("BackendState")=="Running" else 1)'; then
  if [[ "$EXISTING" != true ]]; then
    echo "SSE_HEADLESS_REFUSED: Tailscale already joined; require --use-existing-tailnet after operator tag/ACL review" >&2
    exit 2
  fi
  echo "SSE_HEADLESS_EXISTING_DEVICE_REUSED: no Tailscale credentials rotated"
else
  if [[ "$EXISTING" == true ]]; then
    echo "SSE_HEADLESS_REFUSED: expected existing Tailscale device not connected" >&2
    exit 2
  fi
  python3 "$REPO/tools/sse_validator_mesh_join.py" \
    --node-id "$NODE_ID" --broker-url "$BROKER" --apply
fi
# Dedicated account runs all security tests and own local validator key
# ceremony. A failure does NOT reset or copy cryptographic identities.
runuser -u "$OWNER" -- bash "$REPO/scripts/r9_ubuntu_firsthost.sh" \
  "$NODE_ID" "$REV" --apply-identity

echo "SSE_HEADLESS_PHASE1_COMPLETE: approved tailnet device + local validator key; no chain, validator vote or app wallet activated"
