#!/usr/bin/env bash
# Fresh application monitor bootstrap. No transaction signing or native clients.
set -euo pipefail
umask 077
fail(){ echo "R328_REFUSED: $*" >&2; exit 2; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "exact source commit required"
SHA="$1"
[[ "$(id -u)" != 0 && "$(uname -m)" == x86_64 ]] || fail "nonroot x86_64 operator required"
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail "Ubuntu 24.04 required"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse HEAD)" == "$SHA" && -z "$(git status --porcelain)" ]] || fail "pinned clean source required"
for p in "$HOME/.local" "$HOME/.local/share" "$HOME/.local/share/sse-v2-app-only" "$HOME/.venvs" "$HOME/.config" "$HOME/.config/sse"; do
 [[ ! -L "$p" ]] || fail "symlink in owner paths"
done
for p in "$HOME/.local/share/sse-r35-chain31340-g2-private" "$HOME/.local/share/sse-r27-bls-operator-private" "$HOME/.local/share/sse-v2-app-only" "$HOME/.venvs/sse-v2-operator" "$HOME/.config/sse/dashboard.env" "$HOME/sse-dashboard-runtime"; do
 [[ ! -e "$p" && ! -L "$p" ]] || fail "existing SSE state: $p"
done
echo "Select role for this application bootstrap:"
echo "  1. monitor"
echo "Other role combinations are not yet supported by this installer."
read -r -p "Role: " ROLE
[[ "$ROLE" == 1 ]] || fail "unsupported selection"
echo "Installs signed Ubuntu dependencies and verified ZeroTier package, joins existing public overlay, creates encrypted monitor wallet. No funds or transactions."
read -r -p "Type INSTALL-SSE-MONITOR to authorize: " APPROVAL
[[ "$APPROVAL" == INSTALL-SSE-MONITOR ]] || fail "not authorized"
sudo -n true || fail "local administrative permission required"
# Repair only the exact public keyring/source left by a prior interrupted install.
# Re-verify fingerprint before granting public read access; never trust an arbitrary key.
sudo -n /bin/bash -s <<'REPAIR_APT'
set -euo pipefail
key=/usr/share/keyrings/sse-zerotier.gpg
source=/etc/apt/sources.list.d/sse-zerotier.list
if [[ -e "$source" || -L "$source" || -e "$key" || -L "$key" ]]; then
  test -f "$key" && test ! -L "$key"
  test -f "$source" && test ! -L "$source"
  test "$(stat -c %u "$key")" = 0
  test "$(stat -c %u "$source")" = 0
  test "$(cat "$source")" = 'deb [arch=amd64 signed-by=/usr/share/keyrings/sse-zerotier.gpg] https://download.zerotier.com/debian/noble noble main'
  tmp="$(mktemp -d)"
  trap 'rm -rf -- "$tmp"' EXIT
  fingerprint="$(gpg --batch --homedir "$tmp" --with-colons --show-keys "$key" | awk -F: '$1=="pub"{p=1} $1=="sub"{p=0} $1=="fpr"&&p{print $10;p=0}')"
  test "$fingerprint" = 74A5E9C458E1A431F1DA57A71657198823E52A61
  chmod 0644 "$key" "$source"
  sudo -u _apt test -r "$key"
  echo R330_VERIFIED_PUBLIC_APT_KEYRING_READABLE=true
fi
REPAIR_APT
sudo -n env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get update
sudo -n env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq --no-install-recommends python3-venv gnupg ca-certificates
if ! command -v zerotier-cli >/dev/null; then
 # Root executes only its own immutable checkout, never user-writable source.
 sudo -n /bin/bash -s -- "$SHA" <<'ROOT_INSTALL'
set -euo pipefail
umask 077
tmp="$(mktemp -d /var/tmp/sse-root-install.XXXXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
git -c credential.helper= clone --no-checkout https://github.com/AkrAyoub/sse-research.git "$tmp/repo"
git -C "$tmp/repo" switch --detach "$1"
test "$(git -C "$tmp/repo" rev-parse HEAD)" = "$1"
cd "$tmp/repo"
PYTHONPATH="$tmp/repo/tools" /usr/bin/python3 -B - <<'PYTHON'
from sse_pos_r291_verified_vendor_package_only import signed_package_command
from sse_pos_r152_unattended_host_dependencies import install_verified_zerotier_apt
import subprocess
def visible_run(argv, **kwargs):
    def run(args, **opts):
        result = subprocess.run(args, **opts)
        if result.returncode and args[:1] == ["apt-get"]:
            print(result.stderr, flush=True)
        return result
    return signed_package_command(argv, run=run, **kwargs)
install_verified_zerotier_apt(runner=visible_run)
PYTHON
systemctl enable --now zerotier-one
ROOT_INSTALL
fi
sudo -n zerotier-cli join ff2328775f000000
for i in $(seq 1 30); do
 if /usr/bin/python3 -B -c 'import sys;sys.path.insert(0,"tools");from sse_pos_r291_common_public_overlay_onboarding import status;sys.exit(not status()["actualOpenOverlayReadyForCrossHostTransport"])'; then
   break
 fi
 sleep 3
done
/usr/bin/python3 -B -c 'import sys;sys.path.insert(0,"tools");from sse_pos_r291_common_public_overlay_onboarding import status;assert status()["actualOpenOverlayReadyForCrossHostTransport"]'
PRIVATE="$HOME/.local/share/sse-v2-app-only"
install -d -m 700 "$PRIVATE"
python3 -m venv "$HOME/.venvs/sse-v2-operator"
PY="$HOME/.venvs/sse-v2-operator/bin/python"
"$PY" -m pip install --disable-pip-version-check -r requirements.txt
"$PY" -B tools/sse_pos_test_wallet.py --role monitor --output-dir "$PRIVATE" --apply
echo "R328_MONITOR_IDENTITY_AND_OVERLAY_READY=true"
echo "R328_RPC_DASHBOARD_AND_FUNDED_ACTIVATION_PENDING=true"
