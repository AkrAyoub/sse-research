#!/usr/bin/env bash
# Repeatable FIRST-BOOT validation on one FRESH Ubuntu QBFT machine.
# Source MUST already be cloned from private GitHub with this VM's read-only
# deploy key. Never used on VM4695 / Anvil31337. No GitHub Actions.
# Will make a VENV if absent, install reviewed minimum dependencies and run
# actual Ubuntu permission tests. New Besu key only on EXPLICIT --apply-identity,
# after human-approved Tailscale admission. No Docker start, wallet creation,
# RPC mutation, or network bootstrap is performed.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: bash scripts/r9_ubuntu_firsthost.sh validator-N APPROVED_40_HEX_GITSHA [--apply-identity]" >&2
  exit 2
fi
NODE_ID="$1"
APPROVED_SHA="$2"
MODE="${3:---dry-run}"
if [[ ! "$NODE_ID" =~ ^validator-[1-4]$ ]]; then
  echo "SSE_FIRSTHOST_REFUSED: initial genesis validator ID must be validator-1..4" >&2
  exit 2
fi
if [[ ! "$APPROVED_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SSE_FIRSTHOST_REFUSED: pin a full SHA, not branch HEAD" >&2
  exit 2
fi
if [[ "$MODE" != "--dry-run" && "$MODE" != "--apply-identity" ]]; then
  echo "SSE_FIRSTHOST_REFUSED: unknown mode" >&2
  exit 2
fi
if [[ "$(id -u)" -eq 0 ]]; then
  echo "SSE_FIRSTHOST_REFUSED: run as local nonroot Ubuntu checkout owner" >&2
  exit 2
fi
if [[ ! -r /etc/os-release ]] || ! grep -Eq '^ID="?ubuntu"?$' /etc/os-release; then
  echo "SSE_FIRSTHOST_REFUSED: native Ubuntu only" >&2
  exit 2
fi
if grep -Eiq 'microsoft|wsl' /proc/sys/kernel/osrelease; then
  echo "SSE_FIRSTHOST_REFUSED: WSL is not an independent VM" >&2
  exit 2
fi
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "$(git rev-parse HEAD)" != "$APPROVED_SHA" ]]; then
  echo "SSE_FIRSTHOST_REFUSED: checkout is not approved Git SHA" >&2
  exit 2
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "SSE_FIRSTHOST_REFUSED: modified tracked source" >&2
  exit 2
fi
if [[ ! -d .venv-r9 ]]; then
  python3 -m venv .venv-r9
fi
# shellcheck disable=SC1091
source .venv-r9/bin/activate
python -m pip install -r infra/qbft-multivm/requirements.txt
mkdir -p "$HOME/sse-r9-validation"
chmod 700 "$HOME/sse-r9-validation"
python --version
python tools/sse_ubuntu_security_gate.py --expected-commit "$APPROVED_SHA" \
  2>&1 | tee "$HOME/sse-r9-validation/ubuntu-security-$NODE_ID.log"
python -m unittest discover -s tests -p 'test_sse_qbft_*.py' -v \
  2>&1 | tee "$HOME/sse-r9-validation/qbft-python-$NODE_ID.log"
python tools/sse_r9_host_setup.py doctor --expected-commit "$APPROVED_SHA" \
  | tee "$HOME/sse-r9-validation/doctor-$NODE_ID.json"
python -m pip freeze > "$HOME/sse-r9-validation/python-freeze-$NODE_ID.txt"
if ! python - "$HOME/sse-r9-validation/doctor-$NODE_ID.json" <<'PY'
import json,sys
with open(sys.argv[1],encoding="utf-8") as f:
    p=json.load(f)
sys.exit(0 if p["readyForValidatorIdentity"] else 1)
PY
then
  echo "SSE_FIRSTHOST_PENDING: Tailscale not admitted; no validator key generated."
  echo "Operator must approve a tailnet and enroll this host, then rerun this script."
  exit 0
fi
if [[ "$MODE" == "--apply-identity" ]]; then
  python tools/sse_r9_host_setup.py init-identity \
    --expected-commit "$APPROVED_SHA" --node-id "$NODE_ID" \
    --private-dir "$HOME/sse-qbft-private" --apply \
    | tee "$HOME/sse-r9-validation/public-identity-$NODE_ID.json"
  echo "SSE_FIRSTHOST_IDENTITY_CREATED: NEVER copy or commit the local node.key"
else
  python tools/sse_r9_host_setup.py init-identity \
    --expected-commit "$APPROVED_SHA" --node-id "$NODE_ID" \
    --private-dir "$HOME/sse-qbft-private"
  echo "SSE_FIRSTHOST_DRY_RUN: add --apply-identity only after reviewing device authorization."
fi
echo "SSE_FIRSTHOST_SOURCE_SECURITY_GATE_COMPLETE; no Besu or wallet transaction started."
