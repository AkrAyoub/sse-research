#!/usr/bin/env bash
# One entry point for fresh or already prepared application participants.
# No native-node reset, signing activation or funds. --publish-web opts into public read-only HTTPS.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(id -u)" != 0 && -z "$(git status --porcelain)" ]]
SHA="$(git rev-parse HEAD)"
MODE="${1:---install}"
[[ "$MODE" == --install || "$MODE" == --upgrade ]] || { echo "Use --install or --upgrade"; exit 2; }
ROLES=""
PUBLISH=0
shift || true
for ARG in "$@"; do
  if [[ "$ARG" == --publish-web ]]; then PUBLISH=1
  elif [[ -z "$ROLES" ]]; then ROLES="$ARG"
  else echo "Unexpected installer argument"; exit 2; fi
done
POL="$HOME/.config/sse-v4/policy.json"
if [[ -f "$POL" && ! -L "$POL" ]]; then
  OLD="$(python3 -B -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["roles"]))' "$POL")"
  [[ -z "$ROLES" || "$ROLES" == "$OLD" ]] || { echo "Existing role policy differs; preserve it"; exit 2; }
  ROLES="$OLD"
elif [[ -z "$ROLES" ]]; then
  echo "Available application roles: consumer,provider,monitor,keeper"
  echo "Native full_node/observer/validator: secure checkpoint/enrollment gate remains outstanding."
  read -r -p 'Select roles (comma-separated): ' ROLES
fi
ROLES="$(printf '%s' "$ROLES" | tr -d '[:space:]')"
[[ "$ROLES" =~ ^(consumer|provider|monitor|keeper)(,(consumer|provider|monitor|keeper))*$ ]] || { echo "Invalid/unsupported roles"; exit 2; }
echo "VM=$(id -un) ROLES=$ROLES SOURCE=$SHA"
# Native nodes are deliberately never modified here. If native clients are
# already installed, require their actual local EL+CL gate, not a relay.
NATIVE=0
if sudo -n docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Eq 'sse31340.*-(el|bn|vc)$'; then NATIVE=1; fi
if [[ "$(id -un)" == ayoubakrvm4707 ]]; then NATIVE=1; fi
if [[ "$NATIVE" == 1 ]]; then
  python3 -B tools/sse_setup_verify_local_native.py
  bash scripts/sse_v4_prepare_python.sh "$SHA"
else
  if systemctl --user is-active --quiet sse-rpc-adapter.service; then
    bash scripts/sse_v4_prepare_python.sh "$SHA"
    python3 -B scripts/sse_v4_upgrade_managed_rpc.py --mode client --commit "$SHA" --allow-raw-send --apply
  elif systemctl --user cat sse-rpc-adapter.service >/dev/null 2>&1; then
    echo "Existing inactive RPC adapter needs inspection; no overwrite"; exit 2
  elif [[ -f "$POL" ]]; then
    # An existing app policy with no adapter may use an older local transport.
    # Never replace an existing listener.
    bash scripts/sse_v4_prepare_python.sh "$SHA"
    if [[ -z "$(ss -H -lnt 'sport = :28545')" ]]; then
      bash scripts/r361_install_optional_rpc_adapter.sh "$SHA"
    fi
  else
    bash scripts/sse_v4_prepare_app_host.sh "$SHA"
  fi
fi
PY="$HOME/.venvs/sse-v4/bin/python"
"$PY" -B scripts/sse_v4_app_install.py --roles "$ROLES" --prepare-only
sudo -n loginctl enable-linger "$(id -un)"
sleep 3
systemctl --user is-active sse-v4-console.service
curl --noproxy '*' -fsS --max-time 15 http://127.0.0.1:8790/ -o /dev/null
if [[ "$PUBLISH" == 1 ]]; then
  "$PY" -B scripts/sse_v4_publish_web.py --apply
fi
"$PY" -B tools/sse_v4_participant_status.py
echo "SSE_PREPARATION_VERIFIED=true; activation, funding and provider admission separately gated"
