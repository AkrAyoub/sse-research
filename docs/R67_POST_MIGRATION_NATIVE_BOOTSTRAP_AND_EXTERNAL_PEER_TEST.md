# R67 — actual VM4706 post-migration Besu enodeV6 and Lighthouse ENR (READ ONLY)

**2026-11-21:** Original owner VM4706 successfully ran **real** R65 `--apply --accept-single-vm-recovery-risk` at SHA `7b4d7c9afe5fb389abfa9fb333e645c6f15c6e7c`. 41/41 tests passed, native Besu + Beacon new process EL+BN APIs verified on SAME original testnet chain31340, original validator process restarted, original stopped EL/BN containers preserved. Original EL/BNode Docker host TCP/UDP ports verified ONLY on real owner overlay IPv6 `fca0:2328:776e:4750:395b::1`; original host Engine8551 private. Exact original single signer remains on trusted isolated bridge. Owner intentionally accepted absent external backup risk: local sensitive R66 unencrypted TAR **45 files, 229,023,554 bytes SHA256-verified against stopped originals**, never distribute/archive into public GitHub or VM4707. **Original post-restart finality progression has NOT YET been measured.** Native remote EL devp2p and Lighthouse discv5/libp2p peers have NOT YET been observed.

**New `tools/sse_pos_r67_post_migration_native_bootstrap_audit.py`** is a source-only, strictly READ-ONLY audit (10 unit tests, NOT yet run on VM). It queries ONLY real owner LOCALHOST Besu JSON-RPC `http://127.0.0.1:18545/` methods `eth_chainId`, `eth_blockNumber`, `net_peerCount`, `net_listening`, `net_enode`. The `net_enode` public source node ID is used to form a **source-derived** IPv6 enode on the actual validated owner ZeroTier 6plane `fca0:2328:776e:4750:395b::1:30404` (IPv6 brackets required). Besu official documentation says `net_enode` returns the node's identity and dual-stack Besu advertises separate enodeV6. **This script does not cryptographically verify a remote advert or reachability**; actual live original key identity is taken from the local running owner Besu RPC, not guessed or fabricated, and source verified P2P host flags/ports must match.

For original Beacon, reads ONLY `http://127.0.0.1:15052/eth/v1/node/identity` for genuine locally sourced Lighthouse ENR, decodes public RLP fields and verifies **`ip6` exactly owner overlay IPv6, `tcp6=9000`, `udp6=9000`**, the expected ENR identity scheme and public secp256k1 field. Rejects provider-private IPv4 in the ENR. No signing key/JWT/validator data is read or printed; no private host Docker mount paths printed. **ENR cryptographic signature itself not independently checked by audit**, although supplied directly by Lighthouse's own live node identity API. Any mismatch is a fail-closed diagnostic, never construct a fake ENR. Reads real Beacon genesis, header head slot, finalized epoch/root, sync status and connected peer count. Current baseline **epoch 120 is the pre-migration snapshot**; reports whether finalized epoch is now greater than 120. Checks actual EL/BN/VC remain running; old saved containers STOPPED; new EL+BN exactly both reviewed trusted bridge and public bridge and expected host port binds; source 6plane membership `ff2328775f000000` ACTUALLY OK PUBLIC on owner interface. Does NOT start/stop Docker, restart signer, change network, upload a file or enable an RPC admin API.

## VM4706 exact R67 command (no migration/restart)

```bash
(
  set -e
  cd "$HOME/sse-research"
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="504beea58ec60e1ab3b1354fb2f37012cbc310e3"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r67_post_migration_native_bootstrap_audit.py' -v
  echo "R67_SOURCE_TESTS_PASSED=true"
  sudo -v
  python3 -B tools/sse_pos_r67_post_migration_native_bootstrap_audit.py --audit
)
```

**Expected:** 10 source tests and then real post-migration JSON output containing `sourceDerivedBesuEnodeV6` and `sourceLighthouseBeaconEnrFromLiveNodeIdentity` ONLY if original client public IDs and overlay P2P endpoint fields validate. These are public network bootstrap identities, not signing secrets. Never paste or upload local R66 private TAR or hidden node keys. If rejected, preserve live clients and return sanitized output; do NOT rerun R65 or launch VM4707 blindly.

## Next independent native two-layer peer test

1. VM4707 (different VM) already proved actual PUBLIC controllerless ZeroTier IPv6 `fca0:2328:77b8:6578:a55::1`, same network. Get genuine R67 source-derived Besu IPv6 enode and genuine source Beacon ENR, NEVER invent static node key or subnet.
2. VM4707 obtains verified original chain31340 **PUBLIC genesis package** from already-reviewed R59 process, NOT owner VC/JWT. Review and use corrected `tools/sse_pos_r59_native_ipv6_observer.py` with `--execution-seed-enode-v6 '<actual R67 enode>' --beacon-seed-enr '<actual R67 ENR>'`. `--plan` first, then separately operator-approved `--apply` only on VM4707 (R59 one-time). The *consumer's own* EL and BN use newly generated local non-signing keys and their own JWT, preserving exact original GENESIS but no owner private signing material. No provider-private-LAN bootstrapping, no required fixed public IPv4 or same infrastructure prerequisites.
3. Require **actual** native EL `net_peerCount>0` and Beacon node `/eth/v1/node/peer_count` `connected>0` across owner and VM4707, compare exactly same finalized root at exactly same finalized epoch, verify original genesis/fork and status `eth_syncing` as appropriate. Transport alone, TCP reachability alone, host Docker port binding alone, or unit tests alone do NOT establish full Ethereum synchronization.
4. Independent outside-provider host/laptop must repeat same native EL/CL sync (separate from provider-private IPv4) before claiming Internet-open permissionless third-party join. Only then add second independent validator via protocol roles and complete resource/SLA/reward/smart-contract deployment and end-to-end test.

Official public references: Besu node IDs, net_enode and dual-stack enodeV6 https://docs.besu-eth.org/public-networks/concepts/node-keys ; Besu peer monitoring https://docs.besu-eth.org/public-networks/how-to/connect/manage-peers ; Lighthouse node identity REST https://lighthouse-book.sigmaprime.io/api_bn.html ; Ethereum Beacon node identity schema https://ethereum.github.io/beacon-APIs/#/Node/getNetworkIdentity .
