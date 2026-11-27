#!/usr/bin/env bash
# Application-only host prerequisites; no chain clients, wallet, role or funds.
# Reuses reviewed fingerprint-pinned R152 package installation and R361 relay.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" ]]
[[ "$(id -u)" != 0 && -z "$(git status --porcelain)" ]]
[[ "$(uname -m)" == x86_64 ]]
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]]
VENV="$HOME/.venvs/sse-v4"
# Refuse existing SSE signers and runtime state; do not repurpose a live host.
for p in "$HOME/.local/share/sse-r35-chain31340-g2-private" "$HOME/.local/share/sse-r59-chain31340-observer" "$HOME/.local/share/sse31340-validator" "$HOME/.config/sse-v4" /var/lib/sse/selection.json; do
  [[ ! -e "$p" && ! -L "$p" ]] || { echo "Existing SSE state; refused: $p" >&2; exit 2; }
done
sudo -n true
sudo -n apt-get update -qq
sudo -n apt-get install -y --no-install-recommends python3-venv gnupg ca-certificates curl iproute2
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -r requirements.txt
"$VENV/bin/python" -c 'import eth_account,eth_abi,Crypto; print("V4_PYTHON_DEPS_READY=true")'
# No Docker images or blockchain clients on application-only hosts.
sudo -n /usr/bin/python3 -B - "$ROOT" <<'PYCODE'
import sys
sys.path.insert(0, sys.argv[1]+"/tools")
import sse_pos_r152_unattended_host_dependencies as p
from pathlib import Path
if not Path("/usr/sbin/zerotier-one").exists():
    p.install_verified_zerotier_apt()
p.call(["systemctl","enable","--now","zerotier-one"], timeout=80)
p.call(["zerotier-cli","join",p.NETWORK], timeout=30)
PYCODE
# Wait for actual overlay address, not merely successful join submission.
READY=0
for i in $(seq 1 18); do
  if sudo -n /usr/bin/python3 -B - "$ROOT" <<'PYCODE'
import sys
sys.path.insert(0,sys.argv[1]+"/tools")
import sse_pos_r59_native_ipv6_observer as r
try:
    iface,addr = r.overlay_ip()
except r.R59Refused:
    sys.exit(1)
print("OVERLAY_INTERFACE="+iface)
print("OVERLAY_IPV6="+addr)
PYCODE
  then READY=1; break; fi
  sleep 5
done
[[ "$READY" == 1 ]]
bash scripts/r361_install_optional_rpc_adapter.sh "$1"
"$VENV/bin/python" -B - <<'PYCODE'
import sys
sys.path.insert(0,"tools")
from sse_chain_read import LocalRPC
from sse_v4_state import GENESIS, finalized
ask=LocalRPC("http://127.0.0.1:28545",timeout=15).request
assert ask("eth_chainId",[]) == hex(31340)
assert ask("eth_getBlockByNumber",["0x0",False])["hash"].lower() == GENESIS
print("FINALIZED_HEIGHT_AND_HASH=",finalized(ask))
print("APP_HOST_PREREQUISITES_PASSED=true")
PYCODE
