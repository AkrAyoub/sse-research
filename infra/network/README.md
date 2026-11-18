# SSE cross-cloud enrollment, cryptographic discovery and signed distribution

**Integration stage (2026-11-18). Source and offline test cases exist; no real public HTTPS broker, public Tailscale tailnet, independent four-VM Besu deployment or authenticated external host acceptance has yet been proven.** NO GitHub Actions are used.

This package extends the existing R6/R7 code, rather than replacing `tools/sse_vm_bootstrap.py`, `tools/sse_vm_role_setup.py`, `tools/sse_vm_enroll.py`, `tools/sse_vm_overlay.py`, `tools/sse_mesh_broker.py`, `tools/sse_release_verify.py` or `tools/sse_ssh_identity_tunnel.py`. It preserves Anvil chain 31337 and its existing funded lease.

## What "any machine can join" actually means

Any **network-reachable Ubuntu host under its own administration**, including home, campus and third-party cloud networks, can download an approved SSE release, establish outgoing HTTPS to an SSE enrollment service, and request a mesh connection **if the operator authorizes that host**. Hosts do not need an address within the old 10.50.56.0/24 subnet; DNS, SSH and Tailscale overlay identities must be checked independently. After overlay join, an agent still requires its own encrypted EOA and an on-chain transaction to become a bonded monitor.

- An application participant can operate consumer, provider, monitor or observer roles. Role declaration in UI or join request does NOT imply on-chain authorization, funding, committee eligibility or physical independence.
- An Ethereum **full node** may join the peer network using an approved signed bootstrap record and its own Besu P2P identity, subject to any node-permissioning/mesh ACL policy.
- A **QBFT validator** must ALSO enter the on-chain QBFT validator set under a reviewed voting/governance process. Four genesis validators are fixed for the first controlled experiment; a new VM is NOT automatically a validator.
- The initial Tailscale tailnet + OAuth broker is a **managed, invitation-based overlay**. It is not permissionless access to consensus or a fully decentralized public DHT. A future permissionless onboarding design needs an explicitly tested open transport / relay / peer-discovery alternative, Sybil resistance and governance. Do not label this stage permissionless.

## Responsibility split

| Component | Truth owned | Independent of a changing DHCP IP? |
|---|---|---|
| GitHub source commit | reviewed source revision | yes; pin full SHA |
| Signed public archive | signed publisher SHA, archive digest, intended contract/roles | yes; distributor can change |
| Enrollment broker | one-time authorization for node ID + explicit roles | yes; DNS and HTTPS origin; not an on-chain actor |
| Tailscale mesh | encrypted connectivity, ACL/device identity, mesh DNS | yes under supported readdress/reconnect; tailnet availability still a dependency |
| Besu node key/enode | unique P2P node key, NOT VM hostname | yes; public key stable while locator updates |
| Signed peer catalog | chain 31338 genesis hash, source SHA, fresh enode+FQDN/IP map | yes after signed republish and refresh |
| SSE EOA | on-chain consumer/provider/monitor account | yes; never copied between VMs |
| SSE chain | contracts, fees, committee, proof, escrow, payouts | independent of HTTP control plane; RPC trust/finality need separate proofs |

**Old incident to prevent:** VM4695 moved from 10.50.56.20 to 10.50.56.14; earlier VM4699 was lost; VM4693 SSH tunnel had >1700 restarts. The original IP was a locator, not a trusted identity. The old SSH key fingerprint remains pinned and may be used for a *local lab recovery only*. Duplicated Linux portal hostnames and copied EOA/SSH keys also must not be mistaken for unique nodes.

## A. An operator sets up the network exactly once

1. Provision a dedicated HTTPS enrollment host with a **public DNS name** and a real TLS certificate, independent of the original Anvil VM. Apply restrictive firewall rules and logs that never include POST bodies/tokens.
2. Create a Tailscale tailnet with tags, restrictive policy grants, tag ownership and separate categories for app nodes, non-validator full nodes, and validator hosts. This first lab's existing broker can only mint `tag:sse-node`. Do not grant broad network administrator rights to ordinary tagged participants.
3. Create an OAuth client restricted to creating Tailscale auth keys with **only** `tag:sse-node` permission. Do not place its secret in the GitHub repository, chat, cloud-init or client VM.
4. On the enrollment host, create a private database directory and root/service-owned mode-0600 files for the Tailscale OAuth ID/secret. First use `tools/sse_mesh_broker.py --db ... --node-id ... --roles ...` to issue a short-lived one-time token for a specific identity.
5. Start `tools/sse_mesh_broker_http.py` behind an authenticated/controlled production HTTPS reverse proxy. The supplied `infra/network/Caddyfile.example` illustrates the path, but review TLS, firewall, request throttling, DDoS limits and certificate lifecycle separately.

Example on an **already prepared and approved** dedicated Ubuntu enrollment host:

```bash
sudo install -d -m 0700 /var/lib/sse-broker
# Separately provision approved OAuth credential files mode 0600 under /etc/sse.
python3 tools/sse_mesh_broker.py \
  --db /var/lib/sse-broker/enrollment.sqlite \
  --node-id provider-outside-01 --roles provider

# The command above emits a one-time token ONCE. Deliver via a private,
# authenticated provisioning channel, never via GitHub or paste logs.
sudo python3 tools/sse_mesh_broker_http.py \
  --database /var/lib/sse-broker/enrollment.sqlite \
  --client-id-file /etc/sse/tailscale-oauth-id \
  --client-secret-file /etc/sse/tailscale-oauth-secret --port 18781
```

The service binds only to 127.0.0.1:18781; the publicly reachable HTTPS reverse proxy forwards POST `/v1/mesh/enroll`. Token and requested roles must match. Token redemption is atomic and single-use. Upstream issuance errors invalidate the token; the operator must issue a new one. A status-200 response contains a 300-second one-off Tailscale auth key. **HTTP response credential is never a GitHub or Ethereum private key.**

Do not deploy the Python `wsgiref` listener as a directly exposed public production server: it is a loopback pilot endpoint behind an appropriate reverse proxy/service manager.

## B. An external Ubuntu host joins (without credentials for the private repo)

First obtain an independently **pinned publisher Ed25519 verification public key**, a public HTTPS location for a signed release manifest, and an operator-approved chain/contract tuple. The repo may remain private; source distribution is an **explicit public export of an approved revision**, not a token-bearing Git clone.

The source publisher performs manually on a trusted development machine, from a clean approved commit:

```bash
git status --porcelain
git rev-parse HEAD
git archive --format=tar.gz --prefix=sse-research/ \
  --output=/tmp/sse-approved-source.tar.gz HEAD
sha256sum /tmp/sse-approved-source.tar.gz
```

**Do not publish the full private Git history.** Review the archive's source and docs for any private information before uploading. The release manifest must use the existing `SSE_RELEASE_V1` format: actual source commit, expected chain ID, deployed settlement address, approved roles, HTTPS artifact URL, SHA256 and an expiry no more than 14 days after creation. Sign using a separately protected Ed25519 publisher key and distribute the public verification key independently. GitHub is the source of the approved commit; a public HTTPS server/CDN can host the signed archive and envelope. Nothing is published automatically by GitHub Actions.

On the **new** host with Python 3.12 and PyCryptodome installed in its isolated bootstrap environment:

```bash
python3 tools/sse_signed_release_install.py \
  --manifest /trusted/sse-release.json \
  --publisher-public-key /trusted/sse-publisher.pub \
  --chain-id 31338 --settlement 0xYOUR_ACTUALLY_DEPLOYED_SETTLEMENT \
  --roles provider --target /opt/sse/release

# After verifying printed plan and local prerequisites:
python3 tools/sse_signed_release_install.py \
  --manifest /trusted/sse-release.json \
  --publisher-public-key /trusted/sse-publisher.pub \
  --chain-id 31338 --settlement 0xYOUR_ACTUALLY_DEPLOYED_SETTLEMENT \
  --roles provider --target /opt/sse/release --apply
```

The installer refuses to overwrite an existing release target, rejects redirecting HTTPS, checksum mismatches, tar path traversal, symlinks, oversized archives and mismatched signed chain/roles. It installs **source only**; Python dependencies, role-agent activation, wallet generation and on-chain registration are separate reviewed phases. Before chain31338 contracts exist, do NOT fabricate an SSESettlement address: bootstrap the validator hosts using pinned Git source and R9 configuration instead.

If a VM already has an approved private Git checkout, the existing `sse_vm_bootstrap.py` and `sse_lab_release_handoff.py` remain available under their original trust assumptions; do not overwrite the live Anvil nodes.

To connect a provisioned outside host to the mesh (after operator has securely delivered the one-time token file, mode 0600 under `/run/sse`):

```bash
sudo python3 tools/sse_vm_enroll.py \
  --node-id provider-outside-01 --roles provider \
  --broker-url https://enroll.example.org

# Requires separately installed, approved Tailscale package, broker and token.
sudo python3 tools/sse_vm_enroll.py \
  --node-id provider-outside-01 --roles provider \
  --broker-url https://enroll.example.org --apply
```

Never print, paste, commit or log the token. Existing `sse_vm_role_setup.py init` creates local encrypted role wallets; `status` is read-only. Monitor registration or bidding has its own signed transaction limits, gas caps and contract eligibility checks. A host with multiple roles MUST NOT attest to its own lease as an independent monitor.

## C. Consensus peers find each other when IP addresses change

Besu enodes contain the immutable P2P node public key and an ephemeral locator. A signed `SSE_QBFT_PEERS_V1` envelope binds 4+ validator entries, node IDs, enodes, initial chain 31338, actual genesis hash, reviewed source SHA, issuance time and expiry. The operator signs offline. Each VM receives the independently pinned Ed25519 public key:

```bash
python3 tools/sse_network_peers.py verify \
  --manifest /trusted/sse-qbft-peers.json \
  --public-key /etc/sse/peers-ed25519.pub \
  --chain-id 31338 --genesis-hash 0xYOUR_ACTUAL_64_HEX_GENESIS \
  --self-id validator-1 \
  --output /srv/sse-qbft/config/bootnodes.txt
```

The first invocation creates a peer file; it **refuses overwrite**. For later signed announcements, use `sse_peer_refresh.py` with `--apply` to replace only the locally verified peer hints atomically. An untrusted download, old/expired signature, changed genesis, duplicate peer key, or a 10.50.56.x private endpoint must fail closed. The example systemd timer runs locally every five minutes and is **not** a GitHub Action.

Hostnames in enodes need Besu private-network early-access DNS options (`--Xdns-enabled`, `--Xdns-update-enabled`) and DNS-reverse-lookup support in a validated client version. Re-resolution, long-lived TCP sessions, periodic refresh and service restart semantics MUST be tested on real VMs; the signed file alone does not guarantee hot peer reconnection.

For early experiments, a Tailscale `100.64.0.0/10` address offers host-independent reachability across NAT; if device identity/authentication changes and the overlay address changes, publish a new signed locator and restart/reconnect as required. Never bind a validator to an old, private DHCP address.

## D. Four real validator VMs and no shared administrator artifacts

The starting R9 design remains **4 distinct Ubuntu VMs**, Besu QBFT **chain 31338**, **5-second** target period, **10-second** QBFT request timeout, **15M** block gas limit and an optional explicit **1e13 wei** synthetic proposer reward. These are preregistered research baselines, not measured optima. Historical 667093-gas SSE lease funding permits a theoretical 22 such transactions in an empty 15M-gas block before overhead; measure actual throughput and block bytes.

Each VM independently generates and stores its **own** Besu node key locally (never in GitHub) and uses separate persistent state; the GitHub branch contains only the shared, key-free `sse_qbft_lab_config.py` generator. The four validator public addresses form genesis `extraData`. Verify identical genesis files and hash independently.

The one-VM-four-container `infra/qbft-lab` design in another branch is a *disposable syntax/smoke lab* and must not be used to claim independent consensus entities. For multi-VM launch, see `infra/qbft-multivm/compose.yaml`. It runs **one** Besu instance on each Ubuntu host using host networking so P2P can bind to that VM's verified overlay IP. RPC binds only to `127.0.0.1:18545`, and a reviewed digest-pinned Besu image is mandatory. The host must prevent unintended public P2P exposure and configure mesh ACLs.

Early deployment order:
1. Validate the pinned Besu version, genesis parser, early-access DNS switches, required image digest, Docker UID/GID and system resources on ONE fresh dedicated VM.
2. Start one validator as a genesis-only canary using an initially empty bootnodes file; inspect block0 and its genesis hash. This VM alone will NOT finalize new blocks.
3. Independently sign a peer catalog after the real genesis hash is known, including the four unique node keys and overlay locators. Distribute the signed catalog; generate per-VM peer lists.
4. Start each remaining validator with the **same genesis**; restart the first canary with its verified peers when approved.
5. Run `sse_qbft_readiness.py --require-four` against **four authenticated loopback RPC tunnels** (not public JSON-RPC). Verify chain ID, block0 hash, validator lists, peer connectivity and common-height block hash.
6. Repeat after stopping one validator; then stop two and record consensus stall. Test restart and IP change, original key persistence and no chain reset. A successful status report is not proof of independent administrators or protocol slashing.

The compose template does not generate keys, fund wallets, install Tailscale, vote in validators or launch on its own. Initial off-chain SSH/key distribution and trusted genesis/manifest publication remain operator gates.

## E. Remaining limits (must not be hidden)

- Tailnet admission is still operator/invitation-controlled; open anonymous public peer discovery, relay and Sybil-resistant validator entry are **not** implemented.
- Tailscale outage and broker outage may stop new admission; existing connected nodes should continue according to overlay/client behavior, which still needs live testing.
- GitHub private repo does not allow anonymous clones; the signed public archive solution solves source delivery only after a human/approved release publisher creates and hosts the package.
- Peer catalogs are **discovery hints**, not consensus finality proofs. `sse_qbft_readiness.py` checks observable agreement, not Byzantine safety proofs.
- Monitor EOA, provider EOA, validator P2P identity, SSH host key, overlay device identity and Linux hostname are all distinct. Never copy keys or assume one means another.
- No automatic chain-state-changing transaction may be triggered by release installation, mesh join, peer refresh or VM restart.
- Do not run `forge test` or VM commands via GitHub Actions. Manual local/source-pinned execution only.

## Local validation (operator-triggered)

```bash
python3 -m unittest discover -s tests -p 'test_sse_mesh_broker_http.py' -v
python3 -m unittest discover -s tests -p 'test_sse_network_peers.py' -v
python3 -m unittest discover -s tests -p 'test_sse_peer_refresh.py' -v
python3 -m unittest discover -s tests -p 'test_sse_qbft_readiness.py' -v
python3 -m unittest discover -s tests -p 'test_sse_signed_release_install.py' -v
python3 -m unittest discover -s tests -v
forge build && forge test -vv
```

Do not mark WAN onboarding or R9 ACCEPTED from these offline tests: real heterogeneous internet hosts, dynamic-IP failover, signed releases, independent keys, DDoS/tailnet trust, RPC access and Besu consensus must all be exercised.
