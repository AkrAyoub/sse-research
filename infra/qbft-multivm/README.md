# R9 multi-VM QBFT deployment: actual validator operators, no GitHub Actions

> **R10 publication and real-client canary:** Source now contains an
> operator-approved, P2P-disabled Besu **26.11.1+** genesis canary that
> records a live block-zero hash and immutable Docker image digest, and a
> seeded research campaign for observational SLA ambiguity plus an
> evidence parser for Foundry/Ubuntu logs. Read
> `docs/research/R10_PUBLICATION_CAMPAIGN_AND_LIVE_CANARY.md` before running.
> The synthetic canary addresses are NOT real validators. Do not reuse
> its genesis or call its block0 result four-node consensus. No existing
> Anvil 31337 VM or real validator key is touched.
>
> **Fresh VM fast path and subsequent GitHub source updates:** Use
> `docs/research/R9_VM_SOURCE_ROLLOUT_AND_FIRSTHOST.md`. On an approved
> native Ubuntu checkout, `bash scripts/r9_ubuntu_firsthost.sh validator-1
> APPROVED_FULL_SHA` runs Linux gates and produces a read-only host readiness
> report. Tailscale login requires initial owner approval. Then an explicit
> `--apply-identity` generates the node's own Besu key locally once. To
> install a newer GitHub revision on a STOPPED R9 source checkout, use
> `tools/sse_r9_release_update.py`, which pins the exact approved SHA,
> reruns Ubuntu/Python gates and does not restart Docker or change chain state.
> **Do not run either tool on old Anvil/agent VMs.**
>
**Deployment status: NOT YET RUN ON LIVE BESU.** The client/image, Compose flags,
genesis hash, peer discovery and permissioning must pass these gates before any
financial/SSE workload. This is one independent Ubuntu host **per validator**.
It is not the four-container smoke lab, nor a PoW mining race.

## Research provenance / upstream references

- https://docs.besu-eth.org/private-networks/how-to/configure/consensus/qbft
- https://docs.besu-eth.org/public-networks/concepts/node-keys
- https://docs.besu-eth.org/public-networks/reference/options
- https://docs.besu-eth.org/public-networks/how-to/connect/configure-ports
- https://tailscale.com/docs/features/tailscale-funnel

Avoid unreviewed mutable Docker tags. Besu 26.8.0 appears in the 2026 release
feed, but **a working actual immutable Docker image digest is not known in
this repository**. Operator must obtain, independently verify, and pin it.

The baseline chain is 31338, QBFT 4 genesis validators, 5-second target period,
10-second request timeout, 15M gas limit, optional 1e13 test-wei block reward.
Changing genesis creates a **new chain**. Four independent **host identities** are
necessary but not sufficient to prove independent administrators.

## 0. Prerequisites

An SSE operator must first create a Tailscale tailnet, enable MagicDNS, and
authorize exactly the four validator machines. **No public DNS purchase.**
These are separate dedicated VMs, not VM4695 hosting Anvil chain31337.
A validator VM needs Ubuntu, Python3.12, pinned GitHub source (or reviewed signed
public archive), Tailscale connected, Docker Engine and Compose plugin, enough
CPU/RAM/disk, and a separately secured persistent data volume.
A source SHA alone does not grant roles, gas balances, a Tailscale membership
or a validator vote. Set tailnet ACLs so validator P2P TCP/UDP 30303 is reachable
ONLY between authorized validator/full nodes; do not expose JSON-RPC or Docker.
RPC must remain 127.0.0.1:18545, accessed via independently verified SSH tunnels.

**Source of truth is GitHub**: review an exact full SHA on
`integration/r7-wp09q-wan-multivm-no-actions`. These VM commands must be
executed on VM copies at that exact SHA. Updating all four VMs must be an
operator-approved staged rollout, not automatic `git pull` of a mutable
branch in a running consensus container. Never store validator secrets in GitHub.

Security: Docker group privileges are effectively root. Use dedicated machines
and audited Docker access; don't grant it to untrusted app participants.

## 1. First prove the Ubuntu host-specific tests

On ONE **new Ubuntu VM**, with reviewed SSE source and an isolated Python venv:

```bash
git rev-parse HEAD
python3 --version
python3 -m unittest discover -s tests -p 'test_sse_qbft_validator_identity.py' -v
python3 -m unittest discover -s tests -p 'test_sse_qbft_vm_preflight.py' -v
python3 -m unittest discover -s tests -p 'test_sse_qbft_block_sample.py' -v
python3 -m unittest discover -s tests -p 'test_sse_mesh_broker_http.py' -v
python3 -m unittest discover -s tests -p 'test_sse_vm_role_setup.py' -v
python3 -m unittest discover -s tests -p 'test_sse_ssh_identity_tunnel.py' -v
python3 -m unittest discover -s tests -p 'test_sse_lab_release_handoff.py' -v
```

No live Ethereum or Docker changes from these source tests. Run the complete
Ubuntu Python suite before marking R6 security accepted. Note that Python
offline tests don't validate a particular Besu binary.

## 2. Generate unique keys locally on FOUR distinct hosts

Each VM uses only its **own** Tailscale IPv4 reported by `tailscale ip -4`.
On validator-1, for example (repeat on validator-2/-3/-4 with their own IDs):

```bash
hostname
tailscale ip -4
id
install -d -m 0700 /home/"$(id -un)"/sse-qbft-private

python3 tools/sse_qbft_validator_identity.py init \
  --private-dir /home/"$(id -un)"/sse-qbft-private \
  --public-file /home/"$(id -un)"/sse-qbft-private/validator-1.public.json \
  --node-id validator-1 --tailscale-ip ACTUAL_100_X_ADDRESS

python3 tools/sse_qbft_validator_identity.py inspect \
  --private-dir /home/"$(id -un)"/sse-qbft-private \
  --public-file /home/"$(id -un)"/sse-qbft-private/validator-1.public.json
```

The private key file `node.key` is generated once, 0600, in the user-owned
0700 directory; no overwrites or key copying. **Never paste its contents.**
The `validator-1.public.json` file is safe to share with the operator after
inspection: it contains the 20-byte validator address and the 64-byte P2P public
key, with an authenticated overlay locator. Public records do NOT prove
physical ownership and are NOT automatically accepted into consensus.

**Important key compatibility check:** verify Besu itself can read
`node.key` and `besu public-key export-address` emits exactly the same
address as the public JSON on a throwaway fresh host. Do not start the full
validator fleet until that one-time compatibility test passes.

## 3. Assemble one immutable genesis (operator workstation only)

Collect four distinct **public validator addresses** from the four host records
plus any independently created public consumer/provider account to receive
TEST chain gas funds. On the trusted **operator machine**:

```bash
mkdir -m 700 -p .local/qbft-r9-genesis
python3 tools/sse_qbft_network_assembly.py genesis \
  --output-dir .local/qbft-r9-genesis \
  --public /trusted/validator-1.public.json \
  --public /trusted/validator-2.public.json \
  --public /trusted/validator-3.public.json \
  --public /trusted/validator-4.public.json \
  --fund 0xPUBLIC_TEST_EOA
sha256sum .local/qbft-r9-genesis/genesis.json
```

Only the operator may publish this genesis with a signed release manifest.
Copy **identical** audited genesis bytes into a NEW private folder on each VM
and independently confirm SHA-256. Do not use Anvil's known dev account as a
sensitive real-world wallet. Do not include validator secrets in genesis.

## 4. Pin the executable/image and prove local host readiness

On all four VMs, ensure Docker Engine + Compose are available and the reviewed
Besu image has been pulled and verified. A **version + immutable sha256 digest**
is required; never use `latest` or the placeholder in `env.example`.

Create a dedicated persistent data/config directory as the intended Linux user;
copy public genesis/config/peer hints there. Use real Unix UID/GID consistent
with Compose file permissions and a node-private-key file only on THIS host.
The Compose template lives at `infra/qbft-multivm/compose.yaml` and uses
host networking, the host's Tailscale IP, and loopback-only HTTP RPC.

**Do not start real validators with an empty bootnodes file.** Besu can fall back
to default Mainnet bootnodes if no peers are configured. Instead use the NEW
`genesis-canary.compose.yaml` with `--p2p-enabled=false` and
`--discovery-enabled=false` to check the actual genesis block-zero hash in a
disposable isolated data folder. Only after signing a matching peer catalog
do we start any validator. A single canary is NOT a blockchain network,
and it must never be used as a validator.

```bash
python3 tools/sse_qbft_vm_preflight.py \
  --expected-revision THE_ACTUAL_REVIEWED_40_CHARACTER_GIT_SHA \
  --besu-image 'hyperledger/besu:REVIEWED_VERSION@sha256:REAL_64_HEX_DIGEST' \
  --genesis /srv/sse-qbft/config/genesis.json \
  --genesis-sha256 REAL_64_HEX_GENESIS_SHA256 \
  --private-dir /home/USER/sse-qbft-private \
  --public-file /home/USER/sse-qbft-private/validator-1.public.json
```

Preflight checks Ubuntu, exact Git SHA, SHA256 of genesis, chain ID and
block/gas parameters, local node-key/public identity match, online Tailscale
address ownership, live Docker Engine and Compose, legacy port 8545 not
occupied, validator port 18545/P2P port availability. No container is started.

The `env.example` is only a template; copy to a **local**, operator-reviewed
`.env` (do not commit), replace ALL placeholders and point `BESU_NODE_KEY`
to this node's PRIVATE `node.key`. `BESU_UID` and `BESU_GID` must be the
correct numeric owner of data/config files. `BESU_DATA` must be a fresh empty
directory and never an Anvil/other-chain database.

Before the first `docker compose up`, manually check:
```bash
docker compose -f infra/qbft-multivm/compose.yaml --env-file .env config --quiet
docker run --rm --entrypoint besu 'hyperledger/besu:REVIEWED_VERSION@sha256:REAL_DIGEST' --help
```

These arguments are illustrative: enter a **real validated** image ref.
No `--apply` action in the preflight; activation is a separate approved action.

## 5. Derive actual block-zero hash with an isolated canary

Set reviewed `BESU_IMAGE`, `BESU_UID`, `BESU_GID` and
`BESU_GENESIS` in a **private .env file** on a NEW Ubuntu host.
The canary service uses NO validator key or persistent validator data;
P2P and discovery are disabled. It only exposes loopback RPC on port18559.

```bash
docker compose -p sse-genesis-canary \
  -f infra/qbft-multivm/genesis-canary.compose.yaml \
  --env-file .env config --quiet

docker compose -p sse-genesis-canary \
  -f infra/qbft-multivm/genesis-canary.compose.yaml \
  --env-file .env up -d

curl -sS --max-time 5 -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_getBlockByNumber","params":["0x0",false]}' \
  http://127.0.0.1:18559

docker compose -p sse-genesis-canary \
  -f infra/qbft-multivm/genesis-canary.compose.yaml \
  --env-file .env logs --tail=80

docker compose -p sse-genesis-canary \
  -f infra/qbft-multivm/genesis-canary.compose.yaml \
  --env-file .env down
```

Record the actual **block-zero hash** (NOT the SHA256 of the JSON file).
If the canary does not start, do not deploy 4 validators: inspect flags,
image, genesis parser and permissions and fix in GitHub. This is a
controlled **disposable canary project**, not a command to remove any
other Compose services/chain. Preserve sanitized logs and image digest.

## 6. Sign peer catalog, then start the genuine 4-validator network

1. Operator obtains four independently generated public validator reports.
   Use `sse_qbft_fleet_evidence.py collect` locally on each VM and
   `sse_qbft_fleet_evidence.py audit` on the operator checkout to reject
   copied SSH host keys, reused Tailscale device identities, overlay IPs,
   different source SHAs and duplicated P2P keys. This is a **clone/consistency
   check**, not proof of separate physical administrators.
2. From the four public records and the observed canary hash, create the
   unsigned `SSE_QBFT_PEERS_V1` catalog. Pin and sign via the existing
   offline Ed25519 signer; publish the signed catalog through a reviewed HTTPS
   source, not a private repository with shared tokens.
3. Each VM verifies the signed catalog and creates its own immutable
   `bootnodes.txt` before starting a validator. It should identify **at
   least two** distinct other peers and carry the same public genesis hash
   and chain ID 31338. The signed file is an initial trust anchor; native
   Besu discovery handles peer expansion and reconnects. DNS enodes are an
   early-access feature and require explicit on-host testing.
4. All four VMs pass `sse_qbft_vm_preflight.py`. Then operator starts the
   single local `qbft` service per VM from the reviewed, pinned
   `infra/qbft-multivm/compose.yaml`. Never run the four-validator smoke
   Compose on one VM as a substitute for independent hosts.
5. Use four identity-pinned loopback RPC tunnels to run
   `sse_qbft_readiness.py --require-four`. Check actual validator views,
   P2P peer counts, genesis, common height/hash and advancement. Head
   agreement does not by itself prove physically independent hosts.
6. Only after read-only agreement passes, execute approved synthetic
   transactions on **chain31338**, never the protected Anvil chain31337.

No automatic wallet transactions, validator votes, or synthetic rewards
are activated merely by publishing code or starting Tailscale.

## 7. Collect raw real-block metrics, not guessed values

Use four independently verified local RPC tunnels, a signed catalog and
the real genesis hash:

```bash
python3 tools/sse_qbft_block_sample.py \
  --manifest /trusted/sse-qbft-peers.json \
  --public-key /trusted/sse-peer-signer.pub \
  --genesis-hash 0xACTUAL_GENESIS_BLOCK_HASH \
  --rpc-url http://127.0.0.1:18545 \
  --rpc-url http://127.0.0.1:18546 \
  --rpc-url http://127.0.0.1:18547 \
  --rpc-url http://127.0.0.1:18548 \
  --blocks 40 --output .local/qbft-first-40.json
```

Output contains actual gas used, block bytes, transaction counts, p50/p95
inter-block periods, chain hash agreement, common head and **observed**
transactions/second. It explicitly reports that proposer identity/reward
accounting, physical independence and external enrollment have NOT been
proven by RPC sampling. To measure proposer rewards, add explicit before/after
balance observations with QBFT author/signature evidence.

Before deleting any disposable VM, capture logs and hash-index them using
`sse_experiment_evidence.py`. A checksum-only manifest is not a raw-log
archive. Preserve original run seed, client image digest, VM resources,
UTC timestamps and observed faults.

## 8. Failures and teardown/rebuild experiments

Run under an explicit **experimental window** only, never on VM4695:
- 0 failures: all 4 peers connected, common hash, expected block rate;
- 1 validator down: others continue if quorum available;
- 2 validators down: observe consensus stall (do not create fake blocks);
- restart same validator with same key and data: expect catch-up;
- move one host across NAT / change DHCP IP: tailnet locator and signed
  catalog must still connect; record reconnect latency;
- new fifth full node joins via signed peer catalog and syncs (no
  validator vote automatically);
- candidate fifth validator requires explicit QBFT governance/vote and
  an independently generated key; initial identity ceremony for only four
  genesis validators will need a separate governed add-validator tool.

Do not conflate a simulated failure model with evidence of real independent
administration. Pending SSE leases, settlements, EOA balances and bonds
must be accounted for before **any** network teardown.
