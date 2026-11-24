#!/usr/bin/env bash
# R279: only an owner-invoked experimental app EOA on four REAL standby VMs.
# Source trust: pinned exact immutable SHA, private owner 0700 directory,
# pinned existing research requirements, existing audited test-wallet generator.
# No native chain tx, Docker, PoS BLS keys, OS privilege changes, or role cap.
set -euo pipefail
umask 077

if [[ $# -ne 2 ]]; then
  echo "USAGE: bash scripts/r279_standby_vm_app_identity.sh FULL_40_CHAR_SHA --preview|--create" >&2
  exit 2
fi
PIN="$1"
MODE="$2"
if [[ ! "$PIN" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R279_REFUSED: exact lower-case 40-character Git SHA required" >&2
  exit 2
fi
case "$MODE" in --preview|--create) ;; *)
  echo "R279_REFUSED: unknown mode" >&2; exit 2 ;;
esac
if [[ "$(id -u)" == "0" ]]; then
  echo "R279_REFUSED: nonroot VM owner required" >&2
  exit 2
fi
OWNER="$(id -un)"
case "$OWNER" in
  ayoubakrvm4711) ROLE="adaptive-v2-monitor-vm4711" ;;
  ayoubakrvm4712) ROLE="adaptive-v2-monitor-vm4712" ;;
  ayoubakrvm4713) ROLE="adaptive-v2-monitor-vm4713" ;;
  ayoubakrvm4714) ROLE="adaptive-v2-provider-vm4714" ;;
  *)
    echo "R279_REFUSED: VM owner not one of the four observed small standby hosts" >&2
    exit 2
    ;;
esac
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$(git rev-parse HEAD)" != "$PIN" ]]; then
  echo "R279_REFUSED: working Git SHA differs from the reviewed immutable pin" >&2
  exit 2
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "R279_REFUSED: tracked source files not clean" >&2
  exit 2
fi
if [[ -L "$HOME/.local" || -L "$HOME/.local/share" ]]; then
  echo "R279_REFUSED: private parent path is a symlink" >&2
  exit 2
fi
PRIVATE="$HOME/.local/share/sse-v2-app-only"
KEYFILE="$PRIVATE/$ROLE.keystore.json"
if [[ -L "$PRIVATE" || -L "$KEYFILE" ]]; then
  echo "R279_REFUSED: private identity path is a symlink" >&2
  exit 2
fi
if [[ -e "$KEYFILE" ]]; then
  echo "R279_REFUSED: exact role encrypted EOA already exists; NEVER OVERWRITE" >&2
  exit 2
fi
if [[ -e "$PRIVATE" ]]; then
  if [[ ! -d "$PRIVATE" || "$(stat -c '%a:%u' "$PRIVATE")" != "700:$(id -u)" ]]; then
    echo "R279_REFUSED: existing app identity directory not private owner 0700" >&2
    exit 2
  fi
fi
if ! command -v python3 >/dev/null; then
  echo "R279_REFUSED: python3 missing" >&2
  exit 2
fi
printf 'R279_PUBLIC_STANDBY_APP_IDENTITY_PLAN=host_user:%s role:%s chain:31340 new_key_only:true native_test_eth_sent:false docker_changed:false validator_changed:false\n' "$OWNER" "$ROLE"

if [[ "$MODE" == "--preview" ]]; then
  echo "R279_PREVIEW_ONLY_NO_WALLET_OR_PACKAGE_INSTALL=true"
  exit 0
fi
if [[ ! -t 0 || ! -t 2 ]]; then
  echo "R279_REFUSED: owner terminal required to create and encrypt new app EOA" >&2
  exit 2
fi
PHRASE="CREATE-ONE-R279-CHAIN31340-$ROLE"
read -r -p "Type $PHRASE to create EXACTLY ONE encrypted application EOA: " ANSWER
if [[ "$ANSWER" != "$PHRASE" ]]; then
  echo "R279_REFUSED: owner did not authorize this one wallet" >&2
  exit 2
fi
install -d -m 0700 "$PRIVATE"
# Existing source imports eth_account only for wallet creation, not consensus.
# App-only virtualenv: no system Python/site-packages mutation.
VENV="$PRIVATE/pyvenv"
if [[ -L "$VENV" ]]; then
  echo "R279_REFUSED: owner application venv is a symlink" >&2
  exit 2
fi
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
if [[ ! -x "$PY" || ! -x "$PIP" ]]; then
  echo "R279_REFUSED: incomplete owner application virtualenv" >&2
  exit 2
fi
"$PIP" install --disable-pip-version-check -r "$ROOT/requirements.txt"
"$PY" -B "$ROOT/tools/sse_pos_test_wallet.py" \
  --role "$ROLE" --output-dir "$PRIVATE" --apply
echo "R279_ONE_STANDBY_ENCRYPTED_APP_EOA_CREATED_NO_TEST_ETH_NO_TX=true"
