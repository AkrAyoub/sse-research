#!/usr/bin/env bash
# G2: actual chain31340 lab; one real BLS key; no Internet P2P or secret leakage.
set -euo pipefail
umask 077
set +x
refuse() { printf 'R35_G2_START_REFUSED: %s\n' "$*" >&2; exit 2; }
[[ $# -eq 2 && ( "$1" == "--plan" || "$1" == "--apply" ) &&
   "$2" =~ ^[a-f0-9]{40}$ ]] || refuse "usage: --plan|--apply EXACT_GITHUB_SHA"
MODE="$1"; SHA="$2"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse --verify HEAD^{commit})" == "$SHA" ]] ||
  refuse "wrong immutable Git commit"
git diff --quiet && git diff --cached --quiet || refuse "tracked VM source changed"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 &&
   "$(id -u)" != 0 ]] || refuse "unprivileged Linux x86_64 only"

echo "== VERIFY ACTUAL STEP40 EL, CL, SSZ AND ONE EXISTING ENCRYPTED BLS KEY =="
python3 -B tools/sse_pos_g2_preflight.py --expected-commit "$SHA" ||
  refuse "R35 real genesis/validator gate failed"

mapfile -t REFS <<< "$(python3 -B tools/sse_pos_client_pins.py --refs)" 
mapfile -t IDS <<< "$(python3 -B tools/sse_pos_client_pins.py --image-ids)"
[[ ${#REFS[@]} -eq 2 && ${#IDS[@]} -eq 2 ]] || refuse "image manifest incomplete"
sudo -n docker info --format 'R35_DOCKER={{.ServerVersion}}' ||
  refuse "operator-scoped Docker not available"
for I in 0 1; do
  ID="$(sudo -n docker image inspect --format '{{.Id}}' "${REFS[$I]}")" ||
    refuse "pinned image absent; no mutable tag pull"
  OSARCH="$(sudo -n docker image inspect -f '{{.Os}}/{{.Architecture}}' "${REFS[$I]}")"
  [[ "$ID" == "${IDS[$I]}" && "$OSARCH" == linux/amd64 ]] ||
    refuse "image digest/platform differs from observed VM4706"
done

echo "== VALIDATE PINNED CLI FLAGS IN OFFLINE CONTAINERS =="
BHELP="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
  --network none --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --hostname sse-help --add-host sse-help:127.0.0.1 \
  --user 65534:65534 --cpus 1 --memory 1g \
  --cap-drop ALL --security-opt no-new-privileges "${REFS[0]}" --help 2>&1)" ||
  refuse "Besu help failed"
for FLAG in --genesis-file --network-id --p2p-enabled --data-path \
  --engine-rpc-enabled --engine-rpc-port --engine-host-allowlist \
  --engine-jwt-secret --rpc-http-enabled --rpc-http-api; do
  [[ "$BHELP" == *"$FLAG"* ]] || refuse "Besu missing $FLAG"
done
LHELP="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
  --network none --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --user 65534:65534 --cpus 1 --memory 1g \
  --cap-drop ALL --security-opt no-new-privileges \
  --entrypoint lighthouse "${REFS[1]}" --help 2>&1)" ||
  refuse "Lighthouse help failed"
[[ "$LHELP" == *"--testnet-dir"* && "$LHELP" == *"--datadir"* ]] ||
  refuse "Lighthouse custom testnet flags absent"
for TYPE in bn vc; do
  LHELP="$(sudo -n docker run --rm --pull never --platform linux/amd64 \
    --network none --read-only --tmpfs /tmp:rw,nosuid,noexec,size=64m \
    --user 65534:65534 --cpus 1 --memory 1g \
    --cap-drop ALL --security-opt no-new-privileges \
    --entrypoint lighthouse "${REFS[1]}" "$TYPE" --help 2>&1)" ||
    refuse "Lighthouse $TYPE help failed"
  if [[ "$TYPE" == bn ]]; then
    for FLAG in --execution-endpoint --execution-jwt --http --http-address --suggested-fee-recipient; do
      [[ "$LHELP" == *"$FLAG"* ]] || refuse "Beacon missing $FLAG"
    done
  else
    for FLAG in --beacon-nodes --validators-dir --secrets-dir --suggested-fee-recipient; do
      [[ "$LHELP" == *"$FLAG"* ]] || refuse "VC missing $FLAG"
    done
  fi
done
unset BHELP LHELP

RUN="$HOME/.local/share/sse-r35-chain31340-g2-private"
PUBLIC="$HOME/.local/share/sse-r34-chain31340-public"
KEYS="$HOME/.local/share/sse-r27-bls-operator-private"
NET="sse31340-g2-internal"
EL="sse31340-g2-el"; BN="sse31340-g2-bn"; VC="sse31340-g2-vc"
EOA="0x13fb73aace8A11Be2899D047635A757a224Ce00B"
[[ ! -e "$RUN" && ! -L "$RUN" ]] ||
  refuse "G2 run directory already exists; never overwrite or duplicate signing"
if sudo -n docker network inspect "$NET" >/dev/null 2>&1; then
  refuse "G2 network already exists; inspect previous attempt"
fi
for NAME in "$EL" "$BN" "$VC"; do
  if sudo -n docker container inspect "$NAME" >/dev/null 2>&1; then
    refuse "G2 container already exists; never start duplicate VC"
  fi
done
echo "R35_G2_REAL_ARTIFACT_AND_CLIENT_PREFLIGHT_PASSED=true"
echo "R35_G2_ONE_OWNER_FAULT_DOMAIN=true"
echo "R35_G2_NO_PUBLIC_P2P_OR_ENGINE_API=true"
echo "R35_G2_EL_READ_RPC=127.0.0.1:18545"
echo "R35_G2_BEACON_READ_API=127.0.0.1:15052"
if [[ "$MODE" == "--plan" ]]; then
  echo "R35_G2_DRY_RUN_NO_WRITES_OR_CLIENT_START=true"
  exit 0
fi
[[ -t 0 && -t 2 ]] || refuse "interactive owner authorization required"
echo "Start REAL Besu, Lighthouse Beacon and ONE already-existing BLS VC."
echo "The single owner VM is NOT a decentralized public network."
echo "DO NOT approve if this same validator is already signing elsewhere."
read -r -p "Type START-CHAIN31340-G2 to authorize: " CONSENT
[[ "$CONSENT" == "START-CHAIN31340-G2" ]] || refuse "owner declined signing"
mkdir -m 700 "$RUN"
for SUB in testnet el beacon vc; do mkdir -m 700 "$RUN/$SUB"; done
for FILE in config.yaml genesis.json deposit_contract.txt deploy_block.txt; do
  cp -- "$PUBLIC/$FILE" "$RUN/testnet/$FILE"
  cmp -s "$PUBLIC/$FILE" "$RUN/testnet/$FILE" ||
    refuse "public input changed during copying"
  chmod 644 "$RUN/testnet/$FILE"
done
# Lighthouse v8.3.3 requires THIS exact public file basename; upstream
# Eth2NetworkConfig::load uses load_from_file!(DEPLOY_BLOCK_FILE), not optional.
# Keep the original R34 deploy_block.txt as immutable provenance.
[[ ! -e "$RUN/testnet/deposit_contract_block.txt" ]] ||
  refuse "refuse overwrite of Lighthouse required public testnet block file"
cp -- "$PUBLIC/deploy_block.txt" "$RUN/testnet/deposit_contract_block.txt"
cmp -s "$PUBLIC/deploy_block.txt" "$RUN/testnet/deposit_contract_block.txt" ||
  refuse "Lighthouse required public deposit block copy mismatch"
chmod 644 "$RUN/testnet/deposit_contract_block.txt"
cp -- "$PUBLIC/beacon-generated/genesis.ssz" "$RUN/testnet/genesis.ssz"
cmp -s "$PUBLIC/beacon-generated/genesis.ssz" "$RUN/testnet/genesis.ssz" ||
  refuse "SSZ copying mismatch"
chmod 644 "$RUN/testnet/genesis.ssz"
JWT="$RUN/engine.jwt"
( set -C; umask 077; python3 -c 'import secrets,sys; sys.stdout.write(secrets.token_hex(32))' > "$JWT" ) ||
  refuse "failed create-only 256-bit local JWT"
[[ "$(stat -c '%u:%a' "$JWT")" == "$(id -u):600" ]] ||
  refuse "local Engine JWT owner-only permissions incorrect"
sudo -n docker network create --driver bridge --internal "$NET" >/dev/null ||
  refuse "Docker private bridge failed; preserve local data"
USER_ID="$(id -u):$(id -g)"

echo "== SUBMIT PINNED BESU EXECUTION =="
sudo -n docker run -d --pull never --platform linux/amd64 \
  --name "$EL" --hostname "$EL" --init --network "$NET" \
  -p 127.0.0.1:18545:8545/tcp \
  --user "$USER_ID" --read-only --tmpfs /tmp:rw,nosuid,noexec,size=256m \
  --cpus 2 --memory 4g --pids-limit 384 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$RUN/testnet,target=/testnet,readonly" \
  --mount "type=bind,source=$RUN/el,target=/data" \
  --mount "type=bind,source=$JWT,target=/jwt/engine.jwt,readonly" \
  "${REFS[0]}" \
  --network-id=31340 --genesis-file=/testnet/genesis.json --data-path=/data \
  --p2p-enabled=false \
  --rpc-http-enabled --rpc-http-host=0.0.0.0 --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,WEB3 --host-allowlist=localhost,127.0.0.1 \
  --engine-rpc-enabled --engine-rpc-port=8551 \
  --engine-host-allowlist='*' --engine-jwt-secret=/jwt/engine.jwt >/dev/null ||
  refuse "Besu launch failed; preserve data and containers"
echo "== SUBMIT PINNED LIGHTHOUSE BEACON =="
sudo -n docker run -d --pull never --platform linux/amd64 \
  --name "$BN" --hostname "$BN" --init --network "$NET" \
  -p 127.0.0.1:15052:5052/tcp \
  --user "$USER_ID" --read-only --tmpfs /tmp:rw,nosuid,noexec,size=256m \
  --cpus 1.5 --memory 4g --pids-limit 384 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$RUN/testnet,target=/testnet,readonly" \
  --mount "type=bind,source=$RUN/beacon,target=/data" \
  --mount "type=bind,source=$JWT,target=/jwt/engine.jwt,readonly" \
  --entrypoint lighthouse "${REFS[1]}" \
  --testnet-dir=/testnet --datadir=/data bn \
  --execution-endpoint="http://$EL:8551" \
  --execution-jwt=/jwt/engine.jwt --http \
  --http-address=0.0.0.0 --http-port=5052 \
  --suggested-fee-recipient="$EOA" >/dev/null ||
  refuse "Lighthouse Beacon launch failed; preserve data"
echo "== SUBMIT EXISTING OWNER LIGHTHOUSE SIGNING VC =="
sudo -n docker run -d --pull never --platform linux/amd64 \
  --name "$VC" --hostname "$VC" --init --network "$NET" \
  --user "$USER_ID" --read-only --tmpfs /tmp:rw,nosuid,noexec,size=128m \
  --cpus 0.5 --memory 1g --pids-limit 192 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$RUN/testnet,target=/testnet,readonly" \
  --mount "type=bind,source=$RUN/vc,target=/data" \
  --mount "type=bind,source=$KEYS/validators,target=/keys/validators" \
  --mount "type=bind,source=$KEYS/secrets,target=/keys/secrets,readonly" \
  --entrypoint lighthouse "${REFS[1]}" \
  --testnet-dir=/testnet --datadir=/data vc \
  --beacon-nodes="http://$BN:5052" \
  --validators-dir=/keys/validators --secrets-dir=/keys/secrets \
  --suggested-fee-recipient="$EOA" >/dev/null ||
  refuse "VC launch failed; preserve slashing protection, never recreate keys"
echo "R35_REAL_EL_CL_AND_EXISTING_VC_CONTAINERS_SUBMITTED=true"
echo "R35_CONTAINERS_SUBMITTED_NOT_YET_FINALITY_VERIFIED=true"
echo "R35_PRIVATE_LOGS_AND_VALIDATOR_PASSWORDS_NEVER_PASTE=true"
echo "R35_NEXT_COMMAND=python3 -B tools/sse_pos_g2_health.py"
sudo -n docker ps --format 'R35_RUNNING_CONTAINER={{.Names}}' \
  --filter "name=^/$EL$" --filter "name=^/$BN$" --filter "name=^/$VC$"
