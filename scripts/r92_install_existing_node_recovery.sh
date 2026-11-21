#!/usr/bin/env bash
# R92: install the reviewed *existing-node* recovery unit only; VM4706 or VM4707.
# Does NOT run an automatic migration of Docker containers on installation.
set -euo pipefail
MODE="${1:---plan}"
[[ "$MODE" == "--plan" || "$MODE" == "--apply" ]] || { echo "R92_UNKNOWN_MODE" >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="$ROOT/tools/sse_pos_r92_guarded_existing_node_recovery.py"
UNIT="$ROOT/systemd/sse31340-existing-node-recover@.service"
test -f "$TOOL" && test -f "$UNIT"
case "$(whoami)" in
  ayoubakrvm4706) ROLE=owner ;;
  ayoubakrvm4707) ROLE=observer ;;
  *) echo "R92_WRONG_HOST_REFUSED" >&2; exit 2 ;;
esac
sudo -v
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r92_guarded_existing_node_recovery.py' -q
sudo -n python3 -B "$TOOL" --role "$ROLE" --plan
if [[ "$MODE" == "--plan" ]]; then
  echo "R92_EXISTING_NODE_RECOVERY_INSTALL_PLAN_OK role=$ROLE"
  exit 0
fi
sudo -n install -D -m 0755 "$TOOL" /usr/local/libexec/sse_pos_r92_guarded_existing_node_recovery.py
sudo -n install -m 0644 "$UNIT" /etc/systemd/system/sse31340-existing-node-recover@.service
sudo -n systemctl daemon-reload
sudo -n systemctl enable "sse31340-existing-node-recover@$ROLE.service"
echo "R92_EXISTING_NODE_RECOVERY_ENABLED_NEXT_BOOT=true role=$ROLE"
echo "NOTE: unit is only enabled, NOT started in this installation."
