#!/usr/bin/env bash
# R19: exact-revision, unprivileged, offline-first first-boot SOURCE checks.
# This is NOT a network installer, validator admission, faucet, or chain launch.
# Git fetch/authentication must be performed separately, through a reviewed
# read-only developer credential while the source repository remains private.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: bash scripts/r19_verify_fresh_host.sh <exact-40-character-commit-sha> <comma-separated-roles>" >&2
  exit 2
fi

EXPECTED_SHA="$1"
ROLES="$2"
if [[ ! "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R19_REFUSED: expected a lowercase 40-character Git commit SHA" >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ACTUAL_SHA="$(git rev-parse --verify HEAD^{commit})"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]]; then
  echo "R19_REFUSED: checked-out Git commit does not match required SHA" >&2
  echo "expected=$EXPECTED_SHA actual=$ACTUAL_SHA" >&2
  exit 2
fi
if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code; then
  echo "R19_REFUSED: tracked working tree has local changes" >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
echo "SSE_R19_SOURCE_SHA=$ACTUAL_SHA"
echo "SSE_R19_ACTUAL_PUBLIC_POS_JOIN_VERIFIED=false"
echo "SSE_R19_OWNERLESS_FAUCET_DEPLOYED=false"
echo "SSE_R19_NODE_PUBLIC_HTTPS_UI_VERIFIED=false"
echo "== Python 3 version =="
python3 --version
echo "== Source regression tests (Python stdlib) =="
python3 -m unittest discover -s tests -p 'test_sse_fresh_host_probe.py' -v
echo "SSE_R19_FRESH_HOST_PYTHON_TESTS_PASSED=true"

echo "== Local-only host inventory, no network or host mutation =="
python3 tools/sse_fresh_host_probe.py --roles "$ROLES"
echo "== Foundry build prerequisite status =="
if command -v forge >/dev/null 2>&1; then
  forge --version
  echo "SSE_R19_FOUNDRY_PRESENT=true"
  echo "SSE_R19_FOUNDRY_TESTS_EXECUTED=false"
else
  echo "SSE_R19_FOUNDRY_PRESENT=false"
  echo "SSE_R19_FOUNDRY_TESTS_EXECUTED=false"
fi
echo "SSE_R19_HOST_INVENTORY_COMPLETE=true"
