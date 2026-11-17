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
The node ID is the full existing Ubuntu hostname; no hostname changes occur.

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
