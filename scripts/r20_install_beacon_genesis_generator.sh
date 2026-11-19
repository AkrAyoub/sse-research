#!/usr/bin/env bash
# R20: install a hash-pinned real Beacon genesis-state generator (developer VM).
# Never use a shared genesis mnemonic; accept public operator validators only.
# Software install and --help ONLY: this does not produce or launch a genesis.
set -euo pipefail
umask 077

VERSION="v0.0.8"
FILE="eth-beacon-genesis_0.0.8_linux_amd64.tar.gz"
SHA256="73b5e33ed309e7bd98bd5f115b032a462b7ed8f1b67b204ac2000016c2f1856b"
# Binary SHA-256 observed on VM4706 after verifying the official release archive.
BIN_SHA256="5ee29389cb29e8a1ace8cfc83ff30a1726409152e88cf07681764740ca9244d2"
URL="https://github.com/ethpandaops/eth-beacon-genesis/releases/download/$VERSION/$FILE"
BASE="$HOME/.local/share/sse-r19-toolchains"
DEST="$BASE/eth-beacon-genesis-$VERSION"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "R20_GENESIS_TOOL_REFUSED: pinned release only for Linux x86_64" >&2
  exit 2
fi
for cmd in curl sha256sum tar mktemp; do
  command -v "$cmd" >/dev/null || {
    echo "R20_GENESIS_TOOL_REFUSED: missing $cmd" >&2
    exit 2
  }
done
# Re-running the same SHA-pinned tool installer must verify, not re-download.
# Never overwrite any preexisting installation or trust an unverified binary.
verify_binary() {
  local binary="$1"
  if [[ -L "$binary" || ! -f "$binary" || ! -x "$binary" ]]; then
    echo "R20_GENESIS_TOOL_REFUSED: missing, symlinked or nonexecutable binary: $binary" >&2
    return 2
  fi
  if ! printf '%s  %s\\n' "$BIN_SHA256" "$binary" | sha256sum --check --status; then
    echo "R20_GENESIS_TOOL_REFUSED: expected generator binary SHA256 mismatch" >&2
    return 2
  fi
  echo "R20_GENESIS_BINARY_SHA256_VERIFIED=true"
}

if [[ -e "$DEST" || -L "$DEST" ]]; then
  if [[ -L "$DEST" || ! -d "$DEST" ]]; then
    echo "R20_GENESIS_TOOL_REFUSED: existing tool location is not a normal directory" >&2
    exit 2
  fi
  verify_binary "$DEST/eth-genesis-state-generator"
  echo "R20_GENESIS_TOOL_REUSED_VERIFIED=true"
  echo "== Existing trusted Beacon genesis tool help (no chain generated) =="
  "$DEST/eth-genesis-state-generator" --help
  echo "R20_GENESIS_TOOL_PATH=$DEST/eth-genesis-state-generator"
  sha256sum "$DEST/eth-genesis-state-generator"
  echo "R20_GENESIS_SSZ_GENERATED=false"
  echo "R20_INDEPENDENT_BLS_KEYS_EXCHANGED=false"
  echo "R20_PUBLIC_POS_NETWORK_DEPLOYED=false"
  exit 0
fi

mkdir -p -- "$BASE"
WORK="$(mktemp -d)"
STAGE="$(mktemp -d "$BASE/.eth-beacon-genesis-$VERSION.XXXXXXXX")"
cleanup() { rm -rf -- "$WORK" "$STAGE"; }
trap cleanup EXIT

echo "R20_RELEASE_URL=$URL"
echo "R20_RELEASE_SHA256_EXPECTED=$SHA256"
ARCHIVE="$WORK/$FILE"
curl --fail --location --silent --show-error \
  --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 20 --max-time 300 \
  --output "$ARCHIVE" "$URL"
printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum --check --status || {
  echo "R20_GENESIS_TOOL_REFUSED: release archive SHA256 mismatch" >&2
  exit 2
}
echo "R20_RELEASE_SHA256_VERIFIED=true"

# The pinned upstream source has exactly one cmd/eth-genesis-state-generator
# executable. Do not extract the whole archive, symlinks or surprise paths.
LIST="$(tar -tzf "$ARCHIVE")" || {
  echo "R20_GENESIS_TOOL_REFUSED: corrupt archive" >&2
  exit 2
}
ENTRY=""
while IFS= read -r p; do
  clean="${p#./}"
  if [[ "$clean" == "eth-genesis-state-generator" ]]; then
    if [[ -n "$ENTRY" ]]; then
      echo "R20_GENESIS_TOOL_REFUSED: duplicate target binary" >&2
      exit 2
    fi
    ENTRY="$p"
  fi
done <<< "$LIST"
if [[ -z "$ENTRY" ]]; then
  echo "R20_GENESIS_TOOL_REFUSED: pinned archive missing expected CLI binary" >&2
  exit 2
fi

# Output streaming avoids archive-controlled paths in local filesystem.
tar -xzOf "$ARCHIVE" -- "$ENTRY" > "$STAGE/eth-genesis-state-generator"
if [[ ! -s "$STAGE/eth-genesis-state-generator" || -L "$STAGE/eth-genesis-state-generator" ]]; then
  echo "R20_GENESIS_TOOL_REFUSED: invalid extracted generator binary" >&2
  exit 2
fi
chmod 0755 "$STAGE/eth-genesis-state-generator"
verify_binary "$STAGE/eth-genesis-state-generator"
echo "== Official real Beacon genesis tool help (not generating a chain) =="
"$STAGE/eth-genesis-state-generator" --help
mv -- "$STAGE" "$DEST"
echo "R20_GENESIS_TOOL_PATH=$DEST/eth-genesis-state-generator"
sha256sum "$DEST/eth-genesis-state-generator"
echo "R20_GENESIS_SSZ_GENERATED=false"
echo "R20_INDEPENDENT_BLS_KEYS_EXCHANGED=false"
echo "R20_PUBLIC_POS_NETWORK_DEPLOYED=false"
