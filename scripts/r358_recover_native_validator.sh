#!/usr/bin/env bash
# Recover the same imported validator, never reimport or reset slashing state.
set -euo pipefail
umask 077
set +x
fail(){ echo "R358_RECOVERY_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || fail "exact source SHA required"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ "$(git rev-parse HEAD)" == "$1" ]] || fail "source mismatch"
git diff --quiet && git diff --cached --quiet || fail "dirty source"
[[ "$(id -u)" != 0 && -t 0 && -t 2 ]] || fail "owner terminal required"
ROOT="$HOME/.local/share/sse31340-validator"
PY="$HOME/.venvs/sse-validator/bin/python"
NAME=sse31340-owner-vc
EXPECTED="$(python3 -B tools/sse_pos_client_pins.py --image-ids | tail -n1)"
[[ "$(sudo -n docker inspect --format '{{.Image}}' "$NAME")" == "$EXPECTED" ]] || fail "unexpected VC image"
[[ "$(sudo -n docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$NAME")" == "$ROOT/lighthouse" ]] || fail "unexpected VC data mount"
REPORT="$("$PY" -B tools/sse_pos_r358_validator_reconcile.py --directory "$ROOT")"
"$PY" -B -c 'import json,sys; r=json.load(sys.stdin); assert r["receiptSuccessful"] and r["state"]=="CANONICAL_DEPOSIT"' <<<"$REPORT"
echo "$REPORT"
# Stop only this exact existing VC; no other clients or data are touched.
sudo -n docker stop "$NAME" >/dev/null
[[ "$(sudo -n docker inspect --format '{{.State.Running}}' "$NAME")" == false ]] || fail "VC did not stop"
"$PY" -B tools/sse_pos_r358_validator_unlock.py --directory "$ROOT"
sudo -n docker start "$NAME" >/dev/null
sleep 5
sudo -n docker inspect --format 'VC_STATE={{.State.Status}} RESTARTS={{.RestartCount}} RESTART={{.HostConfig.RestartPolicy.Name}}' "$NAME"
[[ "$(sudo -n docker inspect --format '{{.State.Status}}' "$NAME")" == running ]] || fail "VC not running; preserve data and inspect startup logs"
echo "R358_EXISTING_VC_RESTARTED=true"
