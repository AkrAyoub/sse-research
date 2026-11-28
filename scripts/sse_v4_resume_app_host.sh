#!/usr/bin/env bash
# Resume lightweight onboarding after initial dependencies / overlay setup.
# No wallet deletion, role overwrite, native modifications or automatic funding.
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $# == 2 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" && "$(id -u)" != 0 ]]
ROLES="$2"
[[ "$ROLES" =~ ^(consumer|provider|monitor|keeper)(,(consumer|provider|monitor|keeper))*$ ]]
PY="$HOME/.venvs/sse-v4/bin/python"
[[ -x "$PY" ]]
"$PY" -m pip check
if [[ -e "$HOME/.config/sse-v4/policy.json" ]]; then
  "$PY" - "$ROLES" <<'PYCODE'
import json,sys
from pathlib import Path
p=json.loads((Path.home()/".config/sse-v4/policy.json").read_text())
assert set(p["roles"])==set(sys.argv[1].split(",")), "Existing policy differs; do not overwrite"
PYCODE
fi
sudo -n zerotier-cli info
sudo -n zerotier-cli listnetworks
ip -6 route get fca0:2328:77e5:740c:ce60::1
bash scripts/r361_install_optional_rpc_adapter.sh "$1"
"$PY" -B - <<'PYCODE'
import json,sys
from pathlib import Path
sys.path.insert(0,"tools")
from sse_chain_read import LocalRPC
import sse_v4_state as st
m=st.load_manifest(Path("release/chain31340-v4-manifest.json"))
ask=LocalRPC("http://127.0.0.1:28545",timeout=20).request
assert int(ask("eth_blockNumber",[]),16)>0
print(json.dumps(st.verify_deployment(ask,m),indent=2))
PYCODE
"$PY" -B scripts/sse_v4_app_install.py --roles "$ROLES" --prepare-only
sudo -n loginctl enable-linger "$(id -un)"
sleep 3
systemctl --user is-active sse-v4-console.service
curl -fsS --max-time 15 http://127.0.0.1:8790/ -o /dev/null
echo "VM=$(id -un)"
echo "V4_APPLICATION_PREPARATION_COMPLETE=true"
