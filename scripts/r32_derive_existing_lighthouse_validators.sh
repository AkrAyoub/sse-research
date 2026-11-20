#!/usr/bin/env bash
# R32: offline derivation of ACTUAL Lighthouse EIP-2335 voting keys from the
# EXISTING owner-encrypted EIP-2386 HD wallet. Never creates a new mnemonic,
# wallet or execution EOA; never starts any blockchain client or P2P port.
# Consent and explicit OFFLINE BACKUP acknowledgement are separate.
set -euo pipefail
umask 077
set +x

refuse() { printf 'R32_VALIDATOR_DERIVATION_REFUSED: %s\n' "$*" >&2; exit 2; }
if [[ $# -ne 3 || ! "$1" =~ ^[0-9a-f]{40}$ ||
      ! "$2" =~ ^[1-9][0-9]*$ ||
      ! "$3" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
  refuse "usage: <EXACT_GITHUB_SHA> <POSITIVE_LOCAL_BATCH_COUNT> <VERIFIED_PUBLIC_TEST_EOA>"
fi
# One VM batch is resource-bounded, but there is NO network role/validator cap.
COUNT="$2"
(( COUNT >= 1 && COUNT <= 64 )) ||
  refuse "resource-limited single-host lab batch must have 1..64 keys; not a global validator limit"
[[ "${3,,}" != "0x0000000000000000000000000000000000000000" ]] ||
  refuse "withdrawal address cannot be zero"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse --verify HEAD^{commit})" == "$1" ]] ||
  refuse "Git source mismatch"
git diff --quiet --exit-code && git diff --cached --quiet --exit-code ||
  refuse "tracked source changes on VM are prohibited"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
  refuse "reviewed owner-local x86_64 Linux only"
[[ "$(id -u)" != 0 ]] || refuse "owner account required, not root"
[[ -t 0 && -t 2 ]] || refuse "interactive owner terminal required"

BASE="$HOME/.local/share/sse-r27-bls-operator-private"
[[ -d "$BASE" && ! -L "$BASE" && "$(stat -c '%u:%a' "$BASE")" == "$(id -u):700" ]] ||
  refuse "existing private Lighthouse HD wallet parent must be owner-owned 0700"
for file in "$BASE/owner-wallet.pass" "$BASE/recovery.mnemonic"; do
  [[ -f "$file" && ! -L "$file" &&
     "$(stat -c '%u:%a' "$file")" == "$(id -u):600" && -s "$file" ]] ||
    refuse "existing real HD wallet secret missing or unsafe; DO NOT recreate"
done
[[ -d "$BASE/wallets" && ! -L "$BASE/wallets" &&
   "$(stat -c '%u' "$BASE/wallets")" == "$(id -u)" ]] ||
  refuse "real encrypted Lighthouse wallet directory missing"
[[ ! -e "$BASE/validators" && ! -L "$BASE/validators" &&
   ! -e "$BASE/secrets" && ! -L "$BASE/secrets" &&
   ! -e "$BASE/public-validator-contribution.json" &&
   ! -L "$BASE/public-validator-contribution.json" ]] ||
  refuse "existing validator/slashing-public output found; NEVER overwrite or run duplicate derivation"

LIGHTHOUSE="$(python3 -B tools/sse_pos_client_pins.py --refs | tail -n 1)"
EXPECTED_ID="$(python3 -B tools/sse_pos_client_pins.py --image-ids | tail -n 1)"
ACTUAL_ID="$(sudo -n docker image inspect --format '{{.Id}}' "$LIGHTHOUSE")" ||
  refuse "pinned Lighthouse Docker image missing"
[[ "$EXPECTED_ID" == "$ACTUAL_ID" ]] ||
  refuse "pinned Lighthouse container identity differs"

lighthouse_help() {
  sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --hostname sse-validator-help \
    --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 512m \
    --cap-drop ALL --security-opt no-new-privileges \
    --entrypoint lighthouse "$LIGHTHOUSE" "$@" --help 2>&1
}
PARENT_HELP="$(lighthouse_help account validator)" ||
  refuse "Lighthouse account validator parent help unavailable"
CREATE_HELP="$(lighthouse_help account validator create)" ||
  refuse "Lighthouse validator create help unavailable"
for flag in "--validator-dir"; do
  grep -Fq -- "$flag" <<< "$PARENT_HELP" ||
    refuse "pinned Lighthouse validator parent lacks $flag"
done
for flag in "--wallets-dir" "--secrets-dir" "--wallet-name" "--wallet-password" "--count"; do
  grep -Fq -- "$flag" <<< "$CREATE_HELP" ||
    refuse "pinned Lighthouse validator create lacks $flag"
done
echo "R32_PINNED_OFFLINE_LIGHTHOUSE_VALIDATOR_CLI_VERIFIED=true"
echo "R32_EXISTING_HD_WALLET_PRESERVED=true"
echo
echo "Derive $COUNT REAL encrypted BLS voting signing key(s) from your EXISTING"
echo "Lighthouse HD wallet, OFFLINE, on this single owner VM."
echo "The separate withdrawal EOA will be represented by PUBLIC 0x01"
echo "genesis credentials; new Ethereum Mainnet deposit data generated"
echo "by the generic Lighthouse CLI MUST NEVER be broadcast or reused."
echo "Owner must independently verify the provided TEST-only EOA address."
echo "Backup the existing encrypted HD wallet, its password AND recovery"
echo "mnemonic OFFLINE, before deriving any validators. This script cannot"
echo "verify your external backup media. Never share keys/passwords here."
echo "The operator's BLS keys are NOT independent organizations."
read -r -p "Type BACKUP-CONFIRMED only if offline HD recovery backups exist: " BACKUP
[[ "$BACKUP" == "BACKUP-CONFIRMED" ]] ||
  refuse "offline mnemonic/password/encrypted-wallet backup not acknowledged"
read -r -p "Type DERIVE-BLS-VALIDATORS to authorize key derivation: " APPROVAL
[[ "$APPROVAL" == "DERIVE-BLS-VALIDATORS" ]] ||
  refuse "new validator-signing-key derivation not authorized"

# Only after BOTH approvals can real secret-bearing files be created.
# No rollback/overwrite after partial key creation. Failed runs keep owner
# files for human diagnosis; do not re-run this creator automatically.
LOG="$BASE/.validator-derivation-stderr-private"
[[ ! -e "$LOG" && ! -L "$LOG" ]] ||
  refuse "previous private derivation log exists; stop instead of overwriting"
(umask 077; : > "$LOG")
if ! sudo -n docker run --rm --pull never --platform linux/amd64 \
  --network none --hostname sse-offline-owner-validator \
  --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --user "$(id -u):$(id -g)" --cpus 2 --memory 2g --pids-limit 128 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$BASE,target=/owner" \
  --entrypoint lighthouse "$LIGHTHOUSE" \
  account validator --validator-dir /owner/validators create \
  --wallets-dir /owner/wallets --secrets-dir /owner/secrets \
  --wallet-name sse31340-operator \
  --wallet-password /owner/owner-wallet.pass \
  --count "$COUNT" > /dev/null 2> "$LOG"; then
  refuse "Lighthouse validator derivation failed; preserve owner-only files and PRIVATE log; DO NOT repeat"
fi

[[ -d "$BASE/validators" && -d "$BASE/secrets" ]] ||
  refuse "expected real validator/slashing-protection directories missing"
# Protect generated voting keystores AND the genuine slashing-protection database.
# Lighthouse upstream creates keystore files with create_new, but the
# container umask might be less strict than 077. Private parent is 0700.
# Refuse symlink trees before normalizing access for local-only exporter.
if [[ -n "$(find "$BASE/validators" "$BASE/secrets" -type l -print -quit)" ]]; then
  refuse "unexpected symlink in newly generated validator directory"
fi
find "$BASE/validators" "$BASE/secrets" -type d -exec chmod 700 -- {} +
find "$BASE/validators" "$BASE/secrets" -type f -exec chmod 600 -- {} +
[[ "$(stat -c '%u' "$BASE/validators")" == "$(id -u)" ]] ||
  refuse "validator directory has unexpected owner"

# PUBLIC output is created from ACTUAL new encrypted voting key metadata,
# without touching mnemonic or opening the private voting keystores.
# Explicit chain31340 withdrawal credentials bind to the owner-provided
# TEST-only public EOA. The generic CLI deposit_data is NOT used.
if ! python3 -B tools/sse_pos_public_keystore_export.py \
  --keystore-dir "$BASE/validators" \
  --operator-id operator-own-one \
  --withdrawal-address "$3" \
  --output "$BASE/public-validator-contribution.json" > /dev/null; then
  refuse "public-only metadata export failed; real validator keys may exist; preserve for review"
fi
# Derivation completed with private file paths/ciphertext never printed.
rm -- "$LOG"
echo "R32_REAL_OWNER_BLS_VOTING_KEYSTORES_CREATED=true"
echo "R32_BLS_VOTING_KEY_COUNT=$COUNT"
echo "R32_PRIVATE_SLASHING_PROTECTION_RETAINED=true"
echo "R32_PUBLIC_GENESIS_CONTRIBUTION_CREATED=true"
echo "R32_RECOVERY_BACKUP_ATTESTED_BY_OWNER=true"
echo "R32_BLS_PUBLIC_SUBGROUP_VERIFIED=false"
echo "R32_EL_CL_GENESIS_CREATED=false"
echo "R32_CHAIN31340_RUNNING=false"
echo "R32_INDEPENDENT_OPERATOR_FAULT_DOMAINS=1"
