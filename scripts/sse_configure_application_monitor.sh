#!/usr/bin/env bash
# R331: finish application monitor bootstrap with persistent RPC and local dashboard.
set -euo pipefail
umask 077
fail(){ echo "R331_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "pinned commit required"
[[ "$(id -u)" != 0 ]] || fail "nonroot owner required"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" ]] || fail "clean pinned checkout required"
PY="$HOME/.venvs/sse-v2-operator/bin/python"
KEY="$HOME/.local/share/sse-v2-app-only/monitor.keystore.json"
CERT="$ROOT/release/chain31340-optional-rpc-vm4709.crt"
FINGERPRINT=967643892bf4eeb3028acd87ab8f849073d0e1ff6f93e122dae4640b69c03d3d
REMOTE=fca0:2328:77e5:740c:ce60::1
MANIFEST="$ROOT/evidence/r261_vm4707_latest_state_v2_deployment_candidate.json"
[[ -x "$PY" && -f "$KEY" && ! -L "$KEY" && "$(stat -c '%a:%u' "$KEY")" == "600:$(id -u)" ]] || fail "existing private monitor identity required"
[[ "$ROOT" =~ ^/[a-zA-Z0-9_./-]+$ && "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail "unsupported service path"
ADDRESS="$("$PY" -B - "$KEY" "$CERT" "$FINGERPRINT" <<'PYTHON'
import json,sys,ssl,hashlib,re
from pathlib import Path
cert=ssl.PEM_cert_to_DER_cert(Path(sys.argv[2]).read_text("ascii"))
assert hashlib.sha256(cert).hexdigest()==sys.argv[3], "RPC certificate pin mismatch"
address=json.loads(Path(sys.argv[1]).read_text())["address"]
assert re.fullmatch(r"[0-9a-fA-F]{40}",address)
print("0x"+address)
PYTHON
)"
/usr/bin/python3 -B -c 'import sys;sys.path.insert(0,"tools");from sse_pos_r291_common_public_overlay_onboarding import status;assert status()["actualOpenOverlayReadyForCrossHostTransport"]'
for p in "$HOME/.config" "$HOME/.config/systemd" "$HOME/.config/systemd/user"; do
 [[ ! -L "$p" ]] || fail "symlink configuration path"
done
UNITS="$HOME/.config/systemd/user"
install -d -m 700 "$UNITS"
RPC="$UNITS/sse-application-rpc.service"
DASH="$UNITS/sse-application-dashboard.service"
[[ ! -e "$RPC" && ! -L "$RPC" && ! -e "$DASH" && ! -L "$DASH" ]] || fail "existing services; inspect instead of overwrite"
if ss -H -ltn '( sport = :28545 or sport = :8767 )' | grep -q .; then fail "local service port occupied"; fi
echo "Initial optional RPC: $REMOTE port 19443, certificate pinned."
echo "Enables persistent owner services and login linger; dashboard remains local only."
read -r -p "Type CONFIGURE-SSE-MONITOR to approve: " APPROVAL
[[ "$APPROVAL" == CONFIGURE-SSE-MONITOR ]] || fail "not authorized"
NODE="node-$(sha256sum /etc/machine-id | cut -c1-20)"
# Exclusive writes, never overwrite existing service configuration.
(
set -o noclobber
cat > "$RPC" <<EOF
[Unit]
Description=SSE optional pinned RPC client
[Service]
ExecStart=$PY -B $ROOT/tools/sse_pos_r299_optional_tls_rpc_relay.py client --remote $REMOTE --cert $CERT --fingerprint $FINGERPRINT --local-port 28545 --allow-raw-send
Restart=always
RestartSec=5
NoNewPrivileges=true
UMask=0077
[Install]
WantedBy=default.target
EOF
cat > "$DASH" <<EOF
[Unit]
Description=SSE monitor dashboard
After=sse-application-rpc.service
Requires=sse-application-rpc.service
[Service]
ExecStart=$PY -B $ROOT/services/node-console/v2_status_app.py --node-id $NODE --roles monitor --el http://127.0.0.1:28545 --v2-manifest $MANIFEST --monitor-address $ADDRESS --market-overview --port 8767 --public-readonly --serve
Restart=always
RestartSec=5
NoNewPrivileges=true
UMask=0077
[Install]
WantedBy=default.target
EOF
)
sudo -n loginctl enable-linger "$(id -un)"
systemctl --user daemon-reload
systemctl --user enable --now sse-application-rpc.service
for i in $(seq 1 15); do
 if "$PY" -B tools/sse_pos_r206_adaptive_v2_deployment_audit.py --help >/dev/null && curl -fsS --max-time 10 -H 'Content-Type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' http://127.0.0.1:28545 | "$PY" -c 'import json,sys;assert json.load(sys.stdin)["result"]=="0x7a6c"'; then break; fi
 sleep 3
done
PYTHONPATH="$ROOT/tools" "$PY" -B - "$MANIFEST" <<'PYTHON'
import sys,json
from pathlib import Path
from sse_pos_r206_adaptive_v2_deployment_audit import verify,load
print(json.dumps(verify(load(Path(sys.argv[1])),"http://127.0.0.1:28545"),indent=2))
PYTHON
systemctl --user enable --now sse-application-dashboard.service
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 --max-time 120 http://127.0.0.1:8767/v2/status | "$PY" -m json.tool
echo R331_PERSISTENT_RPC_AND_LOCAL_MONITOR_DASHBOARD_READY=true
echo R331_PUBLIC_HTTPS_AND_FUNDED_ACTIVATION_PENDING=true
