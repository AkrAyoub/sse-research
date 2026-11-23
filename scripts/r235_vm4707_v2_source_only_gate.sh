#!/usr/bin/env bash
# R235: VM4707's source-only return-time V2 integration gate.
# Does NOT contact live node, sign, unlock, broadcast, touch Docker or BLS.
set -euo pipefail
set +x
if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R235_REFUSED: supply the immutable reviewed 40-hex Git SHA" >&2
  exit 2
fi
SHA="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$(git rev-parse HEAD)" != "$SHA" ]] ||
   [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "R235_REFUSED: wrong SHA or dirty tracked source tree" >&2
  exit 2
fi
export PATH="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0:$PATH"
echo "== R235 EXACT SOURCE =="
git rev-parse HEAD
echo "== V2 FOUNDRY =="
forge --version
echo "== R226-R229 PYTHON ABI / FINALITY / EIP-712 SOURCE REGRESSIONS =="
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r22*.py' -v
echo "== R231-R234 TRUE HTTP-SOCKET TESTS (LOCAL ONLY; NOT REMOTE SLA) =="
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r23*.py' -v
echo "== R242 OWNER-APPROVED TX POLICY TESTS (MOCKED, NEVER BROADCAST) =="
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r242_v2_owner_local_send.py' -v
echo "== R201 ORIGINAL GENESIS READ-ONLY POLICY MOCK TESTS =="
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r201_v2_readonly_live_chain_gate.py' -v
echo "== R206 MANIFEST AUDIT POLICY MOCK TESTS =="
python3 -B -m unittest discover -s tests -p 'test_sse_pos_r206_adaptive_v2_deployment_audit.py' -v
echo "== FULL PYTHON PROJECT SUITE =="
python3 -B -m unittest discover -s tests
echo "== EXACT SOURCE V2 EIP-170 / EIP-3860 SIZE =="
forge build --sizes
echo "== ADAPTIVE V2 CONTRACT TESTS =="
forge test --match-contract SSEAdaptiveMarketV2Test -vv
echo "== FULL FOUNDRY PROJECT SUITE =="
forge test -q
echo "R235_SOURCE_ONLY_GATES_COMPLETED=true"
