# R6 First-Boot Ubuntu Bootstrap (lab, version 0)

**Status:** experimentally implemented first-boot installer; **not automatic
on-chain role enrollment**. This adds a useful R6 integration path while
keeping the research-only R5 agent and R2/3/4 contracts unchanged.

## What it does

Given an **externally approved 40-character Git commit SHA**, explicit
application roles, RPC URL, chain ID and SSESettlement address, the installer:

1. Defaults to a **dry-run**, printing the intended changes.
2. On explicit `--apply` (Ubuntu + root only) clones the SSE GitHub repository
   over HTTPS, fetches the exact approved commit, checks out detached HEAD,
   and verifies the resulting revision matches the supplied SHA.
3. Creates a separate Python virtual environment under the same revision,
   installs pinned `pycryptodome==3.23.0`, and runs
   `tools/sse_vm_join_preflight.py` against the specified chain and contract.
4. Creates the restricted `sseagent` system user if missing, then starts a
   **read-only local heartbeat** as that unprivileged identity. Existing users
   with unsafe permissions/shells are rejected.
5. Does **not** read/generate private keys, send transactions, provision
   compute capacity, expose network ports, join the Ethereum validator set,
   register/bond monitors, or interpret evidence as contractual truth.

The Git SHA must come from an independently approved release record.
A pin by itself does NOT authenticate the original publisher, secure
dependencies, or establish blockchain consensus. An external HTTPS RPC
can lie about chain state; domain matching is not independent finality.

## Ubuntu VM prerequisite (explicit operator-approved changes)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates git curl python3 python3-venv
```

The installer creates its dedicated locked-down `sseagent` account
only on the explicit `--apply` path, if it does not already exist.

For a new VM, deliver the following installer **from the SAME trusted pinned
commit** using a trusted provisioning channel (for example, cloud-init or an
operator-managed HTTPS download). Do not fetch moving `main`:

```bash
APPROVED_SHA="<FULL_40_CHARACTER_APPROVED_COMMIT>"
curl --fail --show-error --silent --location \
  "https://raw.githubusercontent.com/AkrAyoub/sse-research/${APPROVED_SHA}/tools/sse_vm_bootstrap.py" \
  --output /tmp/sse_vm_bootstrap.py
```

Use your real **deployed** SSESettlement contract address. The existing
Anvil contract address will not automatically work on Sepolia.

```bash
# First plan, with NO changes. Replace placeholders with actual values.
python3 /tmp/sse_vm_bootstrap.py \
  --revision "$APPROVED_SHA" \
  --node-id provider-vm-01 \
  --roles provider \
  --rpc-url "https://YOUR_PUBLIC_TESTNET_RPC_WITHOUT_CREDENTIALS" \
  --chain-id 11155111 \
  --settlement "0xYOUR_DEPLOYED_SSE_SETTLEMENT_ADDRESS"

# Explicit local installation, only after reviewing plan and network values.
sudo python3 /tmp/sse_vm_bootstrap.py \
  --revision "$APPROVED_SHA" \
  --node-id provider-vm-01 \
  --roles provider \
  --rpc-url "https://YOUR_PUBLIC_TESTNET_RPC_WITHOUT_CREDENTIALS" \
  --chain-id 11155111 \
  --settlement "0xYOUR_DEPLOYED_SSE_SETTLEMENT_ADDRESS" \
  --apply

sudo systemctl status sse-vm-role-agent.service
curl --fail http://127.0.0.1:8765/v1/status
```

Choose `--roles monitor` or another explicit combination for the second VM.
The status endpoint's `roles` field means **configured roles**, NOT active
permissionless registration. Each VM must eventually have separate operator
keys and permissions; a monitoring role is not eligible until it has
successfully registered and posted its bond on chain.

The installer refuses to overwrite an existing systemd unit automatically
and does not support silent upgrades. Existing release directories are reused
only if their HEAD matches the trusted pin. On failure it can leave a
downloaded release/runtime but will not install the service unless the
chain preflight passes.

**Security limitation:** this is a research bootstrap, not a hardened
software supply-chain updater. Dependencies must eventually use signed,
hash-locked artifacts and release provenance; remote RPC must be authenticated
and independently corroborated for high-stakes use.

## Acceptance and next steps

Offline:
```bash
python -m unittest discover -s tests -p 'test_sse_vm_bootstrap.py' -v
python -m unittest discover -s tests -q
```

Remote two-VM acceptance requires operator-provided Ubuntu VMs, correct
approved commit, RPC access, deployed settlement addresses and independent
wallets. No real ETH required: target Anvil first, public testnet with native
test ETH later. Before marking R5/R6 exit criteria accepted, implement
secure key custody, registration/confirmation and agent-driven transactions,
end-to-end provider reachability, NAT/tunnel/TLS discovery, evidence
qualification and fault experiments.
