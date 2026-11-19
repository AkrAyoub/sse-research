#!/usr/bin/env bash
# Canonical, no-GitHub-Actions verification for the cleaned SSE mainline.
# Unit/EVM tests are only source validation, NEVER public-network evidence.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo "Python 3 required" >&2; exit 2; }
command -v forge >/dev/null || { echo "Foundry forge required" >&2; exit 2; }
python3 -m unittest discover -s tests -p 'test_sse_pos_*.py' -v
python3 -m unittest discover -s tests -p 'test_sse_public_*.py' -v
python3 -m unittest discover -s tests -p 'test_sse_mainline_integrity.py' -v
forge build --sizes
forge test
echo "SSE_SOURCE_TESTS_PASSED=true"
echo "SSE_PUBLIC_INTERNET_NETWORK_PROVEN=false"
echo "SSE_INDEPENDENT_VALIDATOR_STAKING_PROVEN=false"
echo "SSE_REAL_CROSS_HOST_SLA_PROVEN=false"
