#!/usr/bin/env bash
# R109 owner only: safely install periodic reconciliation of native EL/BN networks.
set -euo pipefail
MODE="${1:---plan}"
[[ "$MODE" == "--plan" || "$MODE" == "--apply" ]] || { echo "R109_REFUSED invalid mode"; exit 2; }
[[ "$(id -un)" == ayoubakrvm4706 ]] || { echo "R109_REFUSED wrong owner"; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/scripts/r106_vm4706_restore_native_dual_network.sh"
SERVICE="$ROOT/systemd/sse31340-owner-native-network-recovery.service"
TIMER="$ROOT/systemd/sse31340-owner-native-network-recovery.timer"
sudo -v
python3 -B -m unittest discover -s "$ROOT/tests" -p 'test_sse_pos_r106_native_dual_network_recovery.py' -q
sudo -n bash "$SCRIPT" --plan
[[ "$MODE" == --apply ]] || { echo "R109_OWNER_INSTALL_PLAN_OK=true"; exit 0; }
sudo -n install -D -m 0755 "$SCRIPT" /usr/local/libexec/sse31340-owner-native-network-recovery.sh
sudo -n install -m 0644 "$SERVICE" /etc/systemd/system/sse31340-owner-native-network-recovery.service
sudo -n install -m 0644 "$TIMER" /etc/systemd/system/sse31340-owner-native-network-recovery.timer
sudo -n systemctl daemon-reload
# Enabling the timer does not immediately restart clients. The service itself
# verifies private network, exact owner identity, signer state and configured ports.
sudo -n systemctl enable --now sse31340-owner-native-network-recovery.timer
echo "R109_OWNER_NATIVE_RECOVERY_TIMER_ENABLED=true"
