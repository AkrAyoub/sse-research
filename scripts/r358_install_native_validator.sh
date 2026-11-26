#!/usr/bin/env bash
# R358g: add one local validator service to an existing native full node.
# No changes to existing EL/BN, no new genesis, no network validator limit.
# One local import attempt; preserve data after any partial failure.
set -euo pipefail
umask 077
set +x
fail(){ echo "R358_VC_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || fail "exact source SHA required"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ "$(git rev-parse HEAD)" == "$1" ]] || fail "wrong source"
git diff --quiet && git diff --cached --quiet || fail "dirty source"
[[ "$(id -u)" != 0 && -t 0 && -t 2 ]] || fail "owner terminal required"
ROOT="$HOME/.local/share/sse31340-validator"
PY="$HOME/.venvs/sse-validator/bin/python"
[[ -d "$ROOT" && ! -L "$ROOT" && "$(stat -c '%u:%a' "$ROOT")" == "$(id -u):700" ]] || fail "private root required"
[[ -f "$ROOT/keystore.json" && ! -L "$ROOT/keystore.json" && "$(stat -c '%u:%a' "$ROOT/keystore.json")" == "$(id -u):600" ]] || fail "existing encrypted validator key required"
REPORT="$("$PY" -B tools/sse_pos_r358_validator_reconcile.py --directory "$ROOT")"
EOA="$("$PY" -B -c 'import json,sys; r=json.load(sys.stdin); assert r["receiptSuccessful"] and r["state"]=="CANONICAL_DEPOSIT"; print(json.load(open(sys.argv[1]))["sender"])' "$ROOT/deposit-intent.json" <<<"$REPORT")"
echo "$REPORT"
mapfile -t BNS < <(sudo -n docker ps --format '{{.Names}}' | grep -- '-bn$' || true)
[[ ${#BNS[@]} == 1 ]] || fail "exactly one local running beacon required"
BN="${BNS[0]}"
TESTNET="$(sudo -n docker inspect --format '{{range .Mounts}}{{if eq .Destination "/testnet"}}{{.Source}}{{end}}{{end}}' "$BN")"
[[ "$TESTNET" == /* && "$TESTNET" != *$'\n'* ]] || fail "existing testnet mount unavailable"
LIGHTHOUSE="$(python3 -B tools/sse_pos_client_pins.py --refs | tail -n1)"
EXPECTED="$(python3 -B tools/sse_pos_client_pins.py --image-ids | tail -n1)"
[[ "$(sudo -n docker image inspect --format '{{.Id}}' "$LIGHTHOUSE")" == "$EXPECTED" ]] || fail "pinned image mismatch"
[[ "$(sudo -n docker inspect --format '{{.Image}}' "$BN")" == "$EXPECTED" ]] || fail "beacon image mismatch"
NAME=sse31340-owner-vc
[[ -z "$(sudo -n docker ps -a --format '{{.Names}}' | grep -Ei 'validator|[-_]vc([_-]|$)' || true)" ]] || fail "existing possible validator client; inspect before importing"
VC="$ROOT/lighthouse"
[[ ! -e "$VC" && ! -L "$VC" ]] || fail "existing import data; preserve and inspect, never recreate"
echo "Use only this host to sign with this BLS key. Lighthouse stores local unlocking material for unattended restart; protect the private directory and backups."
read -r -p "Type IMPORT-AND-START-LOCAL-VALIDATOR to authorize: " APPROVAL
[[ "$APPROVAL" == IMPORT-AND-START-LOCAL-VALIDATOR ]] || fail "not authorized"
mkdir -m 700 "$VC"
UIDGID="$(id -u):$(id -g)"
sudo -n docker run --rm -it --pull never --network none \
  --user "$UIDGID" --read-only --tmpfs /tmp:rw,nosuid,noexec,size=128m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$TESTNET,target=/testnet,readonly" \
  --mount "type=bind,source=$VC,target=/data" \
  --mount "type=bind,source=$ROOT/keystore.json,target=/import/keystore.json,readonly" \
  --entrypoint lighthouse "$LIGHTHOUSE" \
  account validator import --testnet-dir /testnet --datadir /data \
  --keystore /import/keystore.json --reuse-password
[[ -s "$VC/validators/slashing_protection.sqlite" && -s "$VC/validators/validator_definitions.yml" ]] || fail "import lacks expected slashing DB or definitions; preserve files"
[[ -z "$(find "$VC" -type l -print -quit)" ]] || fail "unexpected symlink"
find "$VC" -type d -exec chmod 700 {} +
find "$VC" -type f -exec chmod 600 {} +
sudo -n docker run -d --pull never --name "$NAME" --restart unless-stopped \
  --network host --init --user "$UIDGID" \
  --read-only --tmpfs /tmp:rw,nosuid,noexec,size=128m \
  --cpus 1 --memory 1g --pids-limit 192 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$TESTNET,target=/testnet,readonly" \
  --mount "type=bind,source=$VC,target=/data" \
  --entrypoint lighthouse "$LIGHTHOUSE" \
  --testnet-dir=/testnet --datadir=/data vc \
  --beacon-nodes=http://127.0.0.1:25052 --suggested-fee-recipient="$EOA" \
  --enable-doppelganger-protection
sudo -n docker inspect --format 'VC_RUNNING={{.State.Running}} RESTART={{.HostConfig.RestartPolicy.Name}}' "$NAME"
echo "R358_VC_SUBMITTED=true (activation and signing duties not yet verified)"
