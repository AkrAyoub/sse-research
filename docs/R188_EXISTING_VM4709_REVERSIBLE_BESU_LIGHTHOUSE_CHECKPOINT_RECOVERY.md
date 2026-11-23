# R188 — Actual original VM4707 checkpoint e565 delivered; guarded VM4709 client recovery

The real original owner VM4707 R186 exporter successfully finalized epoch565, slot18080,
root `0x86fdc98df47d641a27fbc95eb3229dfc0e24553d1dc57bfbe2599e161b60a259`.
Public e565 GitHub Release has three assets (state, block, manifest).
VM4709 R187 3 targeted tests passed; actual anonymous HTTPS download completed and
SHA256 matched BOTH bytes exactly:
state 2859760B hash `8c03cdec390bb9442d7ac8d98a01a1d6dc03861602bf085d95553554ea5a1d41`;
block 1417B hash `9e2859ca4e57bf1228d010bd7958483ee111b4ec10d39c5d5aa82f691c702373`.
Verified local path:
`/home/ayoubakrvm4709/sse-chain31340-checkpoint-e565`.
Both original VM4709 containers still Restarting (1). No native P2P peers or finality yet.

## R188 exact-owner recovery

The new tool `tools/sse_pos_r188_vm4709_guarded_existing_client_recovery.py`
is for the ONE exact original observer ID
`node-8be265272c35f3d8c3a0` on VM4709 only.
`--plan` performs read-only validation of real original Docker container
names, pinned image IDs, exact original bind-mounted root, JWT/genesis
read-only flags, P2P IPv6-only ports and loopback-only local RPC, Docker
read-only rootfs/cap-drop ALL/no-new-privileges, exact checkpoint
SHA256, populated original Beacon database and original P2P private
identity (metadata only, never prints its contents).

`--execute --authorize RECOVER-VM4709-PRESERVING-OLD-CLIENTS`
is an explicit operator-mutating action for VM4709 only; it:
1. Locally stages a NEW empty Beacon database location
   `/root/.local/share/sse-r137-node-8be265272c35f3d8c3a0/beacon-r188-checkpoint-e565`.
   Copies ONLY the 64B original local P2P network key within private host
   root-owned directories so the observer retains its P2P identity.
   Does not remove, overwrite or export original database or JWT.
2. Stops and RENAMES only the two exact old VM4709 containers to
   `-r188-preserved` names for potential rollback. No `docker rm`
   or `--force`.
3. Starts a new pinned Besu container under the same exact name and
   port bindings using `--entrypoint /opt/besu/bin/besu` (empirically
   version-tested) with original read-only genesis, JWT, cap-drop ALL,
   no-new-privileges and localhost-only JSON-RPC.
4. Starts Lighthouse against separate fresh root with same original
   verified genesis and existing JWT, read-only SSZ files from the
   0700 receiver location, and
   `--checkpoint-state=/checkpoint/checkpoint-state.ssz`,
   `--checkpoint-block=/checkpoint/checkpoint-block.ssz`.
   Original `--allow-insecure-genesis-sync` is removed;
   NEVER adds `--ignore-ws-check` or purges any DB.
5. Reports only container submission; does not mark native EL/CL
   syncing or finality as verified. Read-only R141/R153 then checks
   chain31340, native peers and finalized checkpoint.

The mutation is intentional and irreversible in the sense that old
containers are STOPPED (but renamed and retained) and live P2P
connectivity may temporarily stop. It must NOT be applied to VM4707
or repeated after a partial failure. If any stage fails,
STOP and inspect exact named resources; no blind reruns and no
automatic removal of operator state.

## Remaining technical validation gates

- First run R188 regression tests and `sudo ... --plan` on actual
  VM4709, confirm exact Docker image/network/port/security settings.
- Run R188 explicit execute only after plan succeeds.
- Check real Docker logs for direct Besu startup and actual Lighthouse
  local checkpoint root validation; it is possible the pinned
  Lighthouse v8.3.3 requires extra flags or a corrected SSZ export.
- Observe actual P2P peers, CL/EL head, sync and finalized block root,
  then compare contemporaneous VM4707+VM4709 observations.
- None of marketplace service, external independent ISP, permissionless
  Internet native bootstrap, validation/rewards and real SLA resources
  are proven by client container submission.

Original chain31340 genesis and validator state remain untouched.
