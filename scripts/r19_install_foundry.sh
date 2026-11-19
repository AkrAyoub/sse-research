#!/usr/bin/env bash
# R19 local-only, SHA-256-pinned official Foundry EVM test toolchain.
# NO sudo, curl|bash, Docker socket, PATH mutation or blockchain launch.
# Release metadata (2026-11-02):
# https://api.github.com/repos/foundry-rs/foundry/releases/tags/v1.9.0
# The digest is the official GitHub release asset's immutable SHA-256.
set -euo pipefail
umask 077

VERSION="v1.9.0"
ARCHIVE_NAME="foundry_${VERSION}_linux_amd64.tar.gz"
ARCHIVE_SHA256="8d17599b42e3139f1a9c171be3798c4ed8e743ae17b84cc3435e57bf2a51ae99"
RELEASE_URL="https://github.com/foundry-rs/foundry/releases/download/${VERSION}/${ARCHIVE_NAME}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "R19_FOUNDRY_REFUSED: this checked artifact is only for Linux x86_64" >&2
  exit 2
fi
for cmd in curl sha256sum tar mktemp; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "R19_FOUNDRY_REFUSED: missing prerequisite $cmd" >&2
    exit 2
  fi
done

BASE="$HOME/.local/share/sse-r19-toolchains"
DEST="$BASE/foundry-${VERSION}"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  echo "R19_FOUNDRY_REFUSED: installation already exists (do not overwrite): $DEST" >&2
  exit 2
fi
mkdir -p -- "$BASE"
WORK="$(mktemp -d)"
STAGE="$(mktemp -d "$BASE/.foundry-${VERSION}.XXXXXXXX")"
cleanup() { rm -rf -- "$WORK" "$STAGE"; }
trap cleanup EXIT

ARCHIVE="$WORK/$ARCHIVE_NAME"
echo "R19_FOUNDRY_RELEASE=$VERSION"
echo "R19_FOUNDRY_SOURCE=$RELEASE_URL"
echo "R19_FOUNDRY_EXPECTED_ARCHIVE_SHA256=$ARCHIVE_SHA256"
curl --fail --location --silent --show-error \
  --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 20 --max-time 600 \
  --output "$ARCHIVE" "$RELEASE_URL"

printf '%s  %s\n' "$ARCHIVE_SHA256" "$ARCHIVE" | sha256sum --check --status || {
  echo "R19_FOUNDRY_REFUSED: OFFICIAL RELEASE ARCHIVE HASH MISMATCH" >&2
  exit 2
}
echo "R19_FOUNDRY_ARCHIVE_SHA256_VERIFIED=true"

# Four executable files only. Reject surprising archive paths/extra files.
mapfile -t ENTRIES < <(tar -tzf "$ARCHIVE")
if [[ "${#ENTRIES[@]}" -ne 4 ]]; then
  echo "R19_FOUNDRY_REFUSED: unexpected official archive file count" >&2
  exit 2
fi
for binary in forge cast anvil chisel; do
  present=false
  for item in "${ENTRIES[@]}"; do
    if [[ "${item#./}" == "$binary" ]]; then present=true; fi
  done
  if [[ "$present" != true ]]; then
    echo "R19_FOUNDRY_REFUSED: missing expected binary $binary" >&2
    exit 2
  fi
done
tar -xzf "$ARCHIVE" --no-same-owner --no-same-permissions -C "$STAGE"
for binary in forge cast anvil chisel; do
  if [[ ! -f "$STAGE/$binary" || -L "$STAGE/$binary" ]]; then
    echo "R19_FOUNDRY_REFUSED: expected file absent/nonregular: $binary" >&2
    exit 2
  fi
  chmod 0755 -- "$STAGE/$binary"
done
mv -- "$STAGE" "$DEST"

echo "== installed release =="
"$DEST/forge" --version
echo "== executable digests =="
sha256sum "$DEST/forge" "$DEST/cast" "$DEST/anvil" "$DEST/chisel"
echo "SSE_R19_FOUNDRY_INSTALLED=$DEST"
echo "SSE_R19_FOUNDRY_EVM_TESTS_EXECUTED=false"
echo "SSE_R19_PUBLIC_POS_NETWORK_DEPLOYED=false"
