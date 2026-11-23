# R190 — VM4709 actual recovered Besu healthy; Lighthouse checkpoint import pending

Actual operator VM4709 output from Nov 23 2026 after fixing public e565
checkpoint file permissions (sha256sum -c both assets OK):
- Explicitly set 0755 only public checkpoint directory and 0644 only
  public state/block/manifest, then `docker restart` ONLY new BN.
- Recovered EL container `sse31340-r137-node-8be265272c35f3d8c3a0-el`
  reported `Up 6 minutes (healthy)`. Original EL+BN containers
  `-r188-preserved` are stopped and retained (not removed).
- Recovered BN `sse31340-r137-node-8be265272c35f3d8c3a0-bn`
  reported `Up Less than a second` when checked, not yet proven healthy.
- BN log tail still includes earlier repeated
  `Unable to open /checkpoint/checkpoint-state.ssz: Permission denied`.
  Latest emitted lines timestamp Nov23 13:05:39 show a new Lighthouse
  startup through Deposit contract line, but NO subsequent checkpoint
  acceptance, native peer or finality output. Do NOT claim the
  permission error was fully resolved without observing subsequent
  startup/health. New errors may appear.
- Recovered Besu v26.11.1 actual log:
  - Native PoS initial sync enabled, exact one bootnode,
    combined discovery v4/v5, Java Engine API listening in Docker,
    RLPx listening v4 port30303 and native IPv6 port30404.
  - P2P node enode and IPv6 ENR emitted, genuine dynamic VM4709 address.
  - `Runner | Ethereum main loop is up`; `Node out of sync,
    disabling transaction handling`.
  - After 120sec, repeated `Execution engine not called in 120 seconds,
    consensus client may not be connected`, expected if CL has
    not yet successfully started. No verified live peer handshake.
- Original owner VM4707 finalized real chain; e565 SSZ block+state
  published, downloaded on VM4709, SHA256 verified. Original
  genesis, JWT, locally copied BN network identity and old
  populated Beacon DB preserved throughout.

Next read-only evidence on VM4709:
1. `docker ps -a` statuses at observation time, last ~60 lines new BN and EL logs. Docker logs include prior errors from same restarted
   container; inspect time-ordered most recent occurrence, don't
   misinterpret old EACCES lines.
2. `python3` import `sse_pos_r153_local_node_evidence.observe`
   from preserved pinned source `/opt/sse/releases/df3df85190789cc14fe6920a248f6a7545a44197` with the exact
   node ID. Read-only actual localhost Besu JSON-RPC
   127.0.0.1:28545 and Beacon REST 127.0.0.1:25052.
   If actual finality not yet ready, R153 returns
   `WAITING_FOR_ACTUAL_EL_CL_FINALITY` not fake success.
3. Read-only bounded Beacon peer count, sync status and finality HTTP responses only after service is available. No
   `--ignore-ws-check`, no another create-once installer, no
   deletion/recreation of containers or checkpoint.
4. If BN continues to fail, diagnose precise latest error; recover
   only through narrowly verified, owner-authorized changes.
5. On positive local actual R153 finality and native EL/CL peers,
   capture contemporaneous R141 on VM4707 and VM4709 and compare
   finalized epochs+roots. Then integrate actual SSE marketplace
   workloads and validate physical SLAs.

The live independent-node deployment is not yet demonstrated complete.
