#!/usr/bin/env bash
# Lab convenience wrapper only; not a network role allowlist.
# Existing participants choose compatible roles with sse_v4_app_install.py.
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" ]]
SHA="$1"
case "$(id -un)" in
  ayoubakrvm4707) ROLES="consumer,monitor,keeper" ;;
  ayoubakrvm4711) ROLES="monitor,keeper" ;;
  ayoubakrvm4712) ROLES="monitor,consumer" ;;
  ayoubakrvm4713) ROLES="monitor,keeper" ;;
  ayoubakrvm4714) ROLES="provider,monitor" ;;
  ayoubakrvm4715) ROLES="monitor,keeper" ;;
  ayoubakrvm4717) ROLES="provider,monitor" ;;
  ayoubakrvm4718) ROLES="provider,monitor" ;;
  ayoubakrvm4719) ROLES="consumer,monitor,keeper" ;;
  ayoubakrvm4720) ROLES="monitor,keeper" ;;
  *) echo "Not in this lab batch; general installer accepts arbitrary compatible roles." >&2; exit 2 ;;
esac
echo "VM=$(id -un)"
echo "PROPOSED_ROLES=$ROLES"
VENV="$HOME/.venvs/sse-v4"
PY="$VENV/bin/python"
EXISTING=(--existing-app)
if [[ "$(id -un)" == ayoubakrvm4707 ]]; then
  EXISTING=(--existing-native)
fi
python3 -B scripts/sse_setup.py --commit "$SHA" --roles "$ROLES" "${EXISTING[@]}" --apply
sleep 3
systemctl --user is-active sse-v4-console.service
curl -fsS --max-time 15 http://127.0.0.1:8790/ -o /dev/null
"$PY" -B - <<'PYCODE'
import json
from pathlib import Path
p=json.loads((Path.home()/".config/sse-v4/policy.json").read_text())
print("PUBLIC_WALLET_ADDRESS="+p["wallet"])
print("V4_ROLES="+",".join(p["roles"]))
PYCODE
echo "VM=$(id -un)"
echo "V4_APPLICATION_PREPARATION_COMPLETE=true"
