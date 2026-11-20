#!/usr/bin/env bash
# R27: generate ONE genuinely random owner-local Lighthouse EIP-2386 HD
# wallet, entirely offline, without ever printing its BIP39 mnemonic.
# Does NOT create validator signing keys, network config, native funds,
# chain Genesis, or independent operators. Human approval is mandatory.
set -euo pipefail
umask 077
set +x

refuse() { echo "R27_BLS_HD_WALLET_REFUSED: $*" >&2; exit 2; }
if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  refuse "exact immutable Git source SHA argument required"
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse --verify HEAD^{commit})" == "$1" ]] || refuse "Git commit mismatch"
git diff --quiet --exit-code && git diff --cached --quiet --exit-code ||
  refuse "locally modified tracked source"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
  refuse "only reviewed Linux x86_64 private host supported"
[[ -t 0 && -t 2 ]] || refuse "interactive owner approval TTY required"
[[ "$(id -u)" != 0 ]] || refuse "do not run as root; use owner account"

LIGHTHOUSE="$(python3 -B tools/sse_pos_client_pins.py --refs | tail -n 1)"
EXPECTED_ID="$(python3 -B tools/sse_pos_client_pins.py --image-ids | tail -n 1)"
ACTUAL_ID="$(sudo -n docker image inspect --format '{{.Id}}' "$LIGHTHOUSE")" ||
  refuse "pinned Lighthouse image unavailable"
[[ "$ACTUAL_ID" == "$EXPECTED_ID" ]] || refuse "Lighthouse image ID differs from pin"

BASE="$HOME/.local/share/sse-r27-bls-operator-private"
[[ ! -e "$BASE" && ! -L "$BASE" ]] ||
  refuse "operator private wallet directory already exists; never overwrite"

# Read-only native CLI flag verification with no secret mount or network.
lighthouse_help() {
  sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --hostname sse-hd-wallet-help \
    --add-host sse-hd-wallet-help:127.0.0.1 \
    --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 512m \
    --cap-drop ALL --security-opt no-new-privileges \
    --entrypoint lighthouse "$LIGHTHOUSE" "$@" --help 2>&1
}
WALLET_HELP="$(lighthouse_help account wallet create)" ||
  refuse "Lighthouse account wallet create help failed"
for flag in "--name" "--password-file" "--mnemonic-output-path"; do
  grep -Fq -- "$flag" <<< "$WALLET_HELP" ||
    refuse "pinned Lighthouse wallet create lacks $flag"
done
PARENT_HELP="$(lighthouse_help account wallet)" ||
  refuse "Lighthouse account wallet help failed"
grep -Fq -- "--wallet-dir" <<< "$PARENT_HELP" ||
  refuse "pinned Lighthouse account wallet lacks --wallet-dir"

echo "R27_PINNED_LIGHTHOUSE_OFFLINE_HD_WALLET_CLI_VERIFIED=true"
echo
echo "This will create ONE encrypted Ethereum BLS HD parent wallet for"
echo "chain31340 RESEARCH USE ONLY, under a private 0700 directory."
echo "The upstream Lighthouse CLI prints the BIP39 mnemonic to stdout;"
echo "this script discards stdout and separately stores the mnemonic in"
echo "a private 0600 recovery file. Do not display, upload, or paste it."
echo "Back up offline: wallet directory, generated password file, and"
echo "mnemonic recovery file. Do not use this wallet on Mainnet."
echo "No validator signing keys, validators, genesis, or chain are started."
read -r -p "Type CREATE-BLS-HD-WALLET to authorize: " APPROVAL
[[ "$APPROVAL" == "CREATE-BLS-HD-WALLET" ]] ||
  refuse "explicit operator approval not provided"

mkdir -m 0700 -- "$BASE" || refuse "cannot create owner private directory"
LOG="$BASE/.initialization-stderr-private"
: > "$LOG"
chmod 0600 "$LOG"
# --network none; --user real owner UID; no remote API/secret mount.
# Mnemonic is written to /owner/recovery.mnemonic with owner 0600,
# stdout ALWAYS /dev/null (upstream CLI would otherwise print mnemonic).
if ! sudo -n docker run --rm --pull never --platform linux/amd64 \
  --network none --hostname sse-hd-wallet-owner \
  --add-host sse-hd-wallet-owner:127.0.0.1 \
  --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --user "$(id -u):$(id -g)" --cpus 1 --memory 1g --pids-limit 128 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$BASE,target=/owner" \
  --entrypoint lighthouse "$LIGHTHOUSE" \
  account wallet --wallet-dir /owner/wallets create \
  --name sse31340-operator --password-file /owner/owner-wallet.pass \
  --mnemonic-output-path /owner/recovery.mnemonic \
  > /dev/null 2> "$LOG"; then
  refuse "upstream Lighthouse failed; PRIVATE stderr kept owner-only on disk"
fi

for secret in "$BASE/owner-wallet.pass" "$BASE/recovery.mnemonic"; do
  if [[ -L "$secret" || ! -f "$secret" || ! -s "$secret" ||
        "$(stat -c '%u' "$secret")" != "$(id -u)" ||
        "$(stat -c '%a' "$secret")" != 600 ]]; then
    refuse "new private artifact has unexpected owner/mode; inspect LOCALLY ONLY"
  fi
done
[[ -d "$BASE/wallets" && ! -L "$BASE/wallets" ]] ||
  refuse "encrypted HD wallet directory not created"
rm -- "$LOG"
echo "R27_ENCRYPTED_HD_WALLET_CREATED_ON_OWNER_VM=true"
echo "R27_BIP39_MNEMONIC_WAS_NEVER_PRINTED=true"
echo "R27_PRIVATE_WALLET_ARTIFACTS_MUST_BE_BACKED_UP_OFFLINE=true"
echo "R27_BLS_VALIDATOR_SIGNING_KEYS_CREATED=false"
echo "R27_CHAIN31340_GENESIS_GENERATED=false"
echo "R27_PUBLIC_POS_NETWORK_DEPLOYED=false"
