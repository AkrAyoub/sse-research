# R179 — actual VM4707 finalized chain and exact VM4709 first-start blockers

## New real owner observations

The original VM4707's existing non-signing Lighthouse Beacon REST (127.0.0.1:25052) returned justified epoch 560 and **finalized epoch 558**, finalized block root
`0xde30135baa11178dc5e539c690d1ba1092337890e2ff81a55b718f389e47c3d1`. Top-level Beacon JSON `finalized:false` refers to the queried *head state*, not absence of a finalized checkpoint; finalized checkpoint is explicit under `data.finalized`. Original VM4707 EL and CL containers remain Up. The owner chain therefore has a usable source of **recent finalized identity**. Do not claim checkpoint-sync source reachable remotely: its REST API is only localhost bound by design.

The real VM4709 R178 no-write diagnostic, 2 targeted tests passed, confirms:
- Besu EL image actual ID `sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d`; native image default entrypoint `besu-entry.sh`, 23 restarts. Read-only original genesis mount, capDrop ALL, no-new-privileges preserved. Its chmod/chown/su failures are wrapper compatibility, not genesis corruption. On NEW installs R179 now opts into `/opt/besu/bin/besu` direct binary with all original security options kept. Do not auto-apply this to already-created VM4709 containers without verifying binary availability, command flags, and preserving state.
- Lighthouse CL image actual ID `sha256:53f9063d98c3d3a2d290207873f019ea2298cfc02f8cd58d87c33b04aab856d1`; actual entrypoint `lighthouse`, 22 restarts. It has the original genesis sync flag `--allow-insecure-genesis-sync`, NO `--checkpoint-sync-url` and NO `--ignore-ws-check`. Original genesis is far outside weak subjectivity. A trusted finalized state from existing VM4707 is required for current-chain checkpoint sync. Do NOT automatically disable weak subjectivity or purge the new client's partial Beacon/EL data.
- No native cross-VM EL/CL peers/finality can be claimed.

## R179 changes

- Source R137 Docker command for **new** genuine non-signing Besu now uses explicit `--entrypoint /opt/besu/bin/besu`, bypassing image permissions wrapper while preserving `--read-only`, `--cap-drop ALL`, `no-new-privileges`, original genesis readonly, nonpublished Engine API. Lighthouse remains unchanged.
- Added regression tests checking native Besu direct executable, expected security constraints, no privileged fallback, unchanged Lighthouse config.
- `tools/sse_pos_r179_owner_finalized_checkpoint_probe.py` obtains only THREE localhost Beacon JSON endpoints: genesis, finalized checkpoint, finalized block header. It validates original beacon genesis validators root and equality of checkpoint and header roots and checks finalized slot, printing only nonsecret checkpoint metadata. **This is an observation, not a remote checkpoint-sync service or proof that remote snapshot bytes are accessible.**
- Existing VM4709 containers remain unchanged. Before actual migration, confirm that the pinned Besu binary is runnable in a disposable, hardened image invocation and that existing VM4707 Beacon API can supply SSZ finalized checkpoint state and block bytes as required by Lighthouse checkpoint sync, without exposing owner privileged APIs or keys.
- For any existing-container repair, save exact Docker inspect configuration, preserve bind-mounted original data roots and engine JWT and port bindings, refuse mismatched pinned image, no auto-purge and no naive rerun of R147/R151/R137. Require owner authorization for any actual container replacements. Capture final real sync and peer reports.

## Command sequence to run next

On VM4707: run pinned `sse_pos_r179_owner_finalized_checkpoint_probe.py` (read-only), then perform HTTP GET with Accept: application/octet-stream for `/eth/v2/debug/beacon/states/finalized` and `/eth/v2/beacon/blocks/finalized` *headers and first 32 bytes only* to determine actual snapshot support. Do not publish complete state, keys or run a persistent public API.

On VM4709: run exact image via disposable `docker run --rm --pull never --read-only --cap-drop ALL --security-opt no-new-privileges --entrypoint /opt/besu/bin/besu <PINNED_IMAGE> --version` to verify binary existence, not native network participation. Existing containers untouched.

Then implement the smallest verified, reversible existing-client repair through GitHub with strict safety preflight and targeted tests. This is still an experimental PoS research network, not yet proven independent permissionless infrastructure.
