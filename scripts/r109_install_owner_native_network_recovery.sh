#!/usr/bin/env bash
# R109 owner only: safely install periodic reconciliation of native EL/BN networks.
set -euo pipefail
MODE="${1:---plan}"
[[ "$MODE" == "--plan" || "$MODE" == "--apply" ]] || { echo "R109_REFUSED invalid mode"; exit 2; }
[[ "$(id -un)" == ayoubakrvm4706 ]] || { echo "R109_REFUSED wrong owner"; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/r106_vm4706_restore_native_dual_network.sh"
ORCHESTRATOR="$ROOT/scripts/r110_owner_boot_reconcile_networks.sh"
PRIVATE_RECOVERY="$ROOT/tools/sse_pos_r92_guarded_existing_node_recovery.py"
STALE_RECOVERY="$ROOT/tools/sse_pos_r117_owner_stale_stopped_endpoint_recovery.py"
SERVICE="$ROOT/systemd/sse31340-owner-native-network-recovery.service"
TIMER="$ROOT/systemd/sse31340-owner-native-network-recovery.timer"
sudo -v
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r106_native_dual_network_recovery.py' -q
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r92_guarded_existing_node_recovery.py' -q
bash -n "$ORCHESTRATOR"
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r117_owner_stale_stopped_endpoint_recovery.py' -q
if ! sudo -n bash "$SCRIPT" --plan; then
  sudo -n python3 -B "$STALE_RECOVERY" --plan
  echo "R109_PREFLIGHT_EXACT_STALE_REBOOT_STATE=true"
fi
[[ "$MODE" == --apply ]] || { echo "R109_OWNER_INSTALL_PLAN_OK=true"; exit 0; }
sudo -n install -D -m 0755 "$SCRIPT" /usr/local/libexec/sse31340-owner-native-network-recovery.sh
sudo -n install -m 0755 "$ORCHESTRATOR" /usr/local/libexec/sse31340-owner-native-network-orchestrator.sh
sudo -n install -m 0755 "$PRIVATE_RECOVERY" /usr/local/libexec/sse_pos_r92_guarded_existing_node_recovery.py
sudo -n install -m 0755 "$STALE_RECOVERY" /usr/local/libexec/sse_pos_r117_owner_stale_stopped_endpoint_recovery.py
sudo -n install -m 0644 "$SERVICE" /etc/systemd/system/sse31340-owner-native-network-recovery.service
sudo -n install -m 0644 "$TIMER" /etc/systemd/system/sse31340-owner-native-network-recovery.timer
sudo -n systemctl daemon-reload
# Enabling the timer does not immediately restart clients. The service itself
# verifies private network, exact owner identity, signer state and configured ports.
sudo -n systemctl enable --now sse31340-owner-native-network-recovery.timer
echo "R109_OWNER_NATIVE_RECOVERY_TIMER_ENABLED=true"
