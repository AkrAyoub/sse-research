#!/usr/bin/env bash
# R57: acquire ONLY the previously observed immutable Besu/Lighthouse images
# on a NON-SIGNING host for authentic chain31340 native IPv6 P2P staging.
# No EL/CL/VC clients, containers, ports, genesis or firewall are created.
set -euo pipefail
umask 077

MODE="${1:---plan}"
if [[ $# -gt 1 || ( "$MODE" != "--plan" && "$MODE" != "--pull" ) ]]; then
  echo "R57_REFUSED: use --plan or --pull" >&2
  exit 2
fi
fail() { echo "R57_REFUSED: $1" >&2; exit 2; }

[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
  fail "non-signing Linux x86_64 required"
for name in sudo docker sha256sum; do
  command -v "$name" >/dev/null || fail "missing prerequisite"
done

# Never acquire/deploy anything on original owner's signing machine.
for private_dir in \
  "$HOME/.local/share/sse-r35-chain31340-g2-private" \
  "$HOME/.local/share/sse-r27-bls-operator-private"; do
  [[ ! -e "$private_dir" && ! -L "$private_dir" ]] ||
    fail "original signing machine state present"
done

ARCHIVE="$HOME/chain31340-public-native-observer-v1.tar.gz"
ARCHIVE_SHA="1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7"
[[ -f "$ARCHIVE" && ! -L "$ARCHIVE" ]] || fail "verified original PUBLIC genesis archive missing"
[[ "$(sha256sum "$ARCHIVE" | cut -d' ' -f1)" == "$ARCHIVE_SHA" ]] ||
  fail "public genesis archive SHA256 differs from verified owner Step54"
sudo -n docker info --format 'docker={{.ServerVersion}} cgroup={{.CgroupVersion}}' ||
  fail "noninteractive operator-authorized Docker access unavailable"
if sudo -n docker ps -a --format '{{.Names}}' | grep -Fxq 'sse31340-g2-vc'; then
  fail "original signing validator container found"
fi

BESU_REF="hyperledger/besu@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
BESU_TAG="hyperledger/besu:26.11.1"
BESU_ID="sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d"
LIGHTHOUSE_REF="sigp/lighthouse@sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"
LIGHTHOUSE_TAG="sigp/lighthouse:v8.3.3"
LIGHTHOUSE_ID="sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1"

verify_existing_tag() {
  local label="$1" tag="$2" expected="$3" actual arch
  if actual="$(sudo -n docker image inspect --format '{{.Id}}' "$tag" 2>/dev/null)"; then
    arch="$(sudo -n docker image inspect --format '{{.Os}}/{{.Architecture}}' "$tag")"
    [[ "$actual" == "$expected" && "$arch" == linux/amd64 ]] ||
      fail "$label pre-existing tag has incorrect image ID or platform"
    echo "R57_${label}_EXACT_TAG_PRESENT=true"
  else
    echo "R57_${label}_EXACT_TAG_PRESENT=false"
  fi
}

verify_pulled_ref() {
  local label="$1" ref="$2" expected="$3" actual arch
  actual="$(sudo -n docker image inspect --format '{{.Id}}' "$ref")" ||
    fail "$label immutable image ref missing"
  arch="$(sudo -n docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ref")" ||
    fail "$label image architecture unavailable"
  [[ "$actual" == "$expected" && "$arch" == linux/amd64 ]] ||
    fail "$label immutable pulled image ID/platform not matching pinned owner image"
  echo "R57_${label}_IMMUTABLE_IMAGE_VERIFIED=true"
}

verify_existing_tag BESU "$BESU_TAG" "$BESU_ID"
verify_existing_tag LIGHTHOUSE "$LIGHTHOUSE_TAG" "$LIGHTHOUSE_ID"
echo "R57_PUBLIC_CHAIN31340_ARCHIVE_VERIFIED=true"
echo "R57_ORIGINAL_SIGNER_UNTOUCHED=true"
echo "R57_ETHEREUM_P2P_STARTED=false"

if [[ "$MODE" == "--plan" ]]; then
  echo "R57_PLAN_READ_ONLY_COMPLETE=true"
  exit 0
fi

[[ -t 0 && -t 2 ]] || fail "interactive local operator approval required"
read -r -p "Pull exact digest-pinned public Besu+Lighthouse images (no chain start)? Type PULL-EXACT-R57-CLIENTS: " answer
[[ "$answer" == "PULL-EXACT-R57-CLIENTS" ]] || fail "operator did not approve image pulls"

# Uses immutable registry digest for actual download; never pulls 'latest'.
sudo -n docker pull --platform linux/amd64 "$BESU_REF"
verify_pulled_ref BESU "$BESU_REF" "$BESU_ID"
sudo -n docker pull --platform linux/amd64 "$LIGHTHOUSE_REF"
verify_pulled_ref LIGHTHOUSE "$LIGHTHOUSE_REF" "$LIGHTHOUSE_ID"

# Only after verifying IDs: add locally needed exact version tags for R48-style
# provenance checks; refuse to overwrite any pre-existing mismatched tag.
verify_existing_tag BESU "$BESU_TAG" "$BESU_ID"
verify_existing_tag LIGHTHOUSE "$LIGHTHOUSE_TAG" "$LIGHTHOUSE_ID"
if ! sudo -n docker image inspect "$BESU_TAG" >/dev/null 2>&1; then
  sudo -n docker tag "$BESU_REF" "$BESU_TAG"
fi
if ! sudo -n docker image inspect "$LIGHTHOUSE_TAG" >/dev/null 2>&1; then
  sudo -n docker tag "$LIGHTHOUSE_REF" "$LIGHTHOUSE_TAG"
fi
verify_existing_tag BESU "$BESU_TAG" "$BESU_ID"
verify_existing_tag LIGHTHOUSE "$LIGHTHOUSE_TAG" "$LIGHTHOUSE_ID"

# Offline version-only containers: no host ports, no network, no writable
# files, no secret mounts or blockchain data. Preserve official Besu entrypoint.
besu_version="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
  --hostname sse-r57-besu --add-host sse-r57-besu:127.0.0.1 \
  --network none --read-only --tmpfs /tmp:rw,nosuid,exec,size=64m \
  --user 65534:65534 --cpus 1 --memory 1g --cap-drop ALL \
  --security-opt no-new-privileges "$BESU_REF" --version)" ||
  fail "pinned Besu version probe failed"
echo "$besu_version"
[[ "$besu_version" == *"besu/v26.11.1/"* ]] ||
  fail "pinned Besu version incorrect"

lighthouse_version="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
  --network none --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --user 65534:65534 --cpus 1 --memory 1g --cap-drop ALL \
  --security-opt no-new-privileges --entrypoint lighthouse \
  "$LIGHTHOUSE_REF" --version)" ||
  fail "pinned Lighthouse version probe failed"
echo "$lighthouse_version"
[[ "$lighthouse_version" == *"Lighthouse v8.3.3"* ]] ||
  fail "pinned Lighthouse version incorrect"

echo "R57_PINNED_CLIENTS_INSTALLED_AND_VERSION_VERIFIED=true"
echo "R57_NO_ENGINE_BEACON_VALIDATOR_OR_P2P_STARTED=true"
