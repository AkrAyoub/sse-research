#!/usr/bin/env bash
# R110: owner boot reconciliation. Private Engine network first, public P2P second.
# Existing R92 and R106 guards each verify exact known original identities/ports.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo "R110_REFUSED: must run as root"; exit 2; }
D=(docker)
STALE=/usr/local/libexec/sse_pos_r117_owner_stale_stopped_endpoint_recovery.py
# Exact stopped, empty-endpoint Docker 29 reboot failure: only this recovery
# may detach stale records; never do so on running or unexpected containers.
if /usr/bin/python3 -B "$STALE" --plan >/dev/null 2>&1; then
  echo "R110_STAGE=RECOVER_EXACT_STALE_STOPPED_DUAL_NETWORK"
  /usr/bin/python3 -B "$STALE" --apply
fi
EL=sse31340-g2-el-r40
BN=sse31340-g2-bn
PRIVATE=sse31340-g2-internal
# Do not run owner R92 while a public bridge attachment is present: its
# allowlist deliberately forbids foreign/extra networks.
for C in "$EL" "$BN"; do
  if [[ "$("${D[@]}" inspect "$C" --format '{{if index .NetworkSettings.Networks "sse31340-g2-internal"}}yes{{else}}no{{end}}')" == no ]]; then
    echo "R110_STAGE=RESTORE_EXISTING_PRIVATE_NETWORK"
    /usr/bin/python3 -B /usr/local/libexec/sse_pos_r92_guarded_existing_node_recovery.py --role owner --apply
    break
  fi
done
export R106_BOOT_SERVICE=true
/usr/bin/bash /usr/local/libexec/sse31340-owner-native-network-recovery.sh --apply
echo "R110_OWNER_NATIVE_NETWORK_RECONCILED=true"
