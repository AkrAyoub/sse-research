# R62 — original chain31340 read-only health *inside existing Docker network namespaces*

**2026-11-21 status: GitHub SOURCE ONLY; not yet executed on operator VM.** Last R60/R61 user gate actually passed **19/19** and observed all original owner EL+BN+VC containers running with zero restarts/OOM in later Docker inspect. The original network `sse31340-g2-internal` is IPv4-only and `internal=true`, with Besu `--p2p-enabled=false`. All current host-local probes `127.0.0.1:18545` and `127.0.0.1:15052` returned **ConnectionRefusedError**. Docker `.NetworkSettings.Ports` maps `8545/tcp` and `5052/tcp` to **null** (no effective published host port), while EL/BN are still running. User's output alone does not show whether the Ethereum RPC and Beacon REST services respond **inside the container network namespaces**, or whether the clients currently finalized any blocks.

**Likely technical reason for host refusal:** Docker user-defined internal bridges can retain requested `--publish` in `.HostConfig.PortBindings` but show no **effective** `.NetworkSettings.Ports` publication. Compare the two rather than assume. Do not modify Docker or the original signer to make host APIs temporarily work; first read the actual services from inside existing namespaces.

## What the reviewed local R62 helper does

`tools/sse_pos_r62_original_container_namespace_health.py` is standalone standard-library Python and imports the existing `tools/sse_pos_r60_owner_native_p2p_readonly_audit.py`. It runs **only on original VM4706** at exact audited Git revision. Existing R60 original-genesis/JWT *metadata only* safety gate verifies original state unchanged. R62:
- Read-only inspects *requested* HostConfig.PortBindings vs *effective* NetworkSettings.Ports for only protocol ports 8545, 5052, 8551, 30303, 9000 and 9001 (no credentials, Docker environment, full CLI, full mounts or private logs).
- Verifies original Besu EL and Lighthouse BN actually running in original isolated `sse31340-g2-internal` and original VC still running.
- Uses host `/usr/bin/python3` through `sudo -n nsenter --target <existing-container-PID> --net`; **enters ONLY the already-running process's Linux network namespace**, *not* mount/user namespaces, and makes bounded HTTP requests to `127.0.0.1:8545` from EL namespace and `127.0.0.1:5052` from Beacon namespace. No new Docker container, service, port, overlay, routing, firewall, ZeroTier, keystore, wallet or JWT modification.
- Parses and outputs only whitelisted nonsecret execution `eth_chainId`, `eth_blockNumber`, `net_peerCount`; public Beacon genesis_time, head slot/root, finalized epoch/root. Errors are classified by HTTP status, connection refusal/timeout or invalid JSON without printing unfiltered bodies. Negative result is a genuine *client-namespace* health observation; it is NOT evidence of remote native peers/finality.
- Does not show original container PIDs or untrusted stdout. Refuses if nsenter utility missing, local sudo unavailable, original containers stopped, original genesis changed or Git source differs. User can exit without any modifications.
- All local write actions and new native peer operations remain **forbidden**. The original owner VM4706 has NO ZeroTier CLI; public-native common network setup still requires separate security/migration review. **No private provider LAN may be used as native Ethereum bootstrap even for first nodes.**

## VM4706-only command, after source gate

No SSH/SCP to VM4707 and no networking installation. Run in a subshell. The suite contains **12 source/mock tests, not yet executed**:

~~~bash
(
  set -e
  cd "$HOME/sse-research"
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="ccbe47b2339a3c9b61554b40fb9d2940b1a4251d"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r62_original_container_namespace_health.py' -v
  echo "R62_SOURCE_TESTS_PASSED=true"
  sudo -v
  python3 -B tools/sse_pos_r62_original_container_namespace_health.py --audit --expected-commit "$SHA"
)
~~~

**Acceptance interpretation:** if internal EL and Beacon APIs return valid original chain/finality values while host API binds are absent, this is a port-publication/visibility issue and does NOT require resetting the original chain. If the internal APIs also fail, do not assume prior finality persists; investigate targeted nonsecret client health (socket bind, process errors) *read-only* before maintenance. In either case original P2P remains disabled: no 2nd native peer, no public network acceptance until independently verified Besu+Lighthouse signed peer handshakes from outside provider infrastructure.

**Related evidence:** `docs/experiments/VM4706_2026-11-19.md` Entry 094 and next R62 entry. Docker inspect published ports https://docs.docker.com/reference/cli/docker/inspect/ ; Docker internal bridge port publication issue https://github.com/moby/moby/discussions/53256 ; Linux namespace inspection https://man7.org/linux/man-pages/man1/nsenter.1.html.
