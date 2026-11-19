#!/usr/bin/env bash
# Version-check genuine EL/CL executables BY OBSERVED IMMUTABLE IMAGE DIGEST.
# Developer VM checkpoint ONLY. No P2P, validator keys, state writes, ports.
# Docker sudo is temporary operator authorization, not SSE role admission.
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R19_CLIENT_REFUSED: exact 40-character Git SHA required" >&2
  exit 2
fi
EXPECTED_SHA="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$(git rev-parse --verify HEAD^{commit})" != "$EXPECTED_SHA" ]]; then
  echo "R19_CLIENT_REFUSED: git checkout does not match pinned SHA" >&2
  exit 2
fi
if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code; then
  echo "R19_CLIENT_REFUSED: tracked code modified on VM" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "R19_CLIENT_REFUSED: this checkpoint is for Linux x86_64" >&2
  exit 2
fi

# Use GitHub-committed actual VM4706 digests: NO mutable :tag pull.
REF_LINES="$(python3 -B tools/sse_pos_client_pins.py --refs)"
ID_LINES="$(python3 -B tools/sse_pos_client_pins.py --image-ids)"
mapfile -t REFS <<< "$REF_LINES"
mapfile -t IDS <<< "$ID_LINES"
if [[ "${#REFS[@]}" -ne 2 || "${#IDS[@]}" -ne 2 ]]; then
  echo "R19_CLIENT_REFUSED: pin manifest did not yield exactly two client images" >&2
  exit 2
fi

echo "R19_CLIENT_SOURCE_SHA=$EXPECTED_SHA"
echo "R19_CLIENT_IMAGE_DIGESTS_FROM_GITHUB_PINSET=true"
echo "R19_PUBLIC_POS_NETWORK_DEPLOYED=false"

# This developer-only Docker operation is intentionally not part of external
# role-only onboarding. Never grant docker-group membership to all participants.
sudo -n docker info --format 'docker_server={{.ServerVersion}} cgroup={{.CgroupVersion}}'

for i in 0 1; do
  if [[ "$i" -eq 0 ]]; then
    NAME="besu"
    VERSION_PREFIX="besu/v26.11.1/"
    ENTRY=()
  else
    NAME="lighthouse"
    VERSION_PREFIX="Lighthouse v8.3.3-"
    ENTRY=(--entrypoint lighthouse)
  fi
  REF="${REFS[$i]}"
  ID="${IDS[$i]}"
  echo "== Pinned immutable $NAME image =="
  echo "R19_${NAME^^}_EXPECTED_REF=$REF"
  sudo -n docker pull --platform linux/amd64 "$REF"
  ACTUAL_OS="$(sudo -n docker image inspect --format '{{.Os}}/{{.Architecture}}' "$REF")"
  ACTUAL_ID="$(sudo -n docker image inspect --format '{{.Id}}' "$REF")"
  if [[ "$ACTUAL_OS" != "linux/amd64" || "$ACTUAL_ID" != "$ID" ]]; then
    echo "R19_CLIENT_REFUSED: unexpected $NAME image platform or ID" >&2
    exit 2
  fi
  # --network none restricts traffic. Explicit /etc/hosts mapping prevents
  # Java Log4j's nonfatal UnknownHostException under isolated container DNS.
  # Do not hide stderr; FAIL if either version command logs errors.
  echo "== Actual $NAME version, no P2P or ports =="
  OUTPUT="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --hostname sse-local-probe \
    --add-host sse-local-probe:127.0.0.1 \
    --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 1g \
    --cap-drop ALL --security-opt no-new-privileges \
    "${ENTRY[@]}" "$REF" --version 2>&1)"
  printf '%s\n' "$OUTPUT"
  if [[ "$OUTPUT" == *"UnknownHostException"* || "$OUTPUT" == *" ERROR "* ||
        "$OUTPUT" != *"$VERSION_PREFIX"* ]]; then
    echo "R19_CLIENT_REFUSED: $NAME version or clean logging check failed" >&2
    exit 2
  fi
  echo "R19_${NAME^^}_VERIFIED_IMAGE_ID=$ACTUAL_ID"
done

echo "R19_NATIVE_EL_CL_VERSION_AND_PIN_CHECK_PASSED=true"
echo "R19_NATIVE_EL_CL_P2P_STARTED=false"
echo "R19_BEACON_GENESIS_CREATED=false"
echo "R19_INDEPENDENT_VALIDATOR_KEYS_CREATED=false"
echo "R19_PUBLIC_POS_NETWORK_DEPLOYED=false"
