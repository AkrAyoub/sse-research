# R11 — open SSE roles, four-host QBFT lab, actual-genesis deployment

Date: 2026-11-18. STATUS: NEW GITHUB SOURCE. No new live validator deployed.

## Four is a research starting condition, never a production membership cap

R11 chain31338 is a 4-genesis-validator *permissioned QBFT*
experimental network. That restriction gives clean controlled 0/1/2
validator outage experiments and reproducible gas/finality measurements.
It is NOT the final permissionless validator model. An SSE participant
can request any combination of observer, full_node, consumer, provider,
monitor and validator. Each role has separate eligibility and activation
rules. Tailscale login, signed source or peer catalog does NOT award
block consensus privileges.

**Open production consensus** should rely on an actual Sybil-resistant
permissionless network (for a rapid EVM-compatible experiment, deploy SSE
contracts to a verified Ethereum PoS public testnet such as Hoodi or
Sepolia). Joining the Ethereum validator set requires native staking,
a consensus client and activation under Ethereum's protocol; an SSE
wallet-signature request is only a request, never a validator activation.
If SSE must be an independent L1 with its OWN permissionless validators,
a separately implemented and evaluated PoS/PoW consensus mechanism
remains a major uncompleted workstream. Don't claim that QBFT voting
makes permissionless validators. No admin approval for public
consumer/provider/monitor/full-node participation.

The administrator provisions research VMs, verifies binaries, funds
test wallets and preserves test data; a lab SSH/Tailscale owner is not
a blockchain role gatekeeper. External participants must not be forced
to join or switch personal Tailscale accounts: public P2P and relay
reachability remain necessary network implementation work.

## 4-real-public-key QBFT chain, not the earlier synthetic canary

Observed VM4704 R10 synthetic canary block0:
0xb02111fe8aed30292588a296d35303fe2fb60cfa0b41fcb86b3bd7ee21024c34
NEVER USE THIS AS THE ACTUAL VALIDATOR FLEET GENESIS HASH.

Source SHA for the new R11 GitHub package must first pass Windows
manual gate and Ubuntu security tests, then be pinned on all four VMs.

1. VM4704 can run validator-1 on its existing Tailscale identity.
   Use bash scripts/r9_ubuntu_firsthost.sh validator-1 FULL_SHA
   --apply-identity. This creates its own local 0600 node.key one time.
2. Provision three other distinct Ubuntu VMs. Pin the SAME FULL_SHA
   and run validator-2, validator-3 and validator-4 firsthost commands
   respectively. DO NOT COPY ANY node.key between hosts.
3. Export ONLY each public validator-N.public.json record through
   a trusted public-data channel. Put all 4 public records into a
   private operator folder on VM4704; none contains a private key.
4. Assemble one shared genesis with
   python tools/sse_qbft_network_assembly.py genesis
   --public PUB1 --public PUB2 --public PUB3 --public PUB4
   --output-dir EXISTING_EMPTY_PRIVATE_DIR
   and compute sha256sum genesis.json.
5. NEW: Run tools/sse_qbft_real_genesis_canary.py with four
   --public records, --genesis, --genesis-sha256, --image,
   --source-commit, --run-id and --output-dir. The image MUST be
   an actual digest-pinned image already observed and cached.
   VM4704's prior successful canary observed:
   hyperledger/besu:26.11.1@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d
   The new script is DRY RUN without --apply and starts a disposable
   P2P-disabled Besu only with --apply. Preserve its REAL block0
   hash and Docker output in a NEW evidence folder.
6. Create unsigned peer payload with
   python tools/sse_qbft_network_assembly.py catalog
   --public PUB1 --public PUB2 --public PUB3 --public PUB4
   --genesis-hash REAL_BLOCK0_HASH --revision FULL_SHA
   --output-dir ANOTHER_EMPTY_PRIVATE_DIR
   Sign via the existing offline Ed25519 peer catalog signing utility.
   Never put the private peer-catalog signing key on any validator.
7. Distribute genesis.json, PUBLIC signer PEM and signed catalog to
   each validator independently. New tools/sse_qbft_host_env.py
   validates signature/expiry, FULL_SHA, actual real-genesis hash,
   SHA256 of genesis file, four derived validator public keys,
   this host's node key and peer locators, and pinned Besu image;
   --apply writes one 0600 .env. It never starts Docker or
   grants validator authority.
8. The long-running Compose file is corrected: no more
   --bootnodes=/etc/sse/bootnodes.txt file path. Instead
   --bootnodes receives real comma-separated verified enodes from
   BESU_BOOTNODES_LIST. Java JNA/Netty gets an explicitly executable
   private tmpfs while the rest of the container remains read-only
   with dropped Linux capabilities and no-new-privileges.
9. Start EACH Besu process only after runtime preflight and operator
   approval. Check real 4-host consensus with
   tools/sse_qbft_readiness.py and multiple independently pinned RPC
   views. Do not count the earlier synthetic canary or mere
   Tailscale connectivity as consensus.
10. Deploy and fund real SSE smart contracts on 31338, execute funded
    consumer/provider/monitor transactions, then collect raw physical
    HTTP/compute traces, 0/1/2 validator outages and monitor fault arms.
    A separate public PoS chain deployment is needed to actually study
    open validator admission/rewards.

## Acceptance checklist

- Four fresh independent machine-local Besu P2P keys and public records
- Single real genesis with observed actual block0 and signed peer list
- Four independently running Besu nodes produce agreeing blocks
- EVM SSE contracts deployed with receipts and no bridge to Anvil31337
- End-to-end funded real service lease and monitor-selected settlements
- Fault/partition trials, gas and safety/liquidity comparisons
- External permissionless participants on publicly accessible consensus,
  without administrator/tailnet permission gates
- No old Anvil VM4695 state modification, no GitHub Actions

Vendor references:
https://docs.besu-eth.org/private-networks/how-to/configure/consensus/qbft
https://docs.besu-eth.org/private-networks/how-to/configure/bootnodes
https://ethereum.org/developers/docs/consensus-mechanisms/pos/
https://ethereum.org/developers/docs/networks/
