# R68 — launch real VM4707 independent NONSIGNING native Ethereum node

Original VM4706 R65 real migration SUCCESS, and actual R67 test **10/10 PASSED** plus read-only live check returned:
- Original live chain ID **31340**, execution block **3817** and post-R65 finalized Beacon epoch **122**, root `0x6310aca4e76388f48323370de92019a9b7689ad4e742de698a2eb019486b7888`; original single validator running.
- Actual owner Besu EL P2P listening on open-join ZeroTier network `ff2328775f000000`, host `fca0:2328:776e:4750:395b::1` port TCP/UDP30404; actual original execution enodeV6 derived from real live `net_enode` public ID.
- Original Lighthouse BN ENR read directly from locally running `/eth/v1/node/identity`; R67 decoded actual ENR ip6 equal owner 6plane, tcp6=9000 and udp6=9000. Peer counts EL **0**, CL **0**, as expected BEFORE first external join. **Finality progressed after original R65 maintenance; original single signer remains online**.
- R68 `tools/sse_pos_r68_vm4707_real_native_observer_join.py` pins BOTH public bootstrap records verbatim to original R67 result, invokes the already-developed standalone R59 observer with those identities. NEW R59 source pins non-overlay IPv4 advertise to `127.0.0.1` and IPv6 UDP discovery to30404, like the actual owner. This is not a source-key transfer, and does not create/import validator signing keys.
- VM4707 previously really passed R59 old `--plan`: original 4-file public genesis archive **exact SHA256**, correct immutable Besu/Lighthouse Docker images and actual PUBLIC ZeroTier `fca0:2328:77b8:6578:a55::1`. The corrected R59/R68 version must be tested locally before create-once.
- Source GitHub repo `AkrAyoub/sse-research` is **PRIVATE**. There is **no PUBLIC self-service release yet**; GitHub read-only access for VM4707 is a developer setup requirement, not a permissionless network admission restriction. A user without GitHub credentials cannot fetch from this private developer repo. Do NOT misrepresent that as finished global no-registration onboarding; for this test, operate via a VM4707 GitHub checkout with authorized repository read-only access, not SSH/SCP to VM4706 or private-LAN Ethereum bootstrap. Future public distribution MUST remove that dependency.

## On VM4707: exact one-time real observer deployment

To avoid password prompts and accidental private source transfers, first use the VM4707 account's existing GitHub SSH read credentials to create/refresh a local readonly checkout. These commands do **not** create a second validator. If GitHub access fails, **stop and return the sanitized Git error**; do not use owner signing credentials or SCP from owner VM.

```bash
(
  set -e
  export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=yes -o BatchMode=yes -o IdentitiesOnly=yes"
  if [ ! -d "$HOME/sse-research/.git" ]; then
    git clone --no-checkout git@github.com:AkrAyoub/sse-research.git "$HOME/sse-research"
  fi
  cd "$HOME/sse-research"
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
  SHA="b02c215e5a249dccb4ba2cee8770f6a405ac9d4e"
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  echo "== R59 updated observer safety tests =="
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r59_native_ipv6_observer.py' -q
  echo "== R68 real source bootstrap tests =="
  python3 -B -m unittest discover -s tests -p 'test_sse_pos_r68_vm4707_real_native_observer_join.py' -q
  sudo -v
  echo "== REAL ORIGINAL GENESIS / IMAGE / VM4707 PUBLIC OVERLAY PLAN =="
  python3 -B tools/sse_pos_r68_vm4707_real_native_observer_join.py --plan
  echo "== REAL NONSIGNING EL+CL CREATE-ONCE, OWNER-APPROVED =="
  python3 -B tools/sse_pos_r68_vm4707_real_native_observer_join.py --apply
)
```

**Real R59 installer asks the actual VM4707 local operator to type `CREATE-REAL-R59-NONSIGNING-OBSERVER`.** After successful apply, original chain genesis public archive is unpacked into new user-only directories; VM4707 gets its OWN client keys and JWT (never VM4706's keys or JWT), one Besu EL and one Lighthouse Beacon BN, and NO VC, PoS signer or wallet. Docker publishes only overlay-native P2P+loopback non-privileged API. The source may take time to sync genuine genesis and finalize; initial peer count zero is not proof of failure until peer routing/timeout validated.

**Do not rerun on partial create**; R59 refuses preexisting directory/network/containers. Inspect current Docker state if failed.

## Immediately after apply: non-disruptive TWO-LAYER peer proof

On VM4706 rerun read-only original `tools/sse_pos_r67_post_migration_native_bootstrap_audit.py --audit` from pinned checkout: check `originalExecutionNativePeerCount > 0` and `originalBeaconConnectedNativePeers > 0`, plus finalized epoch progression. On VM4707, check only its LOCALHOST APIs:
- Execution JSON-RPC at `127.0.0.1:28545`: `eth_chainId` must equal31340; `net_peerCount` must exceed0; `eth_blockNumber` should approach owner; `eth_syncing` returns current actual syncing mode.
- Consensus Beacon REST at `127.0.0.1:25052`: `/eth/v1/beacon/genesis` genesis time must match owner; `/eth/v1/node/peer_count` connected must exceed0; `/eth/v1/beacon/states/head/finality_checkpoints` finalized root at same finalized epoch must equal VM4706. No private authentication/JWT endpoints exposed.
- Still need OUTSIDE-provider laptop test of same native EL+CL protocol to establish truly global cross-infrastructure join, and independent multi-validator staking/eligibility/rewards and SLA/contracts integration. PUBLIC ZeroTier root/relay dependence remains; no provider-private LAN native bootstrap allowed.

**Neither source tests nor native host Docker port binding prove remote P2P/finality.**
