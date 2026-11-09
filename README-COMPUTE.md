# SSE Milestone 3 — Local Docker compute + on-chain profile binding

## Scope and honesty

This patch extends the successful 63-test local Anvil E2E demonstration with an *optional* real Docker CPU worker. It does not modify Solidity, the old HTTP service, balances, deployment addresses, or the original E2E behavior unless `--compute-profile` **and** `--docker-container` are supplied.

- A real resource-limited Docker container runs a nonce-bound SHA-256 CPU job tied to the *new admitted epoch's* `requestHash`, `leaseId`, and `epochId`.
- Each monitor's on-machine probe independently recomputes the CPU result. Evidence files include the result/duration and are hashed and committed on-chain alongside the regular signed success vote.
- CPU cap, memory limit, read-only filesystem, local port binding, non-root UID, running status, and exact Docker image ID are inspected and matched to a canonical profile, whose Keccak hash is committed in the *new lease*.
- Contract signature/quorum/settlement is unchanged: EIP-712 provider response, 3 monitor votes, settlement, bond release, zero unresolved exposure.
- **Not claimed:** trusted hardware attestation, proof of actual CPU milliseconds, remote cloud provisioning, Byzantine monitor independence, trustworthy wall-clock receipt time, or actual marketplace bid selection. `computeProvisioningVerified` intentionally stays false. `localComputeWorkloadVerified` becomes true after successful Docker-backed checks.

## Installation

Unzip into the root of the existing SSE repo. Allow overwriting just these *existing* Python files:

- `tools/sse_e2e_local.py`: backward-compatible optional Docker mode
- `services/provider-agent/resource_profile.py`: fixes old missing import `challenge` -> `sse_challenge`

Added files:

- `Dockerfile.sse-compute` and `.dockerignore` (minimal build context)
- `tools/compute_workload.py`
- `tools/sse_compute_docker.py`
- `services/provider-agent/compute_http_service.py`
- `tests/test_sse_compute_docker.py`

No contract modifications or migrations.

## Terminal steps (Git Bash, project root)

**Prerequisites:** Docker Desktop is installed and running in Linux container mode. Local Anvil and SSESettlement still run at the known address. Your existing Python venv is activated.

### 1. Build and launch the isolated worker

```bash
docker info
docker build -f Dockerfile.sse-compute -t sse-compute-worker:local .
docker run -d \
  --name sse-compute-worker \
  --cpus=0.5 --memory=256m \
  --read-only --pids-limit=64 \
  --security-opt=no-new-privileges --cap-drop=ALL \
  -p 127.0.0.1:8888:8877 \
  sse-compute-worker:local
```

The **first build** may download `python:3.12-slim` and pinned `pycryptodome`. Docker runs a *separate* container on port **8888**, so the previously working provider HTTP service on 8877 is not disturbed.

Check that the worker is reachable:

```bash
docker ps --filter 'name=sse-compute-worker'
python -c 'import json, urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8888/healthz")))'
```

If `docker run` says the name is already taken from a previous attempt, don't rebuild or replace anything blindly: run `docker ps -a --filter name=sse-compute-worker` and check whether the existing container is already the intended one. For a *deliberate local reset of only this demo container*: `docker stop sse-compute-worker` then `docker rm sse-compute-worker`, then repeat the `docker run` command. This never touches the SSE smart contract or Anvil.

### 2. Commit the exact running resource specification

```bash
IMAGE_ID=$(docker image inspect sse-compute-worker:local --format '{{.Id}}')
python services/provider-agent/resource_profile.py \
  --image-id "$IMAGE_ID" \
  --endpoint http://127.0.0.1:8888 \
  --cpu-milli 500 \
  --memory-bytes 268435456 \
  --output .local/sse-compute-profile.json
```

The resulting canonical resource profile records image ID, 500 millicores, 256 MiB, and endpoint; its Keccak commitment becomes the `resourceProfileHash` in the newly created lease. It does *not* rewrite the historical lease-2 hash.

### 3. Test, preflight, then run the full new lease

```bash
export RPC_URL="http://127.0.0.1:8545"
export NEW_SSE="0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82"
python -m unittest discover -s tests -q
forge test -q
python tools/sse_e2e_local.py \
  --rpc-url "$RPC_URL" --settlement "$NEW_SSE" \
  --endpoint http://127.0.0.1:8888 \
  --compute-profile .local/sse-compute-profile.json \
  --docker-container sse-compute-worker
```

**Expected:** 79 Python tests pass, 17 Solidity tests pass, then `PREFLIGHT_OK`. Preflight sends no blockchain transactions. It checks the worker's live Docker limits and an example CPU job.

Execute the new lease and epoch:

```bash
python tools/sse_e2e_local.py \
  --rpc-url "$RPC_URL" --settlement "$NEW_SSE" \
  --endpoint http://127.0.0.1:8888 \
  --compute-profile .local/sse-compute-profile.json \
  --docker-container sse-compute-worker \
  --execute --fast-forward
```

The new run creates a fresh lease with an independently committed profile; expected progress includes `REAL_LOCAL_COMPUTE_OBSERVED`, three signed votes, `BONDS_RELEASED`, and `SUCCESS_COMPLETE`. The console JSON should show `localComputeWorkloadVerified: true` and `remoteCloudProvisioningVerified: false`.

Artifacts appear at `.local/sse-e2e-runs/lease-<new_id>/` including the new `provider_compute_observation.json`, `provider_http_observation.json`, `monitor_1_evidence.json`, `monitor_2_evidence.json`, `monitor_3_evidence.json`, and `run.json`. **Keep evidence files** for your paper/demo. `--fast-forward` simulates blockchain time and must not be reported as physical elapsed time.

If anything fails, the script stops without emitting success votes for a failed compute result; previously mined transactions are *not* rolled back. Do not reset Anvil or redeploy. Share the terminal traceback and the last `run.json` status.

## Testing performed by the patch author

The 63 previous Python tests and 16 new tests passed in a local isolated execution with a verified test-only Keccak implementation substituted for an unavailable `pycryptodome`. The new CPU HTTP worker was served and checked in-process; Docker CLI responses were tested using mocks. Docker is **not installed** in the authoring sandbox, so Docker isolation, Windows Docker Desktop behavior, and actual integration with your Anvil are **not yet runtime-verified**. Solidity sources were left unchanged; their existing 17 tests were previously reported passing by the user.
