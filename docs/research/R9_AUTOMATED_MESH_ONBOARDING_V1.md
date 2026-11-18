# R9 Domainless fully automated onboarding — validator and app roles

Date: 2026-11-18. **Code pilot; no live public credential broker, signed public
source publisher or unattended VM created yet.** GitHub is source of truth,
all changes committed on integration branch, no GitHub Actions.

## Goal: one operator decision, not a browser login per machine

A machine *anywhere on the Internet*, possibly behind NAT/DHCP, should be
able to download a verified release, join the overlay, discover blockchain
peers and start the authorized role after an invitation. Operator policy,
rate limits, Tailscale account access and validator governance remain
necessary. **It is incorrect to claim a truly permissionless network** merely
because enrollment becomes noninteractive.

### Current measured state

Windows on approved `a084793d22928219a557a10e637a5347d6befd17`:
**869 Python tests total, 20 skipped, 0 errors; 144/144 Foundry passed**.
VM4704 Ubuntu at same SHA: **50/50 Linux security tests passed with 0
skips**; `r9_ubuntu_firsthost.sh` ran 39 QBFT tests and reported that
Tailscale was initially `NeedsLogin`. The operator then manually logged
in VM4704, which became online as `sse-validator-1`,
Tailscale IPv4 **100.65.29.101**. VM has 2 vCPU, 3.8GiB RAM and Docker
restricted to sudo. **No validator node key was created and no Besu started
from these logs.** That existing device must NOT be logged out or
reauthenticated by the headless join tool.

### Final architecture

1. **Approved source distribution:** operator exports an immutable clean
   GitHub revision, signs SSE_RELEASE_V1 with protected publisher Ed25519
   key, publishes a read-only scrubbed archive and signed manifest over
   HTTPS (`*.ts.net` via reviewed Funnel or an approved artifact store).
   Target nodes bootstrap with a small, pinned installer and the
   publisher's verification-key fingerprint supplied out-of-band. No
   GitHub PAT, SSH deploy key, .git or secrets on random nodes. This
   archive publication and bootstrap delivery are **not automatic yet**.
2. **Operator provisioning:** a dedicated owner-side orchestration
   service maps an approved machine fingerprint, node ID and roles to an
   individual short-lived single-use invitation, delivered via secure
   cloud-init secret injection or authenticated out-of-band channel.
   **Never put tokens in GitHub, shell history, VM metadata accessible to
   other tenants, or pasted logs.** Bare bearer invitations must be
   hardened with proof-of-possession (local signed device challenge and
   nonce) before Internet-facing production use. This identity-bound
   approval/secret delivery is **not complete yet**.
3. **Transport:** dedicated validator-only Tailscale OAuth client with
   restricted `auth_keys` and **only** `tag:sse-validator`;
   separate app-role OAuth client with **only** `tag:sse-node`.
   Token redemption is atomic and consumes the invitation BEFORE key
   minting. Tags provide overlay ACL scoping, NOT consensus privileges.
4. **Internet endpoint:** separate root-only secret files and SQLite DBs:
   `tools/sse_mesh_broker_http.py` on 127.0.0.1:18781 for app roles
   and new `tools/sse_validator_mesh_broker.py` on
   127.0.0.1:18782 for validator invitations. Publish them only behind
   a reviewed production HTTPS proxy with request size cap, per-source
   throttling, credential redaction, secure access control and alerts.
   The Python wsgiref pilot is **NOT a production public HTTP server**.
   Funnel can expose HTTPS 443 or 8443 to a local service, but choose a
   stable and approved `*.ts.net` origin. Set its exact name in a signed
   bootstrap manifest; never trust a random DNS name from the joiner.
5. **New Ubuntu VM** (fresh, not the Anvil legacy host): a source-staged
   node runs `sse_validator_mesh_join.py --apply` as root after it
   receives /run/sse/validator.invitation, which contacts the dedicated
   broker by HTTPS and obtains a scoped 300-second **nonreusable** Tailscale
   key. `tailscale up --auth-key=file:/run/sse/validator-once.authkey`
   keeps the secret out of shell arguments/history. It erases auth key
   and invitation on success, verifies overlay identity and refuses to
   touch existing logged-in devices.
6. **VM-local services:** `r9_ubuntu_firsthost.sh` performs Ubuntu
   security gates and then independently generates its *own* local Besu
   P2P secp256k1 key, persistent DB and local wallets only after
   authorization. The `r9_headless_validator_bootstrap.sh` staged-source
   orchestrator connects steps 5/6 without operator browser login.
   Additional service unit generation, Docker image pin/validation,
   client flag validation and crash recovery still need live tests.
7. **Blockchain bootstrap:** four public validator keys feed single
   QBFT chain31338 genesis. A P2P-disabled disposable Besu canary
   checks actual block0 hash; an offline operator signer publishes
   bounded signed peers. Besu native discovery/gossip takes over.
   New validators require separately authorized QBFT voting/admission.
8. **Application layer:** consumers/providers/monitors use existing
   `sse_vm_enroll.py` broker with `tag:sse-node`, local independent
   EOA keys, signed evidence, economic bond and contract eligibility.
   Consumer/provider/monitor may coexist on a node but a monitor must
   not attest its own provider service. No app node becomes a validator
   by selecting 'validator' in a user-supplied roles string.

## One-time owner control-plane setup (not on every VM)

1. Strongly prefer a **dedicated SSE research tailnet**. VM4704 was
   manually joined to a **personal mixed-use tailnet**; leave it
   untouched for the pilot, but do not claim that personal tailnet
   enforces isolation without checking the whole policy.
   Tailscale policies compose additively; default `allow all` may
   exist when no rules have been configured. Example in
   `infra/network/tailscale-sse-dedicated.hujson.example` is only a
   reviewed STARTING POINT, not a safe patch for unrelated devices.
2. Owner creates `tag:sse-validator`, `tag:sse-node` and optionally
   `tag:sse-enrollment` with limited tag owners/grants. Reject
   wildcard grants to validator P2P ports and all remote JSON-RPC.
   Do not make the broker a validator or allow it SSH access to
   validator machines.
3. Owner creates TWO scoped OAuth clients for app versus validator
   tags. Keep their OAuth client ID/secret in protected files on a
   dedicated enrollment host only. Never distribute OAuth secrets
   to a node or store them on GitHub. Review tags, preauthorization
   and Tailscale device-approval settings.
4. Owner enables HTTPS/Funnel once on the dedicated enrollment VM
   after TLS, hardening, throttling, service-specific security and
   rate limiting. Funnel is **public**. External client can then
   enroll from other providers without a purchased domain or
   inbound public port.
5. Owner configures an **admission policy**: which machine can be
   consumer/provider/monitor/full node, and which nodes may be
   *candidates* for QBFT votes. Do not issue invites to anonymous
   hosts without identity checks and meaningful Sybil resistance.

## Developer/operator CLI: source-staged validator enrollment

Operator-only short-lived invitation issuance on the **dedicated
enrollment server** (database parent root owned mode0700; broker
service also runs with protected owner, with dedicated validator OAuth):

```bash
# DO NOT use ~/sse-r9 on VM4704 as a broker.
# Operator securely delivers the printed token by a separate secret
# provisioning channel, never by copying it into issue comments or GitHub.
sudo python3 tools/sse_validator_mesh_broker.py --issue \
  --database /var/lib/sse-enrollment/validator-invites.sqlite3 \
  --node-id validator-2
```

Run the dedicated pilot broker on loopback **behind a hardened proxy**
and a separate OAuth secret scope:

```bash
sudo python3 tools/sse_validator_mesh_broker.py \
  --database /var/lib/sse-enrollment/validator-invites.sqlite3 \
  --client-id-file /etc/sse-enrollment/validator-oauth-id \
  --client-secret-file /etc/sse-enrollment/validator-oauth-secret \
  --tailnet - --port 18782
```

On a **NEW** authorized Ubuntu validator host with source staged and
`/run/sse/validator.invitation` as root:root 0600 in root-controlled
`/run/sse`:

```bash
# first review without any system change:
sudo python3 tools/sse_validator_mesh_join.py \
  --node-id validator-2 --broker-url https://ACTUAL-APPROVED.ts.net:8443

# after operator-signed release+machine approval:
sudo python3 tools/sse_validator_mesh_join.py \
  --node-id validator-2 --broker-url https://ACTUAL-APPROVED.ts.net:8443 --apply
```

The resulting device identity should be present as `tag:sse-validator`;
confirm with Tailscale admin/device status and security policy tests.
THIS STILL DOES NOT PRODUCE A BLOCK OR MAKE IT A VALIDATOR.

The joined host then runs `scripts/r9_ubuntu_firsthost.sh validator-2
APPROVED_FULL_SHA --apply-identity` as its unprivileged source owner.
The root bootstrap wrapper combines these stages after the secure
invitation and source are provisioned:

```bash
sudo bash scripts/r9_headless_validator_bootstrap.sh \
  validator-2 LOCAL_SOURCE_OWNER APPROVED_FULL_SHA \
  https://ACTUAL-APPROVED.ts.net:8443 --apply
```

This wrapper **requires a Git checkout at ~/sse-r9 and the approved SHA**
or equivalent future source-staging mechanism before invoking it. It does
not bypass approval, install Linux/Docker from scratch, start containers,
sign wallets or submit blockchain transactions. Such entire-fleet
cloud-init provisioning and proof-of-possession remain outstanding
production work.

**VM4704 ALREADY JOINED:** do not use a fresh-invitation command. Keep
its existing `100.65.29.101` identity for the lab; review whether it
must be *retagged in an isolated tailnet* before deploying validator
P2P. Run the read-only host doctor and test the existing account.

## Acceptance tests to run before calling onboarding automatic

- Single-use correct role/node invite; wrong node and role fail
  without token burn, replay and expiry fail, upstream failure burns token
  and does not print secrets.
- A validator OAuth client can mint **only** `tag:sse-validator`;
  an app OAuth client **only** `tag:sse-node`.
  Deliberately request the wrong tag and verify Tailscale API rejects.
- Device offline/online/restart, DHCP renumbering, duplicate hostname,
  copied VM image, duplicate public validator key or SSH host key.
- No owned domain, no inbound public IP, fresh host from **outside**
  10.50.56.0/24. Store actual signed release SHA and peer catalog hash.
- Broker/Funnel offline during enrollment, revoked invitation, expired
  TLS cert, OAuth credentials rotated, inappropriate tailnet policy,
  malicious archive, high-rate unauthenticated redemption attempts.
- Existing node must survive broker outage and not require a new key;
  key replacement or revocation must be audited rather than silent.
- Signed chain genesis and 4 VMs independent, 0/1/2 validator faults,
  consensus reward accounting and monitor-service proofs validated.
- Full disposable fleet teardown/rebuild with complete logs and
  zero private secrets in GitHub.

## References

- https://tailscale.com/docs/features/access-control/auth-keys
- https://tailscale.com/docs/features/oauth-clients
- https://tailscale.com/docs/features/access-control/grants/grants-explained
- https://tailscale.com/docs/reference/tailscale-cli/up
- https://tailscale.com/docs/features/tailscale-funnel
