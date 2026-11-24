#!/usr/bin/env bash
# R291: optional locally approved ZeroTier-only signed APT provisioning
# on dedicated NEW VM4711-VM4714. NO Docker, EL/CL, VC, wallets or keys.
# Execute: bash scripts/r291_vm4711_4714_signed_overlay_install.sh <full SHA> --install
set -euo pipefail
refuse() { echo "R291_SIGNED_APT_ONLY_REFUSED: $*" >&2; exit 2; }

[[ $# -eq 2 && "$2" == "--install" ]] || refuse "expected exact pinned full SHA and --install"
SHA="$1"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || refuse "expected full immutable commit hash"

case "$(id -un)" in
  ayoubakrvm4711|ayoubakrvm4712|ayoubakrvm4713|ayoubakrvm4714) ;;
  *) refuse "only four dedicated NEW lab VMs, not original PoS signing/EL/CL hosts" ;;
esac
[[ "$(id -u)" != 0 ]] || refuse "nonroot owner shell required"
[[ "$(uname -m)" == "x86_64" ]] || refuse "only pinned Ubuntu24.04 amd64 package"
[[ -r /etc/os-release ]] || refuse "missing OS identity"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || refuse "Ubuntu24.04 only"
[[ "$(git rev-parse HEAD 2>/dev/null)" == "$SHA" ]] || refuse "wrong Git revision"
[[ -z "$(git status --porcelain 2>/dev/null)" ]] || refuse "Git checkout not clean"

if command -v zerotier-cli >/dev/null 2>&1 || [[ -e /usr/sbin/zerotier-one ]]; then
  refuse "ZeroTier exists; run read-only R291 --status, never reinstall"
fi
command -v sudo >/dev/null 2>&1 || refuse "no local sudo; no unsafe fallback"
sudo -n true >/dev/null 2>&1 || refuse "no already-granted noninteractive root package install"

[[ -t 0 && -t 2 ]] || refuse "real operator console required"
echo "R291_OWNER_REVIEW: install ONLY vendor-signed ZeroTier package into this dedicated new host."
echo "Package source https://download.zerotier.com/debian/noble"
echo "Pinned vendor primary GPG fingerprint: 74A5E9C458E1A431F1DA57A71657198823E52A61"
echo "This may write scoped APT keyring/source and enable ZeroTier daemon."
echo "It DOES NOT join a network yet, change Docker/chain/keys, or open an app server."
read -r -p "Type INSTALL-ONE-R291-SIGNED-ZEROTIER-ONLY to approve local OS package operation: " answer
[[ "$answer" == "INSTALL-ONE-R291-SIGNED-ZEROTIER-ONLY" ]] || refuse "exact owner consent missing"
sudo -n /usr/bin/python3 -B \
  tools/sse_pos_r291_verified_vendor_package_only.py \
  --install-after-owner-consent --expected-commit "$SHA"
echo "R291_SIGNED_VENDOR_APT_INSTALL_REQUEST_COMPLETED_CHECK_OPEN_OVERLAY_STATUS_NEXT=true"
