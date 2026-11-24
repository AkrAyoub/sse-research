#!/usr/bin/env bash
# R281 dedicated VM4714: optional REAL Docker CPU worker, no chain or keys.
# Default --preview has no side effects. --run requires local owner typed
# consent and healthy access to the local Docker socket; never sudo/fallback.
# Actual 8192 SHA256 requests are real CPU work, but pre-lease measurements
# are NOT paid onchain SLA, independent hardware attestation or service proof.
set -euo pipefail
umask 077

PIN="${1:-}"
MODE="${2:-}"
if [[ ! "$PIN" =~ ^[0-9a-f]{40}$ ]]; then
  echo "R281_REFUSED: exact lowercase 40-hex pinned Git SHA required" >&2
  exit 2
fi
if [[ "$MODE" != "--preview" && "$MODE" != "--run" && "$MODE" != "--run-sudo" ]]; then
  echo "R281_REFUSED: use --preview (no effects), --run (nonroot), or --run-sudo (dedicated VM only)" >&2
  exit 2
fi
if [[ "$(id -un)" != "ayoubakrvm4714" || "$(id -u)" == 0 ]]; then
  echo "R281_REFUSED: dedicated nonroot VM4714 owner only" >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "$(git rev-parse HEAD)" != "$PIN" ]]; then
  echo "R281_REFUSED: actual Git commit differs from reviewed exact SHA" >&2
  exit 2
fi
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "R281_REFUSED: tracked source modifications present" >&2
  exit 2
fi
for p in Dockerfile.sse-compute tools/sse_compute_docker.py tools/compute_workload.py services/provider-agent/compute_http_service.py; do
  if [[ ! -f "$p" || -L "$p" ]]; then
    echo "R281_REFUSED: required real source missing or symlinked: $p" >&2
    exit 2
  fi
done

NAME="sse-compute-vm4714"
TAG="sse-compute-r281:${PIN:0:12}"
SOCKET="unix:///var/run/docker.sock"
LOCAL="http://127.0.0.1:8877"
CPUS="0.5"
MEMORY="256m"

echo "R281_PUBLIC_REAL_COMPUTE_WORKER_PLAN=owner:ayoubakrvm4714 chain:31340 name:$NAME tag:$TAG cpu:$CPUS memory:$MEMORY loopback:$LOCAL rootfs:readonly caps:none pids:32 seccomp:builtin dockerSocket:local nativeTransactions:false"

if [[ "$MODE" == "--preview" ]]; then
  echo "R281_PREVIEW_ONLY_NO_DOCKER_ACTIONS_NO_KEYS_NO_TX=true"
  exit 0
fi

if [[ ! -t 0 || ! -t 2 ]]; then
  echo "R281_REFUSED: real owner TTY required for new Docker worker" >&2
  exit 2
fi

CONSENT="START-ONE-R281-REAL-COMPUTE-VM4714"
if [[ "$MODE" == "--run-sudo" ]]; then
  # Privileged Docker API is effectively root on THIS dedicated lab VM.
  # The user must explicitly choose this mode; NO privilege fallback.
  CONSENT="START-ONE-R283-DEDICATED-VM4714-SUDO-DOCKER-COMPUTE"
fi
read -r -p "Type $CONSENT to BUILD and START ONE localhost-only dedicated CPU worker: " CONFIRM
if [[ "$CONFIRM" != "$CONSENT" ]]; then
  echo "R281_REFUSED: exact local authorization absent" >&2
  exit 2
fi

if [[ ! -S /var/run/docker.sock || -L /var/run/docker.sock ]]; then
  echo "R281_REFUSED: local Docker Unix socket missing or symlinked" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "R281_REFUSED: Docker client unavailable" >&2
  exit 2
fi
DOCKER=(docker --host "$SOCKET")
if [[ "$MODE" == "--run-sudo" ]]; then
  if [[ "$(stat -c %u /var/run/docker.sock)" != "0" ]] ||
    ! command -v sudo >/dev/null 2>&1; then
    echo "R283_REFUSED: root-owned local socket and existing sudo binary required" >&2
    exit 2
  fi
  DOCKER=(sudo -n docker --host "$SOCKET")
elif [[ ! -r /var/run/docker.sock || ! -w /var/run/docker.sock ]]; then
  echo "R281_REFUSED: owner lacks local Docker Unix socket access; NO automatic sudo fallback" >&2
  exit 2
fi
# No Docker CLI environment variables, TLS endpoints or remote daemon.
unset DOCKER_CONTEXT DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH

if ! "${DOCKER[@]}" info --format '{{.ServerVersion}}' >/dev/null; then
  echo "R281_REFUSED: local Docker daemon inaccessible" >&2
  exit 2
fi
EXISTING="$("${DOCKER[@]}" ps -a -q)"
if [[ -n "$EXISTING" ]]; then
  echo "R281_REFUSED: dedicated compute host has existing Docker containers; do not disturb them" >&2
  exit 2
fi

# Real image build uses the repository's already-existing Dockerfile.
# The image digest is measured AFTER build, not guessed or precommitted.
"${DOCKER[@]}" build --pull=false --file Dockerfile.sse-compute --tag "$TAG" .
IMAGE_ID="$("${DOCKER[@]}" image inspect "$TAG" --format '{{.Id}}')"
if [[ ! "$IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "R281_REFUSED: real Docker image ID invalid" >&2
  exit 2
fi

# NO public ports, host networking, Docker socket mounts, privileged
# workers, editable rootfs, added capabilities or host volume mounts.
CID="$("${DOCKER[@]}" run --detach --rm \
  --name "$NAME" \
  --network bridge \
  --publish 127.0.0.1:8877:8877 \
  --read-only \
  --user 10001:10001 \
  --cpus "$CPUS" \
  --memory "$MEMORY" \
  --memory-swap "$MEMORY" \
  --pids-limit 32 \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --security-opt seccomp=builtin \
  "$IMAGE_ID")"
if [[ ! "$CID" =~ ^[a-f0-9]{64}$ ]]; then
  echo "R281_REFUSED: Docker did not return exact 64-hex worker container ID" >&2
  exit 2
fi

KEEP=false
cleanup_if_unverified() {
  if [[ "$KEEP" != true ]]; then
    # Only the exact container created by this single call, never nodes.
    "${DOCKER[@]}" container rm --force "$CID" >/dev/null 2>&1 || true
  fi
}
trap cleanup_if_unverified EXIT

# Real source module does FULL strict hardening audit of the actual Docker
# config plus independent localhost CPU calculation and live HTTP request.
PY="$HOME/.local/share/sse-v2-app-only/pyvenv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "R281_REFUSED: existing isolated app-only Python venv missing" >&2
  exit 2
fi
IMAGE_ID="$IMAGE_ID" R283_EXPLICIT_VM4714_SUDO_DOCKER="$([[ "$MODE" == "--run-sudo" ]] && echo 1 || echo 0)" PYTHONPATH="$ROOT/tools:$ROOT/services/provider-agent" "$PY" -B - <<'PY'
import json
import os
import secrets
from sse_compute_docker import inspect_container, run_compute_probe

profile={
    "endpoint":"http://127.0.0.1:8877",
    "imageId":os.environ["IMAGE_ID"],
    "cpuMilli":500,
    "memoryBytes":256*2**20
}
verified=inspect_container(profile,profile["endpoint"],"sse-compute-vm4714",
                           strict_hardening=True,
                           dedicated_vm4714_sudo_docker=(
                             os.environ.get("R283_EXPLICIT_VM4714_SUDO_DOCKER")=="1"
                           ))
if verified["runtimeReportedRunning"] is not True:
    raise SystemExit("R281_REAL_DOCKER_WORKER_NOT_RUNNING")
challenge="0x"+secrets.token_hex(32)
obs=run_compute_probe(profile["endpoint"],1,0,challenge)
if obs["workloadResultVerified"] is not True or obs["rounds"]!=8192:
    raise SystemExit("R281_REAL_CPU_HASH_RESULT_MISMATCH")
print(json.dumps({
 "schema":"SSE_R281_VM4714_REAL_PRELEASE_CPU_WORKER_OBSERVATION_V1",
 "imageId":profile["imageId"],
 "actualDockerConfigInspected":True,
 "imageCpuRamAndIsolationCapsVerified":True,
 "requestHash":challenge,
 "realMeasuredLocalElapsedSeconds":obs["elapsedSecondsLocal"],
 "actualComputeResultVerified":True,
 "resultDigest":obs["resultDigest"],
 "rounds":obs["rounds"],
 "localhostOnlyWorker":True,
 "onChainLeaseOrSlaProven":False,
 "onChainTransactionSent":False,
 "nativeNodeOrWalletAccess":False,
 "dedicatedOwnerAuthorizedSudoDocker":(
   os.environ.get("R283_EXPLICIT_VM4714_SUDO_DOCKER")=="1"
 )
},sort_keys=True,indent=2))
PY
KEEP=true
trap - EXIT
if [[ "$MODE" == "--run-sudo" ]]; then
  echo "R283_VM4714_ACTUAL_DEDICATED_SUDO_DOCKER_CPU_WORKER_VERIFIED=true"
else
  echo "R281_VM4714_ACTUAL_ISOLATED_CPU_WORKER_RUNNING_AND_VERIFIED=true"
fi
echo "R281_WORKER_CONTAINER_ID=$CID"
echo "R281_REAL_WORKER_IMAGE_ID=$IMAGE_ID"
