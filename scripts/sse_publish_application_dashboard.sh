#!/usr/bin/env bash
# R334 optional public read-only quick tunnel; URL may rotate on restart.
set -euo pipefail
umask 077
fail(){ echo "R334_REFUSED: $*" >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" ]] || fail "clean pinned source required"
[[ "$(id -u)" != 0 && "$(uname -m)" == x86_64 ]] || fail "nonroot amd64 required"
PY="$HOME/.venvs/sse-v2-operator/bin/python"
[[ -x "$PY" && "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail "owner runtime required"
systemctl --user is-active --quiet sse-application-dashboard.service
"$PY" -B tools/sse_node_install_summary.py
# Only publish the reviewed read-only dashboard, never RPC or signing services.
systemctl --user show -p ExecStart --value sse-application-dashboard.service | grep -q -- '--public-readonly --serve'
echo "Publish the read-only dashboard and its public account information using an optional Cloudflare quick tunnel. URL is temporary and may rotate."
read -r -p "Type PUBLISH-SSE-DASHBOARD to authorize: " ANSWER
[[ "$ANSWER" == PUBLISH-SSE-DASHBOARD ]] || fail "not authorized"
for p in "$HOME/.local" "$HOME/.local/bin" "$HOME/.config" "$HOME/.config/systemd" "$HOME/.config/systemd/user"; do
 [[ ! -L "$p" ]] || fail "symlink directory"
done
BIN="$HOME/.local/bin/cloudflared"
install -d -m 700 "$HOME/.local/bin"
if [[ ! -e "$BIN" ]]; then
 tmp="$(mktemp -d)"
 trap 'rm -rf -- "$tmp"' EXIT
 curl -fL --proto '=https' --proto-redir '=https' --max-time 180 https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64 -o "$tmp/cloudflared"
 echo '56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf  '"$tmp/cloudflared" | sha256sum -c -
 install -m 700 "$tmp/cloudflared" "$BIN"
fi
[[ -f "$BIN" && ! -L "$BIN" ]] || fail "invalid binary"
echo '56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf  '"$BIN" | sha256sum -c -
UNIT="$HOME/.config/systemd/user/sse-application-public-dashboard.service"
[[ ! -e "$UNIT" && ! -L "$UNIT" ]] || fail "publisher already configured"
(
set -o noclobber
cat > "$UNIT" <<EOF
[Unit]
Description=SSE optional public HTTPS dashboard
After=sse-application-dashboard.service
Requires=sse-application-dashboard.service
[Service]
ExecStart=$BIN tunnel --url http://127.0.0.1:8767 --no-autoupdate
Restart=always
RestartSec=5
NoNewPrivileges=true
UMask=0077
[Install]
WantedBy=default.target
EOF
)
systemctl --user daemon-reload
systemctl --user enable --now sse-application-public-dashboard.service
for i in $(seq 1 30); do
 URL="$(journalctl --user -u sse-application-public-dashboard.service -b -n 100 --no-pager -o cat | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)"
 if [[ -n "$URL" ]] && "$PY" -B tools/sse_node_install_summary.py --public-https "$URL"; then
  echo R334_PUBLIC_DASHBOARD_VERIFIED=true
  exit 0
 fi
 sleep 3
done
fail "public URL not verified; inspect publisher service; do not recreate wallet"
