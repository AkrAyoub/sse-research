#!/usr/bin/env bash
# Install owner-local persistent CLI, no service or wallet mutations.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git -C "$ROOT" rev-parse HEAD)" == "$1" && -z "$(git -C "$ROOT" status --porcelain)" ]] || exit 2
[[ "$(id -u)" != 0 && "$HOME" =~ ^/[a-zA-Z0-9_./-]+$ ]] || exit 2
for p in "$HOME/.local" "$HOME/.local/bin" "$HOME/.local/share" "$HOME/.local/share/sse-cli"; do
 [[ ! -L "$p" ]] || exit 2
done
BASE="$HOME/.local/share/sse-cli"
install -d -m 700 "$BASE" "$HOME/.local/bin"
# Keep a separate versioned snapshot independent of future Git checkouts.
DEST="$BASE/$1"
if [[ ! -e "$DEST" ]]; then
 mkdir -m 700 "$DEST"
 install -m 600 "$ROOT/tools/sse_node_cli.py" "$ROOT/tools/sse_node_install_summary.py" "$DEST/"
fi
[[ ! -L "$DEST" && -d "$DEST" ]] || exit 2
for name in sse_node_cli.py sse_node_install_summary.py; do
 [[ ! -L "$DEST/$name" ]] && cmp -s "$ROOT/tools/$name" "$DEST/$name" || exit 2
done
BIN="$HOME/.local/bin/sse"
if [[ -e "$BIN" || -L "$BIN" ]]; then
 echo "Existing sse command; refusing overwrite." >&2
 exit 2
fi
(
set -o noclobber
cat > "$BIN" <<EOF
#!/usr/bin/env bash
exec /usr/bin/python3 -B "$DEST/sse_node_cli.py" "\$@"
EOF
)
chmod 700 "$BIN"
echo "Installed $BIN"
echo 'New Ubuntu login shells normally include ~/.local/bin on PATH.'
echo 'For this shell: export PATH="$HOME/.local/bin:$PATH"'
"$BIN" status
