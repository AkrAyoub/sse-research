#!/usr/bin/env bash
# R106: VM4706 ONLY. Restore EXISTING dual-network native P2P without
# changing/recreating EL/BN/VC, Docker networks, genesis, mounts or keys.
# R92 host relay must yield host ports; no execution Engine 8551 published.
set -euo pipefail
MODE="${1:---plan}"
[[ "$MODE" == "--plan" || "$MODE" == "--apply" ]] || { echo "R106_REFUSED: --plan or --apply"; exit 2; }
[[ "$(id -un)" == "ayoubakrvm4706" || "$(id -u)" == 0 ]] || { echo "R106_REFUSED: wrong user"; exit 2; }
if [[ "$(id -u)" == 0 ]]; then
  # Root under sudo: use invoking owner as identity, never resolve from hostname.
  [[ "${SUDO_USER:-}" == "ayoubakrvm4706" || "${R106_BOOT_SERVICE:-}" == "true" ]] || {
    echo "R106_REFUSED: unrecognized root invocation"; exit 2;
  }
fi
D=(sudo -n docker)
if [[ "$(id -u)" == 0 ]]; then D=(docker); fi
EL=sse31340-g2-el-r40
BN=sse31340-g2-bn
VC=sse31340-g2-vc
TRUST=sse31340-g2-internal
PUBLIC=sse31340-g2-r65-public-p2p
IP='fca0:2328:776e:4750:395b::1'
RELAY=sse31340-owner-port-relay.service

die(){ echo "R106_REFUSED: $*" >&2; exit 2; }
hostip(){ ip -6 addr show dev ztrb6cq527 | grep -Fq "$IP/40"; }
check_role(){
  hostip || die "ZeroTier 6plane IPv6 not assigned yet"
  [[ "$("${D[@]}" network inspect "$TRUST" --format '{{.Internal}}:{{.Driver}}')" == 'true:bridge' ]] || die "private bridge changed"
  [[ "$("${D[@]}" network inspect "$PUBLIC" --format '{{.Internal}}:{{.Driver}}:{{.EnableIPv6}}')" == 'false:bridge:true' ]] || die "public bridge not normal IPv6 bridge"
  [[ "$("${D[@]}" inspect "$VC" --format '{{.State.Running}}')" == false ]] || die "validator running: no automatic EL BN maintenance"
  for C in "$EL" "$BN"; do
    [[ "$("${D[@]}" inspect "$C" --format '{{.HostConfig.NetworkMode}}')" == "$TRUST" ]] || die "$C unexpected primary network"
    # R65 originals have exact host-only published API and advertised 6plane P2P
    [[ "$("${D[@]}" inspect "$C" --format '{{json .HostConfig.PortBindings}}')" != *'"8551/tcp"'* ]] || die "Engine host publication detected"
    [[ "$("${D[@]}" inspect "$C" --format '{{.State.Running}}')" == true ]] || die "$C not running"
  done
  [[ "$("${D[@]}" inspect "$EL" --format '{{with index .NetworkSettings.Networks "sse31340-g2-internal"}}{{.IPAddress}}{{end}}')" == 172.18.0.2 ]] || die "EL private IP changed"
  [[ "$("${D[@]}" inspect "$BN" --format '{{with index .NetworkSettings.Networks "sse31340-g2-internal"}}{{.IPAddress}}{{end}}')" == 172.18.0.3 ]] || die "BN private IP changed"
  "${D[@]}" inspect "$EL" --format '{{json .NetworkSettings.Networks}}' | grep -Fq '"sse31340-g2-el"' || die "EL original Engine DNS alias missing"
}
attachment(){
  "${D[@]}" inspect "$1" --format '{{if index .NetworkSettings.Networks "sse31340-g2-r65-public-p2p"}}yes{{else}}no{{end}}'
}
effective(){
  local C="$1" payload
  payload="$("${D[@]}" inspect "$C" --format '{{json .NetworkSettings.Ports}}')"
  if [[ "$C" == "$EL" ]]; then
    for binding in '"HostPort":"18545"' '"HostPort":"30404"'; do [[ "$payload" == *"$binding"* ]] || return 1; done
  else
    for binding in '"HostPort":"15052"' '"HostPort":"9000"' '"HostPort":"9001"'; do [[ "$payload" == *"$binding"* ]] || return 1; done
  fi
}
check_public_set(){
  local C="$1" networks
  networks="$("${D[@]}" inspect "$C" --format '{{json .NetworkSettings.Networks}}')"
  # Neither extra provider network nor missing internal trust path permitted.
  python3 -c 'import json,sys; n=json.loads(sys.argv[1]); assert set(n) <= {"sse31340-g2-internal","sse31340-g2-r65-public-p2p"} and "sse31340-g2-internal" in n' "$networks" ||
    die "$C unexpected network topology"
}
check_role
for C in "$EL" "$BN"; do
  check_public_set "$C"
  echo "R106_PRECHECK $C PUBLIC_ATTACHED=$(attachment "$C")"
done
if [[ "$MODE" == "--plan" ]]; then
  echo "R106_PLAN_OK=true"
  exit 0
fi
# Idempotent: never disturb already restored native ports.
if [[ "$(attachment "$EL")" == yes && "$(attachment "$BN")" == yes ]] &&
   effective "$EL" && effective "$BN"; then
  echo "R106_ALREADY_RECOVERED=true"
  exit 0
fi
# Restrict this intervention to the observed lost-public-endpoint case.
[[ "$(attachment "$EL")" == no && "$(attachment "$BN")" == no ]] ||
  die "mixed public bridge state: manual inspection required"
# Do not bring up original Docker published ports while R92 holds them.
if systemctl is-active --quiet "$RELAY"; then
  echo "R106_STAGE=STOP_TEMPORARY_RELAY"
  sudo -n systemctl stop "$RELAY"
fi
# Relay must stay disabled after native restoration, including subsequent reboots.
# Disable after native checks succeed, not before.
for C in "$EL" "$BN"; do
  echo "R106_STAGE=REATTACH_EXISTING_PUBLIC_BRIDGE $C"
  "${D[@]}" network connect "$PUBLIC" "$C" ||
    die "public connect failed; DO NOT RETRY BLINDLY"
  echo "R106_STAGE=RESTART_EXISTING_CLIENT $C"
  "${D[@]}" restart --time 60 "$C" ||
    die "restart failed; DO NOT RETRY BLINDLY"
  [[ "$(attachment "$C")" == yes ]] || die "public endpoint missing"
  effective "$C" || die "Docker effective port publishing missing"
done
check_role
for C in "$EL" "$BN"; do
  check_public_set "$C"
  effective "$C" || die "$C port publication missing"
done
sudo -n systemctl disable "$RELAY" >/dev/null
echo "R106_NATIVE_DUAL_NETWORK_PORTS_RESTORED=true"
echo "R106_VALIDATOR_UNTOUCHED=true"
