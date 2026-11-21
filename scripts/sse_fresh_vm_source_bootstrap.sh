#!/usr/bin/env bash
# R145 HISTORICAL LAB PROTOTYPE; interactive apply is disabled by R146.
# NOT the zero-interaction onboarding installer; see docs/R146_ZERO_INTERACTION_CORRECTIVE_ARCHITECTURE_AUDIT.md.
# No Ethereum node, validator, Docker, ZeroTier, wallet, or role is started.
set -Eeuo pipefail

usage() {
  cat <<'HELP'
Usage:
  bash scripts/sse_fresh_vm_source_bootstrap.sh --plan  --ssh-key /path/to/read-only-deploy-key --commit FULL_40_SHA --node-id host-id --roles full_node
  bash scripts/sse_fresh_vm_source_bootstrap.sh --apply --ssh-key /path/to/read-only-deploy-key --commit FULL_40_SHA --node-id host-id --roles full_node

The repository is private. Provision a per-host READ-ONLY GitHub deploy key
and independently authenticated github.com SSH host key first.
--plan never installs packages, writes files, or talks to GitHub.
--apply is RETIRED (fails closed). Historical code below remains for audit.
clones this single repository at a reviewed immutable SHA and runs the
unified NONMUTATING role-selection plan. No other components are installed.
HELP
}

refuse() { printf 'R145_SOURCE_BOOTSTRAP_REFUSED: %s\n' "$1" >&2; exit 2; }
MODE='' SSH_KEY='' COMMIT='' NODE_ID='' ROLES=''
while (($#)); do
  case "$1" in
    --plan|--apply)
      [[ -z "$MODE" ]] || refuse 'select one mode'
      MODE="$1"; shift ;;
    --ssh-key|--commit|--node-id|--roles)
      (($# >= 2)) || refuse "missing argument for $1"
      case "$1" in
        --ssh-key) SSH_KEY="$2" ;;
        --commit) COMMIT="$2" ;;
        --node-id) NODE_ID="$2" ;;
        --roles) ROLES="$2" ;;
      esac
      shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) refuse 'unexpected argument' ;;
  esac
done

[[ "$MODE" == '--plan' || "$MODE" == '--apply' ]] || refuse 'missing mode'
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || refuse 'expected reviewed full lowercase Git SHA'
[[ "$NODE_ID" =~ ^[a-z][a-z0-9-]{2,62}$ ]] || refuse 'invalid node label'
[[ "$ROLES" =~ ^[a-z_]+(,[a-z_]+)*$ ]] || refuse 'invalid comma-separated roles'
declare -A SELECTED_ROLES=()
IFS=',' read -r -a ROLE_ARRAY <<< "$ROLES"
for role in "${ROLE_ARRAY[@]}"; do
  case "$role" in
    full_node|observer|validator|provider|consumer|monitor) ;;
    *) refuse 'unknown role' ;;
  esac
  [[ ! -v "SELECTED_ROLES[$role]" ]] || refuse 'duplicate role'
  SELECTED_ROLES["$role"]=1
done
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
  refuse 'reviewed Linux x86_64 host required'
[[ "$HOME" == /* && "$HOME" != '/' ]] || refuse 'unsafe home directory'
TARGET="$HOME/sse-research"
[[ ! -e "$TARGET" && ! -L "$TARGET" ]] ||
  refuse 'existing source checkout/path: do not overwrite or retry'
for state in \
  "$HOME/.local/share/sse-r35-chain31340-g2-private" \
  "$HOME/.local/share/sse-r27-bls-operator-private" \
  "$HOME/.local/share/sse-r59-chain31340-observer"; do
  [[ ! -e "$state" && ! -L "$state" ]] ||
    refuse 'existing signer/observer state: fresh-host workflow forbidden'
done
[[ "$SSH_KEY" == /* && -f "$SSH_KEY" && ! -L "$SSH_KEY" ]] ||
  refuse 'operator-specific deploy key must be an existing regular absolute path'
if command -v stat >/dev/null 2>&1; then
  perms="$(stat -c '%a' "$SSH_KEY")" || refuse 'cannot inspect key permissions'
  case "$perms" in 400|600) ;; *) refuse 'deploy private key must have 0400 or 0600 permissions';; esac
fi

printf 'R145_SOURCE_BOOTSTRAP_PLAN_V1\n'
printf 'nodeId=%s\nroles=%s\ncheckout=%s\nsourceRevision=%s\n' \
  "$NODE_ID" "$ROLES" "$TARGET" "$COMMIT"
printf 'privateGitHubAccessRequired=true\n'
printf 'existingChainOrValidatorWillChange=false\n'
printf 'sourceDownloaded=false\n'
printf 'packagesInstalled=false\n'
printf 'rolesInstalled=false\n'
if [[ "$MODE" == '--plan' ]]; then
  printf 'status=PLAN_ONLY_NO_MUTATION\n'
  exit 0
fi

# R146: never execute the legacy manual SSH-key + typed-prompt installer.
# Retain read-only plan support only for regression/provenance history.
refuse 'R145 manual apply retired: use reviewed zero-interaction infrastructure bootstrap (R146)' 
[[ "$EUID" != 0 ]] || refuse 'run apply as ordinary local owner, not root'
[[ -t 0 && -t 2 ]] || refuse 'create-once apply requires an interactive local terminal'
printf '%s\n' 'R145 installs ONLY basic git/Python/SSH source tools and clones pinned SSE source.' \
  'It will NOT install Docker, join ZeroTier, create validator keys, or broadcast transactions.' >&2
read -r -p 'Type BOOTSTRAP-SSE-SOURCE to authorize: ' ANSWER
[[ "$ANSWER" == 'BOOTSTRAP-SSE-SOURCE' ]] || refuse 'operator authorization absent'

# The only root changes are ordinary OS package installation with local sudo.
if ! command -v git >/dev/null || ! command -v python3 >/dev/null || \
   ! command -v ssh >/dev/null; then
  command -v apt-get >/dev/null || refuse 'Ubuntu apt-get is unavailable'
  command -v sudo >/dev/null || refuse 'sudo is unavailable'
  sudo apt-get update
  sudo apt-get install -y git python3 openssh-client ca-certificates
fi
command -v git >/dev/null && command -v ssh >/dev/null && \
  command -v python3 >/dev/null || refuse 'source tooling unavailable'

# Refuse unauthenticated/interactive host-key acceptance and passwords.
# Only the per-host read-only key is offered, never exported or displayed.
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes"
git clone --no-checkout git@github.com:AkrAyoub/sse-research.git "$TARGET" ||
  refuse 'private GitHub checkout failed; inspect authentication and partial directory'
cd "$TARGET"
git fetch --no-tags origin feature/r136-independent-observer-preflight ||
  refuse 'requested source branch unavailable'
git cat-file -e "$COMMIT^{commit}" || refuse 'reviewed source commit not fetched'
git merge-base --is-ancestor "$COMMIT" FETCH_HEAD ||
  refuse 'reviewed commit not in fetched development branch history'
git switch --detach "$COMMIT"
[[ "$(git rev-parse HEAD)" == "$COMMIT" ]] || refuse 'pinned commit mismatch'

python3 -B tools/sse_join.py --node-id "$NODE_ID" --roles "$ROLES" --plan
printf '%s\n' 'R145_SOURCE_BOOTSTRAP_COMPLETED=true' \
  'R145_CONSENSUS_CLIENTS_OR_ROLES_INSTALLED=false' \
  'R145_VALIDATOR_KEYS_OR_TRANSACTIONS_CREATED=false'
