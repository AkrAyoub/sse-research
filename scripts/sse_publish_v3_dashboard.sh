#!/usr/bin/env bash
# R398 V3 persistent public HTTPS and management CLI. Only publish port 8770.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail(){ echo "R398_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" ]] || fail "clean pinned source required"
[[ "$(id -u)" != 0 && "$(uname -m)" == x86_64 && "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail "unsupported owner host"
systemctl --user is-active --quiet sse-v3-console.service
[[ "$(loginctl show-user "$(id -u)" -p Linger --value)" == yes ]] || fail "linger required"
EXEC="$(systemctl --user show sse-v3-console.service -p ExecStart --value)"
[[ "$EXEC" == *"v2_status_app.py"* && "$EXEC" == *"--public-readonly"* && "$EXEC" == *"--port 8770 "* && "$EXEC" == *"--market-v3"* ]] || fail "unexpected dashboard configuration"
curl -fsS --max-time 60 http://127.0.0.1:8770/v2/status | /usr/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["marketV3"]["deployment"]["chainId"]==31340'
echo "Publish public node identity, roles and marketplace observations through Cloudflare Quick Tunnel. URL rotates on restart. No signing, wallet or RPC listener exposed."
read -r -p "Type PUBLISH-SSE-DASHBOARD to authorize: " APPROVAL
[[ "$APPROVAL" == PUBLISH-SSE-DASHBOARD ]] || fail "not authorized"
for p in "$HOME/.local" "$HOME/.local/bin" "$HOME/.local/share" "$HOME/.local/share/sse-cli" "$HOME/.config" "$HOME/.config/systemd" "$HOME/.config/systemd/user"; do
 [[ ! -L "$p" ]] || fail "symlink directory: $p"
done
install -d -m 700 "$HOME/.local/bin" "$HOME/.local/share/sse-cli"
BIN="$HOME/.local/bin/cloudflared"
HASH=56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
if [[ ! -e "$BIN" && ! -L "$BIN" ]]; then
 curl -fL --proto '=https' --proto-redir '=https' --max-time 180 https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64 -o "$TMP/cloudflared"
 echo "$HASH  $TMP/cloudflared" | sha256sum -c -
 install -m 700 "$TMP/cloudflared" "$BIN"
fi
[[ -f "$BIN" && ! -L "$BIN" && -O "$BIN" ]] || fail "unsafe cloudflared binary"
echo "$HASH  $BIN" | sha256sum -c -
DEST="$HOME/.local/share/sse-cli/$1"
[[ ! -L "$DEST" ]] || fail "unsafe CLI directory"
install -d -m 700 "$DEST"
if [[ ! -e "$DEST/sse_v3_cli.py" && ! -L "$DEST/sse_v3_cli.py" ]]; then
 install -m 600 tools/sse_v3_cli.py "$DEST/sse_v3_cli.py"
fi
[[ ! -L "$DEST/sse_v3_cli.py" ]] && cmp -s tools/sse_v3_cli.py "$DEST/sse_v3_cli.py" || fail "CLI source mismatch"
cat > "$TMP/sse" <<EOF
#!/usr/bin/env bash
exec /usr/bin/python3 -B "$DEST/sse_v3_cli.py" "\$@"
EOF
CLI="$HOME/.local/bin/sse"
if [[ -e "$CLI" || -L "$CLI" ]]; then
 [[ ! -L "$CLI" && -f "$CLI" ]] && cmp -s "$TMP/sse" "$CLI" || fail "existing CLI differs; preserve for reviewed migration"
else
 install -m 700 "$TMP/sse" "$CLI"
fi
UNIT="$HOME/.config/systemd/user/sse-v3-public-dashboard.service"
cat > "$TMP/unit" <<EOF
[Unit]
Description=SSE V3 public HTTPS dashboard
After=sse-v3-console.service
Requires=sse-v3-console.service
[Service]
ExecStart=$BIN tunnel --url http://127.0.0.1:8770 --no-autoupdate
Restart=always
RestartSec=5
NoNewPrivileges=true
UMask=0077
[Install]
WantedBy=default.target
EOF
if [[ -e "$UNIT" || -L "$UNIT" ]]; then
 [[ ! -L "$UNIT" && -f "$UNIT" ]] && cmp -s "$TMP/unit" "$UNIT" || fail "existing unit differs"
else
 install -m 600 "$TMP/unit" "$UNIT"
fi
systemctl --user daemon-reload
systemctl --user enable --now sse-v3-public-dashboard.service
for i in $(seq 1 30); do
 if "$CLI" dashboard; then
  echo SSE_V3_PUBLIC_HTTPS_VERIFIED=true
  echo 'Use sse status, sse dashboard, sse logs; ~/.local/bin must be on PATH.'
  exit 0
 fi
 sleep 5
done
fail "public HTTPS not verified; inspect sse logs; installed service preserved"
