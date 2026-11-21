#!/usr/bin/env bash
# R28: validate EXISTING encrypted Cast UTC-V3 wallet; NEVER create/overwrite.
# A saved keystore may omit embedded address (eth-keystore without geth-compat).
# Ask owner for password through pinned Cast hidden prompt; print address ONLY.
set -euo pipefail
umask 077
set +x

refuse() { echo "R28_EXISTING_EOA_REFUSED: $*" >&2; exit 2; }
if [[ $# -ne 2 || ! "$1" =~ ^[0-9a-f]{40}$ ||
      ! "$2" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
  refuse "exact Git SHA and known PUBLIC EOA address required"
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse --verify HEAD^{commit})" == "$1" ]] ||
  refuse "source Git SHA mismatch"
git diff --quiet --exit-code && git diff --cached --quiet --exit-code ||
  refuse "tracked checkout was locally modified"
[[ -t 0 && -t 2 ]] || refuse "owner terminal required for hidden password"
[[ "$(id -u)" != 0 ]] || refuse "do not inspect owner keys as root"
DIR="$HOME/.local/share/sse-r20-operator-private/withdrawal-keystore"
FILE="$DIR/sse-r20-withdrawal"
[[ -d "$DIR" && ! -L "$DIR" && -f "$FILE" && ! -L "$FILE" ]] ||
  refuse "existing owner-local encrypted keystore not found"
[[ "$(stat -c '%u' "$DIR")" == "$(id -u)" &&
   "$(stat -c '%u' "$FILE")" == "$(id -u)" ]] ||
  refuse "keystore must be owned by invoking owner"
[[ "$(stat -c '%a' "$DIR")" == 700 &&
   "$(stat -c '%a' "$FILE")" == 600 ]] ||
  refuse "keystore must be private 0700 directory with 0600 file"

CAST="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0/cast"
CAST_SHA="cae9d8a3e9a2c2f121879f39498472fee8a767318fc26ff7e3c73908133fdaa4"
[[ -f "$CAST" && ! -L "$CAST" && -x "$CAST" ]] ||
  refuse "pinned Cast v1.9.0 missing"
printf '%s  %s\n' "$CAST_SHA" "$CAST" | sha256sum --check --status ||
  refuse "pinned Cast v1.9.0 SHA256 mismatch"
# Validates the exact encrypted V3 envelope, not whether its password works.
# This prints only public address if EMBEDDED in JSON (often none).
python3 -B tools/sse_pos_local_wallet_report.py "$DIR" ||
  refuse "existing encrypted V3 envelope failed owner-only validation"
HELP="$("$CAST" wallet address --help)" ||
  refuse "pinned Cast local address command help failed"
grep -Fq -- "--keystore" <<< "$HELP" ||
  refuse "Cast wallet address does not support --keystore"
echo "R28_EXISTING_CAST_KESTORE_STRUCTURE_ACCEPTED=true"
echo "Enter the EXISTING keystore password at Cast's hidden prompt."
echo "The next step unlocks locally to derive ONLY the PUBLIC EOA address."
echo "It does NOT create, overwrite, export, or broadcast a secret or transaction."
# Prevent shell exports from silently selecting some unrelated signer.
# stdout is held in memory and validated as only a 20-byte public address.
VERIFIED="$(env -u CAST_UNSAFE_PASSWORD -u CAST_PASSWORD \
  -u ETH_PRIVATE_KEY -u PRIVATE_KEY "$CAST" wallet address --keystore "$FILE")" ||
  refuse "existing keystore could not be locally unlocked by pinned Cast"
[[ "$VERIFIED" =~ ^0x[0-9a-fA-F]{40}$ ]] ||
  refuse "wallet address command did not return just one public EOA"
[[ "${VERIFIED,,}" == "${2,,}" ]] ||
  refuse "owner-provided public address does NOT match encrypted key"
echo "R28_EXISTING_ENCRYPTED_WITHDRAWAL_KEY_PRESERVED=true"
echo "R28_WITHDRAWAL_ADDRESS_VERIFIED_BY_PINNED_CAST=true"
echo "R28_VERIFIED_PUBLIC_WITHDRAWAL_ADDRESS=$VERIFIED"
echo "R28_BLS_VALIDATOR_SIGNING_KEYS_CREATED=false"
echo "R28_NATIVE_CHAIN31340_LAUNCHED=false"
