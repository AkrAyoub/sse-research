# R1/R4/R5/R7 — Bidding-first SLA policy and chosen-provider direct workload exchange

**Status:** implementation source + offline tests committed. NOT yet tested by the operator; not deployed on Ubuntu; no actual Tailscale Serve, container limit or physical SLA certification demonstrated. Historical green baseline: `research/r5-real-anvil-wallet-flow-no-ci`, 580 discovered tests, 576 passed/4 skipped plus 1 opt-in real-Anvil integration passed.

## Marketplace is mandatory; the direct exchange does NOT replace provider bidding

1. **Consumer VM** chooses a versioned `sse-resource-profile-v2` and `sse-service-sla-policy-v1`. `tools/sse_sla_build.py` writes canonical manifests and computes immutable `resourceProfileHash`, `slaPolicyHash` and `serviceEndpointHash` offline.
2. Consumer's own node wallet calls `OpenResourceBoard.requestResource(profileHash, policyHash, maxEpochFeeWei, biddingClose)` via `tools/sse_node_marketplace.py`. A consumer **does not bid**; the consumer declares the request and price ceiling.
3. **Multiple provider VMs** may call `OpenResourceBoard.placeBid(requestId, epochFeeWei)`, each under its own owner-controlled signer, until bidding closes. Neither the network dashboard nor the consumer impersonates providers.
4. The consumer reviews all provider offers and explicitly calls `chooseBidAndFundLease(requestId,bidIndex,settlement,LeaseConfig)`. This commits the **winning provider identity**, endpoint hash, resource hash, SLA policy hash, economic terms and test ETH into `SSESettlement`. For `DELIVERY_ONLY_ZERO_RESERVATION_V1`, use `reservationFeeWei=0`. The contract currently does not automatically pick the lowest bid.
5. Winning provider calls `acceptLease`; monitoring committee is selected and confirms; consumer calls `admitEpoch(leaseId,requestHash)`. No direct service request is eligible before the lease is Active and the epoch is actually admitted.
6. **Direct data plane:** consumer VM sends a signed EIP-712 `SSEConsumerWorkRequest` over authenticated Tailscale Serve HTTPS to the selected provider VM. `tools/sse_direct_delivery.py` and `services/consumer-agent/direct_work_client.py` check a pinned on-chain inspection and ensure that `marketplaceRequestId>0`, escrow>0, SLA and resource hashes match, endpoint is committed, consumer is the lease owner, and requestHash belongs to the admitted epoch.
7. Provider's loopback-only `services/provider-agent/direct_work_service.py` independently reads the active chain lease, confirms that **its own EOA is the chosen provider**, verifies the consumer request signature, and computes the requested service result. HTTP challenges use the V1 response commitment; deterministic compute reuses `compute_workload.compute_result` (SHA-256 chain with 8192 rounds).
8. Provider returns two separate signatures: original Solidity-compatible `ProviderResponse` for the challenge (which **does not sign the compute result**), and additional off-chain EIP-712 `SSEProviderWorkResult` binding the actual resultHash. Consumer recomputes the result, verifies both, and signs an off-chain `SSEConsumerWorkReceipt`. Provider verifies this receipt before acknowledging. The receipt contains a **self-reported, untrusted consumer timestamp**.
9. Selected monitor VMs perform independent service probes, signed/archived R4 observations, and any subsequently *qualified* on-chain evidence. Neither a provider response signature nor a consumer receipt alone proves a physical SLA success. Timeouts during NAT/partition are **inconclusive**, not automatic failures. The independent dashboard is network observability only.

**Critical caveat:** Current receipt/replay records are memory-only and lost on provider restart. The provider's deterministic compute function is executed in the Python service process in this slice; it is not yet a securely isolated, quota-enforced Docker workload. The only supported public transport is authenticated Tailscale Serve HTTPS; the local HTTP fallback is for **loopback tests only**. These services do not initiate an on-chain vote or payment.

## Versioned SLA catalogs currently encoded

| Service | Resource commitment | Correctness predicate | Measured parameters | Not yet independently proven |
|---|---|---|---|---|
| `http_challenge` | committed endpoint; no container allotment | deterministic expected responseHash | response latency, result correctness, signed probes | physical delivery clock, network availability, consumer honesty |
| `deterministic_compute` | immutable `sha256:` image, requested `cpuMilli`, `memoryBytes`, endpoint | SHA-256 chain result 8192 rounds | correct result, local elapsed duration, signed probes | hardware CPU/RAM allocation, secure container execution, trusted physical timing |

This is **new SLA V1 / resource V2**, not a reinterpretation of older R7 `sse-compute-resource-profile-v1`, which has a different historical witness/reservation semantic. A version mismatch must fail closed. Current proposals set a **delivery-only reservation fee of 0**; the previously accepted generic Solidity test used 5 wei reservation for a different contractual policy. No changes to already funded leases are authorized.

`sse_sla_evaluator.evaluate` summarizes verified-attribution **reported samples** (result correctness, p95 elapsed time, observed rate and timeout count). It refuses missing signatures, duplicates and malformed samples. Its provisional assessment is **not** a final settlement outcome and **never authorizes an on-chain failure vote**. One monitor's timeout cannot exclude a timely consumer delivery on another path.

## Build the two immutable request manifests (safe/offline)

First create an empty directory with ordinary owner permissions. For an HTTP service:

```bash
mkdir -p /tmp/sse-sla-demo
python tools/sse_sla_build.py --service-kind http_challenge \
  --endpoint https://provider.example.ts.net --chain-id 31337 \
  --settlement 0x1212121212121212121212121212121212121212 \
  --output-dir /tmp/sse-sla-demo
```

The example contract address is **syntactic only**, NOT evidence of a deployed SSESettlement. Use your actual deployed chain ID and contract address before using these manifests in a funded marketplace lease.

For deterministic compute, instead pass `--service-kind deterministic_compute`, a genuine immutable `--image-digest sha256:...`, `--cpu-milli 500` and `--memory-bytes 536870912`. All addresses and hashes are public; keep wallet secrets on each owning VM.

The generated output gives you exact hashes for the consumer-owned `request` transaction in `tools/sse_node_marketplace.py`. Provider bidding, winner selection and funding are the **existing tested** on-chain operations, not replaced by the direct data plane.

## Direct node processes (after real selected lease and token provisioning)

Provider VM, **default only plans** (without `--serve`):

```bash
python services/provider-agent/direct_work_service.py \
 --policy /var/lib/sse/node/sse-sla-policy.json \
 --endpoint https://provider.example.ts.net \
 --rpc-url https://approved-private-ethereum-rpc.example \
 --signer-file /run/sse/provider.key --port 8881
```

With `--serve`, it actually reads local signer, verifies chain ID, and serves **127.0.0.1:8881**. Publish to peers only using an *authenticated* Tailscale Serve HTTPS mapping after its package installation, tailnet ACLs and TLS settings have been audited. Never expose the raw loopback service to a public interface.

Consumer VM, **default dry-run** (without `--send`):

```bash
python services/consumer-agent/direct_work_client.py \
 --policy /var/lib/sse/node/sse-sla-policy.json \
 --endpoint https://provider.example.ts.net \
 --lease-id 1 --epoch-id 0 \
 --rpc-url https://approved-private-ethereum-rpc.example \
 --signer-file /run/sse/consumer.key
```

`--send` reads signer, obtains pinned chain inspection, contacts the chosen provider over HTTPS, verifies signed result, and sends an off-chain consumer receipt. It does **not** sign an Ethereum transaction, settle an epoch, or transfer funds.

**Do not run these --serve or --send examples on unverified contracts or with wallet secrets in command arguments.** The provider/consumer account names, Tailscale DNS, deployed contracts, independent probes, local wallet provisioning and packet-path access must be set up first.

## Tests

```bash
python -m unittest discover -s tests -p 'test_sse_sla_direct_delivery.py' -v
python -m unittest discover -s tests -p 'test_sse_sla_builder_evaluator.py' -v
python -m unittest discover -s tests -q
```

Tests include genuine off-chain EIP-712 signatures, wrong-selected-provider rejection, tampered compute result, wrong policy hash, replayed signed nonce and a real **127.0.0.1 HTTP** exchange, but use a **stubbed inspection snapshot** rather than an independently deployed chain. The next acceptance gate is coupling this direct delivery loop to the previously passed real-Anvil funded marketplace integration, followed by remote independent Ubuntu VMs.

## Critical remaining gates

- Actual Tailscale package installation and Serve setup automatically during Ubuntu provisioning, broker/tailnet configured one time by operator
- Durable append-only provider and consumer request/result/receipt logs and post-crash replay protection
- Real workload execution with Docker resource quotas, image digest verification, cancellation, isolation, and provenance
- Producer/consumer node-local UI buttons for authorized live request / bid / selection / execution (current node UI is preview only)
- Clock assumptions, independent physical delivery evidence, monitor qualification and conservative on-chain settlement
- End-to-end real Anvil test coupling signed direct exchange into lease state and evidence; cross-VM NAT and network-partition tests
- Observer dashboard signed-evidence drilldown, off-chain archives, and tamper-evident probe logs; no participant control
