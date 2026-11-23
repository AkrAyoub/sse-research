# R191 — Actual VM4709 recovered and locally FINALIZED on original live chain31340

**Observed date:** 2026-11-23, actual VM4709 R153 read-only evidence 13:18:40 UTC.
**Source:** operator-provided actual VM4709 Docker/logs and local R141/R153 JSON.
**Status:** REAL local EL/CL native P2P and FINALITY VERIFIED on VM4709.
**Caveat:** not a simultaneous independent VM4707-vs-VM4709 checkpoint comparison or proof of arbitrary untrusted independent Internet admission.

## Actual reported evidence

- New genuine VM4709 node ID `node-8be265272c35f3d8c3a0`.
- Recovered Besu EL container `sse31340-r137-node-8be265272c35f3d8c3a0-el` **Up 19 minutes (healthy)**.
- Recovered Lighthouse CL container `sse31340-r137-node-8be265272c35f3d8c3a0-bn` **Up 12 minutes**.
- Original two malfunctioning EL/CL containers stopped, named `-r188-preserved`; original populated Beacon DB/identity preserved.
- Actual Besu EngineNewPayloadV4 imported multiple real PoS payloads with **2 peers**, EngineForkchoiceUpdatedV4 reports `FCU(VALID)`.
- Actual Lighthouse independently logs `Synced`, 2 native peers, verified execution hashes, ongoing new actual blocks, finalized epoch 570.
- Actual read-only Beacon REST `/eth/v1/node/syncing`: `is_syncing: false`, `is_optimistic: false`, `el_offline: false`, `head_slot: 18392`, `sync_distance: 0`.
- Actual Beacon peer count `connected: 2`.
- Actual R153 `observe` state **`ACTUAL_LOCAL_CHAIN_FINALITY_VERIFIED`**. Nested R141 evidence:
  - `chainId: 31340`
  - `executionGenesisHash: 0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`
  - `beaconGenesisValidatorsRoot: 0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`
  - `executionBlockNumber: 16782`
  - `beaconHeadSlot: 18392`
  - `executionNativePeers: 2`
  - `beaconNativePeers: 2`
  - `finalizedEpoch: 570`
  - `finalizedRoot: 0x7d34c66101291c4939a42bfe21a13a3c9700bd8cecfe0422959c3a1e9865cc73`
  - `executionSyncing: false`, `beaconSyncing: false`, `executionOffline: false`, `optimistic: false`
  - report capture `2026-11-23T13:18:40.789594+00:00`.
  - report fields `independentOperatorVerified: false`, `publicInternetNativeP2pVerified: false`, `remotePhysicalResourceVerified: false`, `validatorKeyRead: false`, `transactionSubmitted: false`.
- Lighthouse logs `Downloading historical blocks` with remaining history even while `is_syncing: false`: **head sync and forward finality are established; historical backfill is ongoing** and must not be mislabeled as fully finished archival sync.
- The original VM4707 already proved genuine finalized epochs 558,560 and later e565 checkpoint export. **A simultaneous pair of R141 captures** is still needed to verify identical finalized epoch/root on both hosts; cannot assert that solely from VM4709's finalized root.

## Recovery history and scalable installer issues resolved

- R175/R177 official signed ZeroTier APT (fix HTTP403 vendor installer and malformed repo newline).
- R168 public temporary GitHub rendezvous delivered real fresh EL enode/CL ENR; client peering proof now available, but one GitHub issue remains a centralized first-join bootstrap dependency.
- R188 exact-root recovery stopped and preserved original nonworking containers; genuine pinned Besu v26.11.1 direct native executable bypassed `besu-entry.sh` requiring su/chown, without weakening `--read-only`, `--cap-drop ALL`, `no-new-privileges` or immutable original genesis/JWT.
- Original chain31340 VM4707 Beacon e565 finalized checkpoint state/block public SSZ exported (both SHA256 pinned), published as immutable GitHub release and anonymously downloaded/verified by VM4709, without exposing owner Beacon REST, Engine API or validator keys.
- R189 public checkpoint read/traverse permissions allowed hardened Lighthouse to access read-only bind mount; validated real checkpoint and synced.
- Existing old filled Lighthouse DB and original node P2P key retained, new isolated DB imported trusted recent checkpoint.
- No synthetic nodes, fake finality, simulated computational workload or new chain genesis.

## Immediate next acceptance gates

1. Run `python3 -B tools/sse_pos_r141_independent_fleet_audit.py --capture --node-id <distinct-real-id> --el http://127.0.0.1:28545 --bn http://127.0.0.1:25052` **on EACH VM** close in time. Compare the actual two raw reports using `--compare` with <=180s skew. If finalized epochs differ from normal chain progression, repeat captures; do not infer fork from asynchronous root alone.
2. Cross-host validated identical original genesis identities, exact finalized epoch and root, native EL/CL peer counts >0. Only then mark observed cross-node consensus consistency.
3. Next integrate actual marketplace: deploy original SSE contracts on chain31340 with real funding/test-ETH, real consumer/provider/monitor processes and payments, monitoring, SLAs, disputes. Identify deployment receipts, on-chain addresses, authorization and live observed reports. No claims unless evidenced.
4. Build repeated fresh-host 1-command installer/recovery with permissionless native discovery from outside existing VM infrastructure, dynamic IP adaptation, no GitHub REST quota or operator allowlisting, and no original signer cloning.
5. Document protocol choices, real PoS validator participation/rewards, gas/slot metrics, independent external host connectivity and scientific measurements with real workload/fault injection.

**Do not rerun R147/R151/R137/R188 on deployed VM4709. Do not delete old containers/databases or alter VM4707 original validator.**
