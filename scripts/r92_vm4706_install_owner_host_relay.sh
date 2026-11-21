#!/usr/bin/env bash
# R92 VM4706 only; pinned file from reviewed GitHub checkout.
# --plan: read-only. --apply: installs ONLY an independent host relay + systemd unit.
# Never changes Docker networks/containers, starts validators or touches private files.
set -euo pipefail
MODE="${1:---plan}"
if [[ "$MODE" != "--plan" && "$MODE" != "--apply" ]]; then
  echo "R92_REFUSED: use --plan or --apply" >&2; exit 2
fi
[[ "$(whoami)" == "ayoubakrvm4706" ]] || { echo "R92_REFUSED: wrong VM" >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/tools/sse_pos_r92_owner_internal_bridge_host_relay.py"
UNIT="$ROOT/systemd/sse31340-owner-port-relay.service"
test -f "$SOURCE" && test -f "$UNIT"
test "$(sudo -n docker network inspect sse31340-g2-internal --format '{{.Internal}}')" = true
test "$(sudo -n docker network inspect sse31340-g2-internal --format '{{.Driver}}')" = bridge
ip -6 addr show dev ztrb6cq527 | grep -F 'fca0:2328:776e:4750:395b::1/40' >/dev/null
test "$(sudo -n docker inspect sse31340-g2-el-r40 --format '{{.HostConfig.NetworkMode}}')" = sse31340-g2-internal
test "$(sudo -n docker inspect sse31340-g2-bn --format '{{.HostConfig.NetworkMode}}')" = sse31340-g2-internal
test "$(sudo -n docker inspect sse31340-g2-vc --format '{{.State.Running}}')" = false
test "$(sudo -n docker inspect sse31340-g2-el-r40 --format '{{with index .NetworkSettings.Networks "sse31340-g2-internal"}}{{.IPAddress}}{{end}}')" = 172.18.0.2
test "$(sudo -n docker inspect sse31340-g2-bn --format '{{with index .NetworkSettings.Networks "sse31340-g2-internal"}}{{.IPAddress}}{{end}}')" = 172.18.0.3
# No privileged Engine 8551 is included in fixed relay configuration.
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r92_owner_internal_bridge_host_relay.py' -q
if [[ "$MODE" == "--plan" ]]; then
  echo "R92_OWNER_RELAY_PLAN_OK=true"
  echo "R92_NEXT=run --apply after reviewing explicit TCP UDP endpoints"
  exit 0
fi
sudo -n install -D -m 0755 "$SOURCE" /usr/local/libexec/sse_pos_r92_owner_internal_bridge_host_relay.py
sudo -n install -m 0644 "$UNIT" /etc/systemd/system/sse31340-owner-port-relay.service
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now sse31340-owner-port-relay.service
sudo -n systemctl --no-pager --full status sse31340-owner-port-relay.service || true
echo "R92_RELAY_INSTALLED_VALIDATE_BINDINGS_AND_PEERS=true"
