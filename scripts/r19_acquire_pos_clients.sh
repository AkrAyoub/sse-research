#!/usr/bin/env bash
# R19 first native EL+CL client acquisition checkpoint (no network launch).
# For the authorized developer VM only. The finished external installer
# must not require sudo / privileged Docker socket or private GitHub access.
set -euo pipefail
umask 077

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R19_CLIENTS_REFUSED: supply exact 40-character Git commit SHA" >&2
  exit 2
fi
EXPECTED_SHA="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ACTUAL_SHA="$(git rev-parse --verify HEAD^{commit})"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]]; then
  echo "R19_CLIENTS_REFUSED: checked-out Git SHA mismatch" >&2
  exit 2
fi
if ! git diff --quiet --exit-code || ! git diff --cached --quiet --exit-code; then
  echo "R19_CLIENTS_REFUSED: locally modified tracked source" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "R19_CLIENTS_REFUSED: developer VM image test requires Linux x86_64" >&2
  exit 2
fi
for cmd in git sudo docker grep; do
  command -v "$cmd" >/dev/null || {
    echo "R19_CLIENTS_REFUSED: missing tool $cmd" >&2
    exit 2
  }
done

# Version tags are only a DISCOVERY step. Record the resolved immutable digest
# and pin it in GitHub BEFORE using any of these clients to launch a chain.
BESU_TAG="hyperledger/besu:26.11.1"
LIGHTHOUSE_TAG="sigp/lighthouse:v8.3.3"
echo "R19_CLIENT_SOURCE_SHA=$EXPECTED_SHA"
echo "R19_CLIENT_IMAGES_PINNED_BY_DIGEST=false"
echo "R19_PUBLIC_POS_NETWORK_DEPLOYED=false"
echo "R19_CLIENT_VERSIONS=Besu-26.11.1,Lighthouse-v8.3.3"

if ! sudo -n docker info --format 'docker_server={{.ServerVersion}} cgroups={{.CgroupVersion}}'; then
  echo "R19_CLIENTS_REFUSED: explicit operator sudo Docker access unavailable" >&2
  exit 2
fi

verify_and_capture() {
  local tag="$1" repo="$2" name="$3" digest="" ref osarch
  echo "== Pull official tagged $name image (developer checkpoint) =="
  sudo -n docker pull --platform linux/amd64 "$tag"
  osarch="$(sudo -n docker image inspect --format '{{.Os}}/{{.Architecture}}' "$tag")"
  if [[ "$osarch" != "linux/amd64" ]]; then
    echo "R19_CLIENTS_REFUSED: unexpected $name image OS/architecture: $osarch" >&2
    return 2
  fi
  while IFS= read -r ref; do
    if [[ "$ref" =~ ^${repo}@sha256:[a-f0-9]{64}$ ]]; then
      if [[ -n "$digest" ]]; then
        echo "R19_CLIENTS_REFUSED: multiple candidate $name image digests" >&2
        return 2
      fi
      digest="$ref"
    fi
  done < <(sudo -n docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$tag")
  if [[ -z "$digest" ]]; then
    echo "R19_CLIENTS_REFUSED: no immutable $name RepoDigest" >&2
    return 2
  fi
  # No writable mounts, Internet access, ports, validator keys or host shell.
  # A version command is actual client software, NOT a running PoS node.
  # Besu 26.11.1 ships its own besu-entry.sh wrapper: preserve it so
  # upstream JVM security options remain active (do not override entrypoint).
  # Lighthouse's official image documents its binary as "lighthouse".
  local -a entrypoint_args=()
  if [[ "$name" == "lighthouse" ]]; then
    entrypoint_args=(--entrypoint lighthouse)
  fi
  echo "== $name version from immutable digest with no network =="
  sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 1g \
    --cap-drop ALL --security-opt no-new-privileges \
    "${entrypoint_args[@]}" "$digest" --version
  echo "R19_${name^^}_IMAGE_DIGEST=$digest"
  sudo -n docker image inspect --format "R19_${name^^}_IMAGE_ID={{.Id}}" "$digest"
}

verify_and_capture "$BESU_TAG" "hyperledger/besu" "besu"
verify_and_capture "$LIGHTHOUSE_TAG" "sigp/lighthouse" "lighthouse"
echo "R19_NATIVE_EL_CL_BINARIES_EXECUTED=true"
echo "R19_NATIVE_EL_CL_P2P_STARTED=false"
echo "R19_BEACON_GENESIS_CREATED=false"
echo "R19_INDEPENDENT_VALIDATOR_KEYS_CREATED=false"
echo "R19_PUBLIC_POS_NETWORK_DEPLOYED=false"
