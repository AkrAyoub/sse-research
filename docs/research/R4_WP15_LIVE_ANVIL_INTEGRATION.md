# WP-15 — Real Anvil V2 evidence integration (deployed contract state, not synthetic RPC)

## Why WP-15 materially differs from WP-12 and WP-14

WP-12 ran V2 contracts together inside Foundry's in-memory test EVM. WP-13/WP-14 also checked Python chain authorization with **controlled fake JSON-RPC objects**, while exercising real local EIP-712 HTTP signatures and SQLite. Those paths did not establish compatibility with real deployed contract bytecode, actual `eth_getCode`, real `eth_call` ABI, or Anvil's EIP-1898 historical block state.

WP-15 adds a **separate hosted Actions job** which starts a fresh Anvil JSON-RPC node, creates deployed contracts with 38 successful real JSON-RPC transactions, and performs an actual signed HTTP capture and historical archive verification using the chain state from Anvil.

## Exact workflow

```text
GitHub Actions Ubuntu job
  ├─ install Python requirements + Foundry deps, forge build
  ├─ start *fresh* Anvil chain ID 31337, 12 deterministic unlocked test accounts
  └─ python scripts/wp15_anvil_v2_e2e.py
       │
       ├─ CREATE / DEPLOY on Anvil
       │    WP15LabCoordinator      (INSECURE MOCK; not Chainlink)
       │    SSEVRFV25Adapter        (configured coordinator callback)
       │    ScalableMonitorCommitteeV2 (bonded pool)
       │    SSELeaseControllerV2    (escrow)
       │
       ├─ bind pool/controller, consumer funds 3 × epochFee
       ├─ provider accepts
       ├─ 8 independently keyed monitor accounts register (1 ETH) + join (0.1 ETH)
       ├─ advance Anvil chain past enrollment deadline
       ├─ freeze roster → request mock word → coordinator callback
       ├─ supply seed → process batched selection → choose 4 seats
       ├─ 4 selected monitors send ON-CHAIN confirmations
       ├─ activate funded lease, admit an unresolved epoch
       │
       ├─ read actual deployed runtime bytecode and record local code-hash manifest
       ├─ require EIP-1898 pinned eth_call + eth_getCode in WP-13 V2 reader
       ├─ start localhost provider (ProviderResponse EIP-712, real key for on-chain provider)
       ├─ chosen on-chain monitor captures HTTP and signs independent RAW evidence
       ├─ WP-14 SQLite ONE-TRANSACTION store of exact HTTP bytes, envelope and block ref
       ├─ reload: re-verify signatures + exact original historical Anvil block
       │
       ├─ negative: non-selected account #10 cannot capture as a selected monitor
       ├─ advance Anvil to service deadline, release committee and end admissions
       ├─ negative: fresh/current authorization now FAILS
       ├─ positive: historical archived observation STILL VERIFIES at original block
       ├─ negative: tamper stored provider bytes → historical verification FAILS
       ├─ positive: restore exact bytes → verification SUCCEEDS
       └─ assert zero provider credited merely from observation
             |
             v
       upload sanitized JSON trace and local Anvil log (no private keys)
```

The full sequence exercises real contract deployment/transaction receipts and **actual Anvil EIP-1898 block-hash-pinned reads**, not mocked state dictionaries. The URI and provider are **numeric IPv4 loopback only**.

## Integration inputs and limitations

- **LAB KEY SAFETY:** the known Anvil development mnemonic is public. The runner refuses non-31337 chain IDs, nonzero chain height, or unexpected unlocked accounts and uses keys only on the ephemeral local node. Never use those keys on a funded network.
- **Randomness:** the `WP15LabCoordinator` under `foundry/test/` is deliberately insecure. The adapter receives a callback that has *not* undergone real Chainlink proof verification. Successful callback plumbing ≠ unbiased committee sampling.
- **Finality:** `block_tag='latest', allow_unfinalized=True` is used intentionally because this is a fresh Anvil dev chain. This does not establish proof of canonical Ethereum consensus or the safety of short commercial deadlines.
- **Code hash trust:** runtime bytecode digests are recorded from the test's own freshly deployed contracts. This verifies internal consistency, but a malicious RPC could lie to both deployment and verification paths. Public deployments need independently authenticated code hashes/consensus state.
- **HTTP provider:** uses the existing *legacy off-chain* V1 ProviderResponse EIP-712 signing namespace with the V2 controller address as verifying contract. It is **not** an on-chain V2 allocation signature and does not qualify consumer physical receipt.
- **Physical truth:** on-chain seat confirmation + correct provider and monitor signatures still do not prove that the *consumer* received service within an SLA deadline. No automatic payout is authorized by this test.
- **Archives:** historical verification succeeds with Anvil's available historic EIP-1898 state. A pruned or inconsistent remote RPC is expected to fail closed; a local SQLite database remains deletable by its host.
- **Concurrency:** only this local node/provider/monitor are integrated in one CI job. Independent WAN host experiments remain R5/R9 work.

## Actual acceptance run

- First successful live-node run: https://github.com/AkrAyoub/sse-research/actions/runs/43213469626
  - **38 mined transactions** including four deployments, one funded lease, eight enrolled monitors, four selected confirmations and one admitted epoch.
  - **8 registered and joined, 4 selected and confirmed**.
  - The real JSON-RPC block hash, deployed runtime and V2 ABI were accepted by the strict WP-13 reader.
  - The real signed HTTP response was archived with the block reference and reverified after deadline/lease state changes.
  - The provider's withdrawable allocation remained **zero**.
  - The workflow uploaded a sanitized transaction trace: https://github.com/AkrAyoub/sse-research/actions/runs/43213469626/artifacts/13941778427
- Hardened run: https://github.com/AkrAyoub/sse-research/actions/runs/43213885798
  - Confirmed that **unselected account #10 cannot capture** as an authorized monitor using actual Anvil state.
  - Confirmed an actual Anvil historical verification **rejects tampered archived provider bytes**, and accepts the restored original signed bytes.
  - Real-Anvil job passed. Existing CI continues to cover 410 Python tests per OS and 124 Foundry tests.

These are meaningful operational compatibility checks. They are NOT 410 independently executed real-Ethereum tests or real VRF proof checks.

## Reproduction on a clean Linux/macOS/Git Bash environment

Require `forge`, `anvil`, `cast`, Python 3.12, installed `requirements.txt`, and contract dependencies. From repository root:

```bash
bash scripts/install-contract-deps.sh
forge build
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --accounts 12 \
  --mnemonic 'test test test test test test test test test test test junk'
```

In another terminal:

```bash
python scripts/wp15_anvil_v2_e2e.py --rpc-url http://127.0.0.1:8545 \
  --output artifacts/wp15-anvil-v2-trace.json
```

**Never run this against an existing Anvil chain**: the script requires a fresh empty chain, and the test mnemonic is public. If the CLI reports a missing Foundry artifact, rerun `forge build`. If the RPC rejects EIP-1898 pinned code/state queries, **do not downgrade to latest**; the adapter must remain fail-closed and its RPC compatibility needs investigation.

The trace contains transaction receipts, deployed addresses, scope and evidence IDs, but no private keys. It is a research artifact and may not be safe to publish if a future runner ever includes secret-sensitive inputs; review it before publication.

## Progress classification

This moves the research from **synthetic RPC-only authorization to real locally deployed Anvil V2/HTTP/SQLite integration**. The primary earned progress is R4 (chain-aware evidence SDK); a smaller part concerns R8 (traceable observatory). R9 **independent distributed experiments** does *not* advance from same-host Anvil because no independent host or network partition is exercised.

### Next substantive acceptance requirements

1. Consolidate the still-open chain of draft PRs: review #9 → #10/#11 → #12 → #13 → #14 → #15, retarget one at a time, reconcile tracker and rerun CI. Independent V1 #8 remains separate.
2. Move provider, consumer and selected monitors to **separate processes and distinct machines** with authenticated remote TLS and bounded request/response bytes. Inject delays/partitions and observe physical N/F/S ambiguity. Keep the financial V2 consent boundary.
3. Replace the mock lab callback with a **real VRF v2.5 supported testnet coordinator**, funded subscription and independently authenticated deployment.
4. Publish an independently anchored append-only evidence digest or replicate archives across distrustful hosts; validate that one SQLite host cannot rewrite or hide evidence without detection.
5. Define a consumer receipt or service-specific qualified-fact policy that actually excludes impossible N/F/S histories, and prove what money can safely be transferred even under asynchronous failure.
6. Run controlled gas/latency/availability/collusion experiments, then write the publication-quality methodology and reproducibility package.
