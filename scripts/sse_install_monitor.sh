#!/usr/bin/env bash
# R336 unified fresh monitor installer. One role/publication choice.
# Explicitly does not fund, register or claim activation.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" ]] || { echo "Clean pinned source required" >&2; exit 2; }
[[ "$(id -u)" != 0 ]] || exit 2
echo "SSE chain31340 research network. This release supports fresh monitor onboarding."
echo "Selecting an option approves signed OS dependencies, ZeroTier joining, encrypted application wallet creation, initial pinned remote RPC, persistent owner services and login linger."
echo "Public mode publishes the read-only dashboard and public wallet address using Cloudflare Quick Tunnel; URL may change. No secrets or signing endpoints published."
echo "No automatic funding, registration or spending in this release."
echo "1. Monitor + public HTTPS dashboard (recommended)"
echo "2. Monitor + local-only dashboard"
echo "0. Cancel"
read -r -p "Select role and dashboard mode: " choice
case "$choice" in
 1|2) ;;
 0) exit 0 ;;
 *) exit 2 ;;
esac
SHA="$1"
bash scripts/sse_install_application_monitor.sh "$SHA" --approved-monitor
bash scripts/sse_configure_application_monitor.sh "$SHA" --approved-monitor
# Install CLI before publishing, so DNS delays cannot prevent retrieval later.
bash scripts/sse_install_node_cli.sh "$SHA"
if [[ "$choice" == 1 ]]; then
 if ! bash scripts/sse_publish_application_dashboard.sh "$SHA" --approved-monitor; then
  echo "Monitor installed; public publication not verified. Use sse status and sse logs." >&2
  exit 3
 fi
fi
echo "Installed monitor runtime; funded role activation pending."
"$HOME/.local/bin/sse" status || [[ "$?" == 3 ]]
echo 'Use sse status, sse dashboard or sse logs after reconnecting.'
echo 'If needed in this shell: export PATH="$HOME/.local/bin:$PATH"'
