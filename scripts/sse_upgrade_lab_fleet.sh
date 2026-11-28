#!/usr/bin/env bash
# Safe lab fleet dispatch. Not a permissionless admission allowlist.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SHA="$(git rev-parse HEAD)"
WEB=()
if [[ "${1:-}" == --publish-web ]]; then WEB=(--publish-web); elif [[ $# != 0 ]]; then exit 2; fi
[[ "$(id -u)" != 0 && -z "$(git status --porcelain)" ]]
case "$(id -un)" in
  ayoubakrvm4709)
    python3 -B scripts/sse_v4_upgrade_managed_rpc.py --mode serve --commit "$SHA" --allow-raw-send --apply
    ;;
  ayoubakrvm4706|ayoubakrvm4708|ayoubakrvm4721)
    echo "Native/unknown host: read-only inventory; no changes to chain clients."
    whoami; nproc; free -h; df -h /
    sudo -n docker ps -a || true
    python3 -B tools/sse_setup_verify_local_native.py || true
    ;;
  *)
    POL="$HOME/.config/sse-v4/policy.json"
    if [[ -f "$POL" ]]; then
      bash scripts/sse_install_participant.sh --upgrade "${WEB[@]}"
    else
      case "$(id -un)" in
        ayoubakrvm4707) ROLES=consumer,monitor,keeper ;;
        ayoubakrvm4711|ayoubakrvm4713|ayoubakrvm4715|ayoubakrvm4720) ROLES=monitor,keeper ;;
        ayoubakrvm4712) ROLES=monitor,consumer ;;
        ayoubakrvm4714|ayoubakrvm4717|ayoubakrvm4718) ROLES=provider,monitor ;;
        ayoubakrvm4719) ROLES=consumer,monitor,keeper ;;
        *) ROLES="" ;;
      esac
      bash scripts/sse_install_participant.sh --upgrade "$ROLES" "${WEB[@]}"
    fi ;;
esac
