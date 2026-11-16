# R7 — Pinned Docker execution for a consumer-selected SSE compute lease

**Status:** research implementation, source and offline tests committed; **NOT YET VALIDATED ON OPERATOR SYSTEM**. Baseline `8811d32` passed 613 Python tests (608 pass, five skipped) and the opt-in real-Anvil two-bidder signed-delivery test (1 pass).

## Why this matters

Previously the winning provider signed a correct *locally recomputed Python* digest for deterministic compute. That demonstrated signed protocol messages and correctness, but **not that any Docker resource allocation was used**. This slice makes the *real* Ubuntu `--serve` path call an independently inspected Docker worker before producing the provider's EIP-712 result signature.

This **does not prove** the CPU time genuinely came from a trusted remote machine: the provider owns its Docker daemon and can deceive its counterparty. It is inspectable, resource-limited *reported execution*, not hardware attestation, independent physical delivery time, or an automatically payable SLA.

## Mandatory node ownership and auction gate

The established marketplace flow is unchanged:

1. Consumer commits `sse-resource-profile-v2` (immutable `imageDigest`, `cpuMilli`, `memoryBytes`, service endpoint) and `sse-service-sla-policy-v1` to its on-chain `OpenResourceBoard.requestResource`.
2. **Multiple providers bid**, consumer selects bid and funds that particular provider/price. The actual `SSESettlement` lease must have `marketplaceRequestId > 0`, correct winning provider EOA, positive escrow, zero reservation for the chosen delivery-only policy, hash-matching resource and SLA manifests.
3. Selected provider accepts, monitors are selected/confirmed, and consumer admits the epoch.
4. Signed consumer request goes **directly** over authenticated Tailscale Serve private HTTPS to the selected provider VM. The provider checks the pinned chain view and EIP-712 request.
5. For deterministic compute, the provider checks its local immutable-image Docker worker: exact Docker ID, NanoCpus, Memory, MemorySwap, PidsLimit, non-root UID, read-only filesystem, dropped capabilities, built-in seccomp, no-new-privileges, bridge networking, only a host-**loopback** published worker port, and no host binds/devices/additional ports. It runs the real Docker worker's HTTP `/v1/compute`, verifies the result against the known deterministic SHA-256 algorithm, then and **only then** signs both its compute-result commitment and the existing Solidity-compatible provider response.
6. Consumer verifies signatures and result, signs its own receipt. Provider persists in a local owner-only SQLite journal. The monitor evidence pipeline still needs independent physical qualification.

**What is NOT implemented:** independent CPU/RAM attestation; dynamic autoscheduling or multi-tenant capacity accounting; Docker daemon hard isolation from a compromised provider account; network egress deny from the bridge-networked Docker worker; guaranteed cross-provider Docker image distribution; immutable digest verification of the Dockerfile's mutable base before building; interruption/recovery replay of RESERVED work orders; independent remote monitor measurements; actual multi-VM Tailscale Serve deployment. These are explicit security and experimental gates.

## Locally prepare a pinned worker image (operator-owned action)

The repository has `Dockerfile.sse-compute`. From the *provider VM* or the development machine for Docker Desktop tests:

```bash
docker build -f Dockerfile.sse-compute -t sse-compute:r7 .
docker image inspect --format '{{.Id}}' sse-compute:r7
```

Use the actual output `sha256:<64 lowercase hex>` as `imageDigest` when creating the consumer's immutable V2 resource manifest, **before** bidding. Do not use the example `sha256:aaaa...` placeholders for actual worker execution. Every eligible provider needs the *same approved immutable image*, and the consumer must choose the image digest before funding.

The Docker build may access package registries. Its current Python base image tag is not itself pinned to a digest; creating a local immutable ID after build is **not** a complete reproducible supply-chain audit.

## Prepare consumer-selected manifests (safe/offline)

```bash
mkdir -p /tmp/sse-sla-r7
python tools/sse_sla_build.py --service-kind deterministic_compute \
  --endpoint https://provider.example.ts.net \
  --image-digest "sha256:<LOCALLY_INSPECTED_IMAGE_SHA256>" \
  --cpu-milli 500 --memory-bytes 536870912 \
  --chain-id 31337 --settlement 0x<DEPLOYED_SETTLEMENT_ADDRESS> \
  --output-dir /tmp/sse-sla-r7
```

These hashes become the on-chain resource and SLA commitments for the consumer marketplace request. Never rewrite manifests after a lease has been funded. The endpoint must exactly match the winning provider's configured Tailscale Serve origin and stored `serviceEndpointHash`.

## Launch the local worker on Ubuntu (DRY-RUN default)

Use separate local Docker worker port `8877` and SSE signed provider service port `8881`. The Docker worker runs inside the provider VM and has no role keys, EVM RPC credentials or public port.

```bash
python tools/sse_docker_worker_launch.py \
  --resource-profile /var/lib/sse/lease/sse-resource-profile.json \
  --sla-policy /var/lib/sse/lease/sse-sla-policy.json \
  --worker-endpoint http://127.0.0.1:8877 \
  --container-name sse-compute-lease01
```

The command above only prints a bounded, exact `docker run` argument array. Nothing is launched. After inspecting the plan, **only the provider owner** may add `--launch` on a non-root Linux VM with a local Docker Unix socket and a preloaded exact image ID. The launcher does not use `shell=True`, pull images, accept arbitrary host mounts, open a remote Docker context or mutate blockchain contracts.

The worker launches using a bounded `--cpus`, `--memory`, `--memory-swap`, `--pids-limit`, `--read-only`, `--user 10001:10001`, `--cap-drop ALL`, `--security-opt no-new-privileges:true` and `seccomp=builtin`, publishing only `127.0.0.1:8877`. The default bridge network can still have egress unless independently firewalled. For hostile multi-tenant workloads, a stronger sandbox/fully disabled networking is required.

Docker's official resource limits depend on kernel/cgroup support and may be unavailable or partially enforced in an incompatible rootless configuration. Check warnings and inspect actual cgroups on each Ubuntu VM before claiming resource compliance.

## Winning provider service (explicit live mode)

```bash
python services/provider-agent/direct_work_service.py \
  --policy /var/lib/sse/lease/sse-sla-policy.json \
  --resource-profile /var/lib/sse/lease/sse-resource-profile.json \
  --endpoint https://provider.example.ts.net \
  --rpc-url https://<TRUSTED_RPC_ORIGIN> \
  --signer-file /run/sse/provider.key \
  --journal-file /var/lib/sse/private/provider-journal.sqlite \
  --worker-endpoint http://127.0.0.1:8877 \
  --compute-container sse-compute-lease01 \
  --port 8881
```

Without `--serve`, this is a **preview** that sends no workload or Ethereum transaction. With `--serve`, real compute service kinds now **require** their pinned V2 profile and inspected Docker runtime; absent configuration fails closed. Tailscale Serve HTTPS and restrictive tailnet ACLs must be set up independently to forward only to `127.0.0.1:8881`. Never expose `8881` directly to public internet and never grant the container access to the provider key, chain signer files or Docker socket.

## Tests

Offline Windows/Python (no Docker or remote access):

```bash
python -m unittest discover -s tests -p 'test_sse_docker_sla_runner.py' -v
python -m unittest discover -s tests -p 'test_sse_docker_worker_launch.py' -v
python -m unittest discover -s tests -q
```

Optional local Docker Desktop or Ubuntu Docker Engine functional test. It will start and clean up a **real Docker container** on your current local Docker context; do not enable for a remote daemon.

**Windows Docker Desktop preflight:** The CLI can be present even if Docker Desktop's Linux Engine is stopped. Start Docker Desktop and select the Linux containers engine, then check `docker info --format '{{.OSType}}'` returns `linux`. If the error mentions `//./pipe/dockerDesktopLinuxEngine`, the engine is not reachable; don't proceed to image ID export or Anvil+Docker. The opt-in tests now skip with a clear prerequisite message when a local engine or immutable image ID is unavailable. The independent unit test for `os.geteuid` uses portable mocks on Windows.

```bash
docker info --format '{{.OSType}}'
docker build -f Dockerfile.sse-compute -t sse-compute:r7 . &&
  export SSE_DOCKER_WORKER_IMAGE="$(docker image inspect --format '{{.Id}}' sse-compute:r7)"
test -n "$SSE_DOCKER_WORKER_IMAGE" || { echo 'Docker image not built'; exit 1; }
SSE_RUN_DOCKER_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_docker_sla_live.py' -v
```

Optional more ambitious **Anvil + live Docker + competitive bidding + signed direct delivery** (same vetted local image ID, two opt-ins):

```bash
SSE_RUN_ANVIL_INTEGRATION=1 SSE_DIRECT_ANVIL_USE_DOCKER=1 \
 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

Without `SSE_DIRECT_ANVIL_USE_DOCKER=1`, the original opt-in Anvil test continues to use the previous deterministic in-process lab worker, for regression comparison. These new Docker-enabled tests **have not yet been executed**. Neither test uses real Tailscale, cloud VMs or externally trusted physical SLA monitoring.

## Next engineering requirements

1. Independently deployed Ubuntu consumer/provider/monitor VMs, Tailscale package/bootstrap and private HTTPS proxy
2. Host-specific Docker cgroup and egress policy validation; image digest distribution/registry authorization; capacity admission and scheduler
3. Consumer, provider and monitor node-local approval/execution UI for their own actions
4. Independent monitor raw signed evidence, archival replication, witness identity/operator independence, adjudication under network partitions
5. End-to-end QoS performance tests and meaningful paper/report evaluations
