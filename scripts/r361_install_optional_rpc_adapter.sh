#!/usr/bin/env bash
# Persistent optional pinned TLS RPC client for a participant.
# No keys, staking, role registration, or native node modification.
set -euo pipefail
umask 077
fail(){ echo "R361_RPC_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || fail "exact source SHA required"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ "$(git rev-parse HEAD)" == "$1" ]] || fail "wrong source"
git diff --quiet && git diff --cached --quiet || fail "dirty source"
[[ "$(id -u)" != 0 ]] || fail "nonroot participant required"
CERT="$PWD/release/chain31340-optional-rpc-vm4709.crt"
FP=967643892bf4eeb3028acd87ab8f849073d0e1ff6f93e122dae4640b69c03d3d
REMOTE=fca0:2328:77e5:740c:ce60::1
[[ "$(openssl x509 -in "$CERT" -outform DER | sha256sum | awk '{print $1}')" == "$FP" ]] || fail "certificate fingerprint mismatch"
probe(){ curl -fsS --max-time 15 http://127.0.0.1:28545 -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' | /usr/bin/python3 -c 'import json,sys; r=json.load(sys.stdin); assert r.get("result")=="0x7a6c"'; }
if probe 2>/dev/null; then
  echo "R361_EXISTING_RPC_HEALTHY=true"
  exit 0
fi
NAME=sse-rpc-adapter.service
if systemctl --user cat "$NAME" >/dev/null 2>&1; then
  fail "existing adapter unit; inspect rather than overwrite"
fi
[[ -z "$(ss -H -lnt 'sport = :28545')" ]] || fail "existing RPC listener; preserve"
curl -6 -fsS --max-time 15 --cacert "$CERT" "https://[$REMOTE]:19443/" -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' | /usr/bin/python3 -c 'import json,sys; assert json.load(sys.stdin).get("result")=="0x7a6c"'
DIR="$HOME/.config/systemd/user"
mkdir -p "$DIR"
UNIT="$DIR/$NAME"
[[ ! -e "$UNIT" && ! -L "$UNIT" ]] || fail "existing unit"
(
set -o noclobber
printf '%s\n' '[Unit]' 'Description=SSE optional pinned TLS RPC participant adapter' '[Service]' "ExecStart=/usr/bin/python3 -B $PWD/tools/sse_pos_r299_optional_tls_rpc_relay.py client --remote $REMOTE --cert $CERT --fingerprint $FP --local-port 28545 --allow-raw-send" 'Restart=always' 'RestartSec=3' 'NoNewPrivileges=true' 'UMask=0077' '[Install]' 'WantedBy=default.target' > "$UNIT"
)
systemctl --user daemon-reload
systemctl --user enable --now "$NAME"
sudo -n loginctl enable-linger "$(id -un)"
for n in 1 2 3 4 5; do
  if probe 2>/dev/null; then
    echo "R361_PERSISTENT_RPC_READY=true"
    systemctl --user is-enabled "$NAME"
    systemctl --user is-active "$NAME"
    exit 0
  fi
  sleep 2
done
fail "adapter installed but upstream health unverified"
