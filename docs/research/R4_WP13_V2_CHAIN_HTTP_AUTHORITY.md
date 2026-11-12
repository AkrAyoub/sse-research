# WP-13 — Binding V2 signed HTTP observations to the funded lease and chosen committee

## The gap after WP-12

WP-12 ran the funded V2 contract, the scalable pool, the coordinator callback interface and bilateral settlement in one local Foundry EVM scenario. Separately, WP-08B could retrieve a signed HTTP response and store a monitor's EIP-712 observation. Those two paths still did not agree on **who was allowed to report for an actual V2 lease**.

WP-08C is a V1-only chain reader: its settlement has a fixed array of four monitors, V1's EIP-712 domain, and different lease/epoch layouts. V2 changes all of those. Feeding V2 bytes to the V1 decoder would produce invalid or misleading authorization.

The V2 adapter therefore reads the **real V2 ABI**, derives the selected seat identities from the pool, and supplies the exact authorized signer set to WP-08A/WP-08B. This closes the caller-invented-committee gap **under a trusted RPC assumption**, without changing payout rights.

## Exact steps and why

```text
Required independent inputs
  expected chain ID, V2 controller/pool addresses, runtime code hashes
  lease/epoch IDs, SLA hash, profile hash, request hash, service root
                         |
                   select RPC block
                         |
    EIP-1898 {blockHash: ..., requireCanonical:true} on ALL reads
                         |
    check bytecode hashes and V2 EIP712 controller domain
                         |
    controller.pool == pool AND pool.controller == controller
                         |
    V2 getLease(lease) -> Live, consumer/provider, escrow conservation,
                          endpoint/profile/SLA commitments, assignmentId
                         |
    pool assignmentStatus = Active, K/Q/R valid, lease parties match
                         |
    selectedCount=K, confirmedCount=K, seatAt[0..K-1]
                         |
    each selected ticket: joined, paid, everSelected, confirmed, !noShow
                         |
    getEpoch(lease,epoch) -> admitted, unallocated, matching request,
                             matching fee, pending budget, open deadline
                         |
                 recheck original block hash
                         |
    V2AuthoritySnapshot + exact VerificationContext for K monitors
                         |
    WP08A verify_observation -> authenticated RAW statement
                         |
    optional WP08B capture_response -> legacy provider-response verifier,
                                        monitor EIP712 signing and SQLite
                         |
           NO QualifiedFact, NO automatic V2 payout
```

Why every check matters:

- **Code fingerprints:** matching addresses alone is insufficient. A malicious RPC might show a compatible but fake contract. A code digest from the **same** RPC is not independent authentication; expected fingerprints must come from a separately trusted deployment artifact. No Merkle state-proof verification or independent Ethereum finality is implemented.
- **One block hash:** without pinning, lease state, selected seats, ticket confirmations and epoch state could come from different blocks. EIP-1898 is required and unsupported RPCs fail closed—no automatic fallback to `latest` or block number.
- **Bidirectional controller/pool binding:** prevents accidentally reading a genuine but irrelevant pool that happens to contain an address with the same monitor key.
- **Individual ticket checks:** a count of K confirmed seats is not enough when stale or substituted addresses could be read. Each seat must be a unique non-party address and have a paid, confirmed, non-penalized participation ticket.
- **Exact HTTP root:** the V2 funded lease commits `keccak256(UTF8(serviceRoot))`. The existing transport's `signed_probe.validate_endpoint(root)` **returns a request URL ending in `/v1/challenge`**; the adapter deliberately hashes the canonical service ROOT, not that appended request path. Research mode accepts only `http://127.0.0.1:PORT` with no path, credentials, host aliases, redirects or proxies.
- **Financial accounting:** the lease must conserve `escrow = uncommitted + pending + providerCredited + consumerCredited + unusedRefunded`. An admitted raw observation does not permit money movement; the V2 controller still requires bilateral allocation signatures.
- **Admitted/unallocated epoch:** a selected monitor from another epoch or a report for already-allocated money is rejected. For *current capture*, the chosen block's timestamp must not exceed the epoch deadline. That does NOT prove the HTTP exchange occurred by that deadline.

## EIP-712 namespace distinction, not a silent compatibility claim

V2 controller bilateral money allocation uses `EIP712("SSELeaseControllerV2","2")`, and WP-13 verifies this domain on chain.

The **existing** WP-08B provider HTTP response uses the **legacy off-chain** V1 `ProviderResponse` signature namespace (`SSESettlement` version 1), even when the domain's verifying-contract address is the V2 controller address. The adapter's optional bridge deliberately reuses that exact off-chain wire format to avoid changing old signed-provider demo tests. It is **not** the on-chain V2 allocation message, and V2 does not implement a V1 provider-response entrypoint. We still need a separately versioned, V2-native provider-response schema before an interoperable public network.

The monitor's off-chain WP-08A `SSEEvidenceObservation` namespace is also separate. These signatures identify reported bytes and signers, not an objective physical event.

## Limits of the block reference

The selected block hash and contract code hashes are included in a portable snapshot with a Keccak commitment. This helps reproduce exactly what the adapter assumed. But:

1. The RPC can lie about the block, and the `finalized` tag is its own assertion. An independent consensus proof is not produced.
2. `read_v2_authority` reads chain state **before** the HTTP request. A valid snapshot at time t does not establish committee status when the HTTP response arrives later. There is a time-of-check/time-of-use window.
3. The snapshot and its commitment are returned to the caller but **not atomically stored with WP-08B's SQLite evidence record**. Persisting them together remains a separate WP-14 gate.
4. The current adapter authorizes **live, pending, unallocated epochs** only. To inspect older evidence after closure, retain an independently trustworthy historical block hash; the latest chain state may no longer authorize a newly submitted observation.
5. Waiting for `finalized` on a public chain may conflict with short HTTP epoch windows. `safe`/`latest` require explicit opt-in and weaker reorg assumptions. Measure finality latency before choosing production SLA deadlines.
6. An active monitor's signed observation might be false or incomplete about the consumer's actual experience. No physical-consumer-receipt certificate is implemented here.

## Verification and what it does not mean

`tests/test_sse_v2_chain_authority_v1.py` adds **35** scenarios using an explicit **synthetic RPC**. They cover:

- correct 19-field V2 lease, eight-field epoch and five-field ticket decoding;
- strict block-hash pinning, code hashes, controller domain, both bindings and visible reorgs;
- funded escrow conservation and exposure budget;
- numeric localhost endpoint commitment and malformed endpoint rejection;
- variable K/Q/R selected monitor membership, all on-chain ticket confirmations, duplicate and interested seats;
- wrong, resolved, expired or previously unadmitted epochs;
- unsupported RPC pinning, explicit weaker block-tag opt-in, no transaction submission;
- bridge argument binding to the existing capture API;
- selected EIP-712 monitor signature acceptance and outsider rejection.

Initial hosted PR #13 run: https://github.com/AkrAyoub/sse-research/actions/runs/43192903482
- Python Ubuntu **372/372** (337 inherited + 35 new), no failures/skips;
- Python Windows **372/372**, no failures/skips;
- Foundry **124/124** (unchanged cumulative V2 suite), no failures/skips.

A URL mismatch was found during review before CI: `validate_endpoint` returns the `/v1/challenge` URL, not the canonical service root. The implementation was corrected to check the root separately and never compare the request URL to the on-chain root commitment.

The mock-RPC tests prove the **interpretation and fail-closed policy for supplied RPC answers**, not the truth of those answers. Real Anvil- and then independent-network integration are still required.

## Next engineering gates

- **WP-14:** atomically archive the exact signed HTTP response, signed monitor record and the pinned V2 block reference in the same transaction; recheck all commitments on load. Durable per-lease/epoch replay protection must survive restarts and conflicts.
- **V2 provider wire:** define a versioned V2-native provider-response EIP-712 schema with explicit challenge/response and message-domain separation. Do not silently reuse the V1 on-chain domain.
- **R3 live VRF:** deploy #11 against a verified supported Chainlink v2.5 coordinator, authorized and funded subscription; obtain a *real proof-verified callback*, not a local substitute.
- **R5/R9:** independent provider, monitor and consumer processes/machines, WAN faults, RPC disagreement, clock skew, finality-latency and storage-censorship experiments.
- **R1/P1/P2/R2:** physical consumer-delivery qualification, formally bounded settlement under unresolved N/F/S histories and a fair dispute-liveness rule. A provider or monitor signature never alone authorizes escrow release.

## Merge dependencies and reproduction

WP-13 branch is based on WP-12, which includes WP-09 pool, WP-10 controller and WP-11 adapter. The separate WP-08C V1 chain-authority PR #8 is still open. Keep all unmerged branches explicit; do not call `main` current until PRs are actually approved and merged.

Review/merge #9, then #10 and #11, then #12 after adapter deduplication and tracker reconciliation. Retarget #13 to `main` afterward, confirm only WP-13 files remain in the diff, and rerun all CI. PR #8 can be reviewed separately, but its phase tracker modifications also need reconciliation.

```bash
git fetch origin
git switch --track origin/research/r4-wp13-v2-chain-bound-http-evidence
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -p "test_sse_v2_chain_authority_v1.py" -v
./.venv-r0/Scripts/python.exe -m unittest discover -s tests -q
forge test -q
./.venv-r0/Scripts/python.exe tools/sse_v2_chain_authority_cli.py --help
```

Expected on this cumulative branch: 35 WP-13 Python tests; 372 Python total, 124 Foundry. For a live local Anvil inspection, a V2 controller+pool pair must actually be deployed with a **Live** lease and admitted unresolved epoch, and trusted runtime hashes must be supplied explicitly. Some RPCs do not support EIP-1898 for `eth_getCode`: those must fail closed, not be treated as a test failure to hide with a fallback.
