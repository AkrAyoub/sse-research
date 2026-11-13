# WP-17 — Docker bridge and TLS-isolated V2 monitor/provider laboratory

**Research classification: reproducible same-machine container network-isolation experiment. NOT an independent-cloud experiment or physically qualified SLA certificate.**

## Why this increment exists

WP-15 proved real Anvil contract/RPC integration with signed HTTP and historical V2 authority archiving. WP-16 proved **separate operating-system processes** and seven local network-fault scenarios, but both agents shared a host network namespace and used loopback HTTP.

WP-17 now runs the **provider and monitor in distinct Docker containers and network namespaces** on a dedicated private bridge. Their inter-container transport uses TLS 1.2+ with verified hostname `provider.wp17` and a run-generated, explicitly pinned trust certificate. The monitor still executes the strict V2 RPC/evidence/archival code from WP-13–16: **no remote HTTP URL was added to the production verifier's accepted input format**.

One ephemeral CI runner is still the trusted administrator of the container infrastructure, all test keys, certificate generation and Anvil. This does **not** establish independent-host, independent-operator, internet-scale or adversarial RPC safety.

## Architecture and execution

```text
                 GitHub Actions ephemeral Linux runner
          (single administrator; publicly known Anvil keys)
                                |
          +---------------------+------------------------+
          |                     |                        |
 [Consumer / host Python] [Anvil JSON-RPC]     [Docker bridge network]
          |                0.0.0.0:8545             |
          |                     |                   |
          |     +---------------+----------+        |
          |     |                          |        |
          v     v                          v        v
 WP15 prepare-only        [MONITOR Docker container]    [PROVIDER Docker container]
 - funded V2 lease         own network namespace        own network namespace
 - selected committee      local 127.0.0.1:8545        TLS :9443, not host-published
 - 1 admitted epoch        -> trusted host Anvil        legacy V1 ProviderResponse
 - fixed endpoint hash     local 127.0.0.1:PORT         signer = on-chain provider key
                           -> TLS-pinned tunnel   --->  signed HTTPS challenge
                           WP16 monitor evidence
                           WP13 pinned EIP-1898 RPC
                           WP14 atomic SQLite archive
                                     |
                       host validates all entries against
                       original historical Anvil block
                                     |
                       expire pool / end admissions:
                       fresh authority FAILS,
                       historical evidence still PASSES,
                       tampered bytes FAIL,
                       unilateral provider credits == 0
```

### Important transport trust distinction

The **on-chain commitment remains** the exact original `http://127.0.0.1:PORT` service root. A monitor-local tunnel converts that address into a TLS-protected connection to `provider.wp17:9443` in a separate Docker namespace.

This design **does not cryptographically commit the remote DNS endpoint or certificate into the lease**. The pinned certificate is passed as a local experimental transport trust anchor; the signed provider response is still verified against the on-chain provider address and request. A production remote-endpoint protocol needs an explicit endpoint/TLS-identity commitment, a documented rotation policy, independent DNS/CA trust and tests against wrong server identity. Do **not** claim WP-17 implements that policy.

The monitor's **RPC connection to host-gateway:8545 is NOT TLS authenticated or consensus verified**. The host's Anvil is deliberately trusted, `latest` is explicitly unfinalized and the mock coordinator does not prove a Chainlink VRF. EIP-1898 verifies internal block-hash consistency against this trusted node, not finality against malicious consensus peers.

### Process and file separation

- Provider runs `services/provider-agent/wp17_tls_provider.py` in its own container with a *read-only private credential mount* and a run-specific self-signed TLS certificate. It listens only on container port 9443, not a published host port.
- Monitor runs `services/monitor-agent/wp17_container_monitor.py` in a **different** container with a separate mount containing only the public provider certificate, scope manifest and its SQLite archive. It cannot read the provider's TLS private key through this mount.
- Both containers use a nonroot host UID, read-only root filesystem, a temporary `/tmp`, dropped capabilities and `no-new-privileges`. These are laboratory hardening measures, not complete tenant isolation.
- Provider and monitor Ethereum private keys are the **public Anvil mnemonic keys only**, injected into ephemeral container environments. Environment secrets would be visible to a Docker administrator; this technique must never handle production private keys.
- `infra/wp17/Dockerfile` and its **Dockerfile-specific ignore file** restrict the container build to Python requirements, tools and services. No Foundry artifacts, test reports or repository .git directory should be shipped into that image.
- Docker bridge DNS provides `provider.wp17`; the monitor's TLS context verifies this exact hostname against the supplied pinned run certificate. Proxies and redirects from the original HTTP transport remain disabled.
- The monitor's `LocalRPC` and `V2AuthoritySpec` are unchanged; their strict loopback validation, provider/monitor signatures, historical EIP-1898 checks, nonce uniqueness and fail-closed archive logic are reused rather than copied or weakened.

## Eight adversarial integration cases

Each case uses the *same* admitted V2 epoch with a fresh monotonic evidence nonce, and a newly launched monitor container; provider containers are started/stopped between scenarios. Each case checks the on-chain provider's withdrawable balance.

| # | Scenario | Expected outcome | Evidence rows |
|---:|---|---|---:|
| 1 | Correct provider signature over DNS-verified TLS | Accepted RAW observation (selected monitor A) | 1 |
| 2 | Healthy TLS server with independently generated **untrusted** certificate | Transport rejected; no new evidence | 1 |
| 3 | TLS provider intentionally sleeps 1.5 seconds; monitor timeout 0.35 seconds | Monitor-local transport timeout; **no failure verdict** | 1 |
| 4 | HTTPS response returns 503 | Transport error; no new record | 1 |
| 5 | Provider uses wrong Anvil signing key | ProviderResponseInvalid; no new record | 1 |
| 6 | Monitor uses unselected Anvil account | AuthenticationError; no new record | 1 |
| 7 | Running provider has its Docker network disconnected | Transport rejected; no new record | 1 |
| 8 | Valid TLS provider restarted and **different selected monitor B** captures | Second authenticated RAW observation | 2 |

The network-disconnect case first starts a live TLS provider and checks its health before disconnecting its Docker bridge attachment. It reattaches for cleanup, and the final recovery case starts a new provider process. Thus WP-17 does not claim an in-flight session was transparently restored.

After all cases, the host calls the real pool expiry and controller admissions-stop functions. It verifies that a new current-state authorization fails and both **original** archived observations still verify against their respective historical Anvil block hashes. It then changes the first stored HTTP body to `{}`, requires validation failure, restores the exact original signed bytes and requires valid re-verification. No raw HTTP observation can pay the provider unilaterally.

The experiment collects elapsed local timings, scenario error classifications, the deployed addresses/selected committee, the TLS certificate fingerprint, and on-chain transaction receipts. It neither records an authentic consumer-delivery receipt nor evaluates a service-specific SLA truth predicate.

## Reproducible implementation

New files:

1. `infra/wp17/Dockerfile` and `infra/wp17/Dockerfile.dockerignore` — minimal agent image with restricted build context.
2. `services/provider-agent/wp17_tls_provider.py` — TLS-only provider using the existing signed-response construction; supports bounded delay or HTTP 503.
3. `services/monitor-agent/wp17_container_monitor.py` — two small loopback TCP forwarders: **untrusted lab Anvil RPC** and **hostname-/certificate-verified TLS** to the Docker provider; invokes WP-16 verifier unchanged.
4. `scripts/wp17_docker_tls_lab.py` — real Anvil funded lease setup, ephemeral TLS certificate creation, Docker network/container lifecycle, eight fault scenarios, SQLite/EIP-1898 historical verification and negative finance assertions.
5. `.github/workflows/wp17-docker-tls.yml` — CI job builds Docker image, starts a fresh Anvil with public test accounts, executes WP-17 and uploads **only** a sanitized JSON trace. No Anvil logs, private TLS keys or Docker inspect output.

Run on an *isolated Linux development machine or ephemeral CI runner only*:

```bash
python -m pip install -r requirements.txt
bash scripts/install-contract-deps.sh
forge build
docker build -f infra/wp17/Dockerfile -t sse-wp17-lab .
anvil --host 0.0.0.0 --port 8545 --chain-id 31337 --accounts 12 \
    --mnemonic 'test test test test test test test test test test test junk'
```

Then in another terminal:

```bash
python scripts/wp17_docker_tls_lab.py --output artifacts/wp17-docker-tls-lab.json
```

**Caution:** binding Anvil to `0.0.0.0:8545` exposes an intentionally unlocked and insecure development RPC on the host's interfaces so Docker bridge clients can connect. Do this **only on a locked-down, ephemeral or firewall-isolated machine**. Do not use this binding or public mnemonic on any persistent production host. A subsequent increment should use a dedicated private RPC service, pinned TLS or network-policy-restricted access.

## Verified hosted CI

First full hosted WP-17 run:
- [WP-17 Docker/TLS run](https://github.com/AkrAyoub/sse-research/actions/runs/43394460285) — **8/8 cases passed**, two authenticated RAW evidence archives, original historical EIP-1898 verification succeeded after closure, tampered-byte rejection passed, **0 unauthorized provider credits**.
- [Sanitized run artifact](https://github.com/AkrAyoub/sse-research/actions/runs/43394460285/artifacts/14021689391) — includes only the JSON experiment trace.
- [Inherited WP-16 distinct-process tests](https://github.com/AkrAyoub/sse-research/actions/runs/43394460169) — passed unchanged.
- [Inherited WP-15 real Anvil integration](https://github.com/AkrAyoub/sse-research/actions/runs/43394460124) — passed unchanged.
- [Python/Foundry CI](https://github.com/AkrAyoub/sse-research/actions/runs/43394460007) — Ubuntu **410/410**, Windows **410/410**, Solidity Foundry **124/124**, zero failures/skips.

These results establish **laboratory network-namespace and TLS interoperability**. They do not establish multi-cloud independence, physical SLA truth or fair automatic payments.

## Next research gates

1. **Review and consolidate draft PRs #9–#17**, retargeting in dependency order and rerunning the entire suite after each merge. WP08C #8 remains independent. No draft should be merged without explicit approval.
2. Design and test a **V2-native versioned remote provider endpoint identity**: pinned host/cert commitments, authenticated RPC origins, safe proxy configuration, revocation and expiry handling; remove the transparent tunnel before claiming a production remote-monitor protocol.
3. Run truly independent provider and monitor nodes on separately administered machines or cloud VMs, with each role retaining its own private keys and archives. Introduce controlled latency, NAT, partitions, clock disagreement and failed host restarts.
4. Fund a genuine supported Chainlink VRF v2.5 coordinator/subscription on testnet and verify that the selected committee comes from a real proof-verified callback rather than the insecure mock.
5. Establish **sound consumer-delivery facts** or a formally justified fallback dispute mechanism. Correct signatures and VRF-selected monitor agreement still cannot establish the N/F/S physical history.
6. Replicate and externally anchor archive commitments so a single host administrator cannot delete or suppress all evidence; publish repeatable multi-host performance/latency and adversarial cost datasets.

**Milestone status:** WP-17 completes the narrower containerized transport/namespace fault lab. R5 receives moderate implementation credit and R9 only small preliminary laboratory credit; independent-host R9 exit criteria remain unmet.
