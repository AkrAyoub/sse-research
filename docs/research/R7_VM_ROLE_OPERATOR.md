# R7: Ubuntu participant role onboarding operator (research lab)

This is a **committed incremental automation primitive**, not fully unattended
fleet enrollment or production authorization. It extends the existing R6
read-only VM bootstrap; it does not replace source distribution, SSH/overlay
network bootstrap, workload installation, signed releases, or operator approval.

## Why

On the first two Ubuntu VMs, manually copying commands caused a missing
Foundry PATH (funding commands did not execute), followed by a predictable
gas-estimation failure on an unfunded monitoring wallet. We also had to
create encrypted role keystores and a temporary plaintext signer file.

`tools/sse_vm_role_setup.py` automates the participant part:
- `init`: generates a **unique encrypted wallet per role** locally, using
  the actual portal-provided hostname; creates files mode 0600 in an
  owner-only directory mode 0700. Refuses overwrites and copied manifests.
- `status`: checks file ownership/modes and optionally RPC chain ID,
  individual wallet balances, on-chain minimum bond, monitor registration
  status and count; **never** unlocks a key.
- `lab-fund`: preview by default; `--execute` uses only Anvil chain 31337
  and its well-known unlocked **development-only** account. Funds only the
  amount missing from the requested minimum wallet balance.
- `register-monitor`: preview by default; `--execute` explicitly unlocks
  the **local encrypted monitor wallet in memory** and reuses
  `sse_node_marketplace.execute` for preflight, signed raw transaction, gas
  spend cap and receipt checking. No plaintext key file is written.

The tool uses existing Python dependencies. **Foundry is not required on
ordinary participant VMs.** Only the chain/deployment operator needs Anvil,
forge and cast. Do not change VM hostnames.

## First use on a new participant VM with an independently verified checkout

Assumes Python 3.12, a pinned checked-out and reviewed source revision,
`python -m pip install -r requirements.txt` inside an isolated virtualenv,
and a private, authenticated localhost RPC tunnel or HTTPS RPC endpoint.

```bash
cd ~/sse-research
source .venv/bin/activate

# Runs once, prompts for the encryption passphrase twice.
python tools/sse_vm_role_setup.py init --roles provider,monitor,observer

# Shows only public addresses and local status.
python tools/sse_vm_role_setup.py status
```

If the VM already has role wallets, **do not run init again**; run `status`.
**Node identity:** the portal was observed assigning the exact same Linux\nhostname to two DIFFERENT VMs. A hostname is not a unique machine ID. New\n\`init\` runs generate a cryptographically random, stable \`sse-...\` node ID and\nstore a restricted local binding to the machine-id fingerprint. Both the\nportal hostname and the node ID are retained separately. No VM hostname\nchanges occur. The original Consumer+Monitor VM's pre-R7 manifest still has\na hostname-based legacy ID; it remains valid and should not be regenerated.\nThe machine-id binding is a copy-detection check, **not** hardware attestation;\ncloned machine IDs or shared operator control remain research limitations.

After deploying the actual contracts, set trusted public addresses:

```bash
source .local/live-chain/contracts.env
RPC_URL=http://127.0.0.1:8545

# Read-only proof of the required chain, balances and monitor registration.
python tools/sse_vm_role_setup.py status \
  --rpc-url "$RPC_URL" --chain-id 31337 --pool "$COMMITTEE"

# LAB ONLY: plan funding from well-known public Anvil dev funds.
python tools/sse_vm_role_setup.py lab-fund \
  --rpc-url "$RPC_URL" --chain-id 31337

# LAB ONLY: explicitly approve development funding.
python tools/sse_vm_role_setup.py lab-fund \
  --rpc-url "$RPC_URL" --chain-id 31337 --execute

# Preview on-chain registration without a passphrase or transaction.
python tools/sse_vm_role_setup.py register-monitor \
  --rpc-url "$RPC_URL" --chain-id 31337 \
  --board "$BOARD" --settlement "$SETTLEMENT" --pool "$COMMITTEE" \
  --bond-wei 1000000000

# Explicitly approve bond and gas cost, prompt for local passphrase and sign.
python tools/sse_vm_role_setup.py register-monitor \
  --rpc-url "$RPC_URL" --chain-id 31337 \
  --board "$BOARD" --settlement "$SETTLEMENT" --pool "$COMMITTEE" \
  --bond-wei 1000000000 --max-total-wei 10000000000000000 --execute
```

The `contracts.env` file above exists on the **first** participant VM, not
automatically on future VMs. Future onboarding must receive a trusted
deployment manifest through the secure enrollment channel. Do not fabricate
contract addresses or copy a random file from an untrusted VM.

The funding operation is **not** for Sepolia, public networks, or production.
Use a separately authorized faucet/treasury workflow there. Never expose the
Anvil `eth_sendTransaction` endpoint to untrusted clients. After funding,
the regular role-owned client signs transactions using each VM's private key.

## Security and known gaps

- Keys are created on their owning VM and never committed to Git or copied
  between machines. Save an encrypted backup securely; a forgotten passphrase
  prevents recovery. Keep the wallet directory owner-only.
- The tool does not turn a bonded candidate into an actual independently
  operating monitoring service. It does not run probes, publish evidence,
  confirm elections or start provider Docker workloads.
- A VM with both consumer and monitor roles **must not monitor its own leases**.
  The current contract cannot identify shared operators behind distinct
  Ethereum wallets. The local conflict policy remains a required safeguard;
  independent monitor operator attestation is still research work.
- A committee requires 4 confirmed eligible monitors. For a real provider
  lease involving this first consumer VM, plan at least 5 independent monitors
  on **other VMs**, with an additional standby preferable.
- Pinned signed release distribution, one-command VM joins, credentialed
  enrollment broker, authenticated networking, update/rollback, and lifecycle
  systemd services remain separate pending infrastructure tasks.

## Tests

```bash
python -m unittest discover -s tests -p 'test_sse_vm_role_setup.py' -v
```

Tests use a fake RPC. They do not send real transactions. A real Ubuntu
operator must separately run the commands above to claim successful
on-machine end-to-end acceptance.

Branch: `research/r7-vm-role-operator-no-ci` (not deployed automatically).


## R7.1: distribute an approved release without a GitHub key on every VM

`tools/sse_lab_release_handoff.py` is an **opt-in, private-subnet SSH**
lab handoff from the previously approved SSE checkout on VM 4693 to a NEW VM.
It sends a shallow Git clone and checks the complete approved Git SHA on the
receiver. The receiver gets a verified source checkout at `~/sse-research`
and Python virtualenv at `~/sse-research/.venv`; the receiver never needs a
private GitHub deploy key.

**Trust model and limitations:** A known SSH server host key and an operator
administration SSH identity must be approved **before** `--apply`. The
receiving VM must have Python 3.12, `python3-venv`, Git and HTTPS access to
install pinned pip dependencies. This does not install Docker, Anvil, create
Ethereum wallets, enroll Tailscale, authenticate chain RPC, or start provider
workloads. The relay is authenticated point-to-point transport, **not** a
publicly signed immutable release. It is not safe for untrusted VM operators
or public chain deployments; a trusted artifact-signing authority and portal
cloud-init/one-time credential injection remain future requirements.

From the **controller VM**
`patch-dil-template-s2-service-base-g68-20260628-044954`, with an approved
R7 checkout at `$HOME/sse-r7-onboarding`, an existing owner-only SSH
provisioning key and the NEW VM's verified host key in `known_hosts`:

```bash
cd "$HOME/sse-r7-onboarding"
APPROVED_REVISION="$(git rev-parse HEAD)"

# DRY RUN: verify approved source and package it; no network connection.
"$HOME/sse-research/.venv/bin/python" tools/sse_lab_release_handoff.py \
  --source . --revision "$APPROVED_REVISION" \
  --dest-ip "<NEW_VM_PRIVATE_IP>" \
  --dest-user "<NEW_VM_PORTAL_USERNAME>" \
  --ssh-key "$HOME/.ssh/sse_vm_provision_ed25519" \
  --roles provider

# Explicit remote install ONLY after SSH identity is separately verified:
"$HOME/sse-research/.venv/bin/python" tools/sse_lab_release_handoff.py \
  --source . --revision "$APPROVED_REVISION" \
  --dest-ip "<NEW_VM_PRIVATE_IP>" \
  --dest-user "<NEW_VM_PORTAL_USERNAME>" \
  --ssh-key "$HOME/.ssh/sse_vm_provision_ed25519" \
  --roles provider --apply
```

The placeholders are not runnable until the new VM exists; do not infer
IP or username from its hostname. The CLI rejects non-private destination
IPs, duplicate/invalid roles, wrong source revision, and insecure SSH private
key permissions; it requires strict host-key checking (no TOFU bypass).
The receiver refuses existing destination checkouts and tampered or
path-traversing archives. The transport uses SSH stdin, not an open HTTP
file server or public remote shell.

Afterward, on the **recipient VM**:

```bash
cd ~/sse-research
source .venv/bin/activate
python tools/sse_vm_role_setup.py init --roles provider
```

The operator still must set up an approved private RPC route and configure
role-owned runtime services. SSH authorization can be delivered through
the infrastructure portal's cloud-init/SSH-key capabilities if available,
but **do not claim this is already automated**.

Offline tests for the handoff:

```bash
python -m unittest discover -s tests -p 'test_sse_lab_release_handoff.py' -v
```
