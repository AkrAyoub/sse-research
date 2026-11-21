#!/usr/bin/env bash
# R20: create one REAL owner-controlled TEST-ONLY EOA encrypted keystore.
# No mnemonic/validator deposits, EL/CL genesis, public ports or Mainnet tx.
# Never use tee, shell -x, or paste private logs to GitHub/chat.
set -euo pipefail
umask 077
set +x

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R20_OPERATOR_REFUSED: exact 40-character Git source SHA required" >&2
  exit 2
fi
ROOT="$(cd -- "$(dirname -- "$BASH_SOURCE")/.." && pwd)"
cd "$ROOT"
if [[ "$(git rev-parse --verify HEAD^{commit})" != "$1" ]]; then
  echo "R20_OPERATOR_REFUSED: Git checkout mismatch" >&2
  exit 2
fi
if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code; then
  echo "R20_OPERATOR_REFUSED: tracked files locally modified" >&2
  exit 2
fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo "R20_OPERATOR_REFUSED: developer version requires Linux x86_64" >&2
  exit 2
fi
if [[ ! -t 0 || ! -t 2 ]]; then
  echo "R20_OPERATOR_REFUSED: human TTY required for hidden wallet password" >&2
  exit 2
fi

CAST="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0/cast"
CAST_SHA="cae9d8a3e9a2c2f121879f39498472fee8a767318fc26ff7e3c73908133fdaa4"
if [[ -L "$CAST" || ! -f "$CAST" || ! -x "$CAST" ]]; then
  echo "R20_OPERATOR_REFUSED: pinned Cast v1.9.0 missing" >&2
  exit 2
fi
if ! printf '%s  %s\n' "$CAST_SHA" "$CAST" | sha256sum --check --status; then
  echo "R20_OPERATOR_REFUSED: Cast executable SHA256 mismatch" >&2
  exit 2
fi
echo "R20_CAST_VERIFIED_SHA256=true"

# Probe REAL Lighthouse v8.3.3 key-custody flags, without generating keys,
# opening ports or exposing other operators' key material.
LIGHTHOUSE="$(python3 -B tools/sse_pos_client_pins.py --refs | tail -n 1)"
EXPECTED_ID="$(python3 -B tools/sse_pos_client_pins.py --image-ids | tail -n 1)"
ACTUAL_ID="$(sudo -n docker image inspect --format '{{.Id}}' "$LIGHTHOUSE")"
if [[ "$ACTUAL_ID" != "$EXPECTED_ID" ]]; then
  echo "R20_OPERATOR_REFUSED: pinned Lighthouse image ID mismatch" >&2
  exit 2
fi
lighthouse_help() {
  sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --hostname sse-key-cli-probe \
    --add-host sse-key-cli-probe:127.0.0.1 \
    --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 1g \
    --cap-drop ALL --security-opt no-new-privileges \
    --entrypoint lighthouse "$LIGHTHOUSE" "$@" --help 2>&1
}
echo "== Inspect real Lighthouse key-generation CLI offline =="
WALLET_HELP="$(lighthouse_help account wallet create)"
VALIDATOR_HELP="$(lighthouse_help account validator create)"
MANAGER_HELP="$(lighthouse_help validator_manager create)"
for option in "--name" "--password-file"; do
  if ! grep -Fq -- "$option" <<< "$WALLET_HELP"; then
    echo "R20_OPERATOR_REFUSED: wallet create missing $option" >&2
    exit 2
  fi
done
for option in "--wallet-name" "--wallet-password" "--count"; do
  if ! grep -Fq -- "$option" <<< "$VALIDATOR_HELP"; then
    echo "R20_OPERATOR_REFUSED: account validator create missing $option" >&2
    exit 2
  fi
done
for option in "--mnemonic-path" "--eth1-withdrawal-address" "--testnet-dir"; do
  if ! grep -Fq -- "$option" <<< "$MANAGER_HELP"; then
    echo "R20_OPERATOR_REFUSED: validator manager missing $option" >&2
    exit 2
  fi
done
echo "R20_OFFLINE_LIGHTHOUSE_KEY_CLI_VERIFIED=true"
echo "R20_LIGHTHOUSE_WALLET_FLAGS=name,password-file"
echo "R20_LIGHTHOUSE_VALIDATOR_FLAGS=wallet-name,wallet-password,count"
echo "R20_LIGHTHOUSE_GENESIS_FLAGS=mnemonic-path,eth1-withdrawal-address,testnet-dir"

# An EOA private key is valid across EVM chains, so do NOT put real ETH into
# this research-only keystore or reuse it in any production wallet.
BASE="$HOME/.local/share/sse-r20-operator-private"
DIR="$BASE/withdrawal-keystore"
if [[ -e "$BASE" || -L "$BASE" ]]; then
  echo "R20_OPERATOR_REFUSED: operator private dir already exists, never overwrite" >&2
  exit 2
fi
echo
echo "This generates ONE real encrypted, TEST-ONLY EOA on this VM."
echo "Your password is entered through a hidden prompt; never share it."
echo "Back up BOTH the encrypted keystore file and its password OFFLINE."
echo "Do NOT put real ETH in this wallet, reuse it on other chains, or paste private files."
echo "This creates no BLS validator, genesis, test funds, or chain."
read -r -p "Type CREATE to generate the local encrypted wallet: " APPROVAL
if [[ "$APPROVAL" != CREATE ]]; then
  echo "R20_OPERATOR_REFUSED: wallet creation was not authorized" >&2
  exit 2
fi

mkdir -m 0700 -- "$BASE"
mkdir -m 0700 -- "$DIR"
LOG="$BASE/.cast-wallet-output-private"
# Cast new with a destination directory uses an encrypted keystore and hidden
# password prompt; capture any stdout PRIVATELY, never echo it.
if ! "$CAST" wallet new "$DIR" "sse-r20-withdrawal" > "$LOG"; then
  echo "R20_OPERATOR_REFUSED: Cast wallet generation failed, private log retained locally" >&2
  exit 2
fi
chmod 0600 "$LOG"
echo "== Report ONLY the public EOA address =="
if ! python3 -B tools/sse_pos_local_wallet_report.py "$DIR"; then
  echo "R20_OPERATOR_REFUSED: encrypted V3 keystore validation failed; do not share private files" >&2
  exit 2
fi
rm -- "$LOG"
echo "R20_LOCAL_ENCRYPTED_WITHDRAWAL_KEY_CREATED=true"
echo "R20_WALLET_SECRET_MATERIAL_NEVER_UPLOADED=true"
echo "R20_BLS_VALIDATORS_CREATED=false"
echo "R20_CHAIN31340_GENESIS_GENERATED=false"
echo "R20_PUBLIC_POS_NETWORK_DEPLOYED=false"
