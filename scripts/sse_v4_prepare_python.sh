#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ && "$(git rev-parse HEAD)" == "$1" && -z "$(git status --porcelain)" && "$(id -u)" != 0 ]]
VENV="$HOME/.venvs/sse-v4"
if [[ ! -x "$VENV/bin/python" ]]; then
  sudo -n apt-get install -y --no-install-recommends python3-venv
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -r requirements.txt
"$VENV/bin/python" -m pip check
