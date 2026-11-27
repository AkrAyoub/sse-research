#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" && "$(id -u)" != 0 ]]
PY="$HOME/.venvs/sse-v4/bin/python"
probe(){
  curl -fsS --max-time 20 http://127.0.0.1:28545 -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' | "$PY" -c 'import json,sys; n=int(json.load(sys.stdin)["result"],16); assert n>0; print("RPC_HEAD="+str(n))'
}
if ! probe; then
  systemctl --user is-active --quiet sse-rpc-adapter.service || { echo "Existing RPC transport requires inspection" >&2; exit 2; }
  python3 -B scripts/sse_v4_upgrade_rpc_client.py --source-sha "$1" --apply
  sleep 3
fi
probe
"$PY" -B - <<'PYCODE'
import json,sys
from pathlib import Path
sys.path.insert(0,"tools")
from sse_chain_read import LocalRPC
import sse_v4_state as st
m=st.load_manifest(Path("release/chain31340-v4-manifest.json"))
print(json.dumps(st.verify_deployment(LocalRPC("http://127.0.0.1:28545",timeout=20).request,m),indent=2))
PYCODE
