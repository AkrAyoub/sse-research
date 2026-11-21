# R145 — Fresh Ubuntu VM source bootstrap: ONE repo, safe role selection

**Latest verified predecessor:** VM4707 ran R144 at
`6da0c668a23fdfec5d006a6da206dac0ce066cca`: **974 Python tests,
OK (3 skipped)**. R145 is **new GitHub code awaiting owner-VM regression**.
Nothing here installs or restarts Besu/Lighthouse, adds a PoS validator,
joins an overlay, deploys a contract or submits a transaction.

The canonical source remains the SINGLE `AkrAyoub/sse-research`
repository. Its `tools/sse_join.py` is the interactive/multi-role
selection entry point. `scripts/sse_fresh_vm_source_bootstrap.sh`
handles the independent **source-acquisition step** for a new Linux VM.

## Exactly what is and is not automatic

The source bootstrap checks a clean Linux x86-64 host, strictly prohibits
existing VM4706 owner signer/R59 observer states, takes an operator-specific
**read-only** GitHub deploy key and exact reviewed 40-character commit, then
with **explicit local authorization** installs only basic git/Python/SSH
packages when absent, clones the SINGLE private repository, verifies the
commit belongs to the development branch and runs `sse_join.py --plan`
with the selected roles. `--plan` neither writes nor connects.

This is NOT zero-touch blockchain installation. Docker, pinned images,
ZeroTier ad-hoc overlay, original chain public archive, live peer
directories and application service activation still need actual
integration/verification. The private GitHub repository cannot be a
permanent dependency for permissionless joining. Publish trusted public
source/genesis release mirrors and verified build artifacts before
outside-operator acceptance.

## The unavoidable read-only GitHub authorization step (development only)

On each brand-new VM, separately generate a **unique non-signing
SSH read-only deploy key**, for example:

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/sse_repo_readonly" -N '' \
  -C "sse-independent-readonly-source"
chmod 600 "$HOME/.ssh/sse_repo_readonly"
ssh-keygen -lf "$HOME/.ssh/sse_repo_readonly.pub"
cat "$HOME/.ssh/sse_repo_readonly.pub"
```

Only that **public key** should be added under the repository's
GitHub Settings → Deploy keys → Add deploy key, with
**Allow write access NOT selected**. Never share the private key,
wallet, JWT, keystore, mnemonic or cloud credentials.
Ensure `github.com` is independently authenticated in the
host's SSH `known_hosts`; `StrictHostKeyChecking=yes`
deliberately refuses unknown hosts. Do not blindly trust
`ssh-keyscan` output without separately verifying GitHub's
published SSH host-key fingerprint.

At the moment, there is NO general public release path for arbitrary
outsiders. A fresh VM with no deploy key will fail safely instead of
implicitly gaining GitHub access.

## One-time source-bootstrap script

After obtaining this reviewed script from the repository through a
trusted channel, run an isolated **read-only plan** first:

```bash
bash scripts/sse_fresh_vm_source_bootstrap.sh --plan \
  --ssh-key "$HOME/.ssh/sse_repo_readonly" \
  --commit <EXACT_REVIEWED_R145_SHA> \
  --node-id large-new-a --roles full_node
```

Use `--apply` in place of `--plan` only on the fresh VM after
reviewing output. The script prompts
`BOOTSTRAP-SSE-SOURCE` and fetches the exact pinned checkout,
then calls the unified role planner. Source-bootstrap `--apply`
is a real file/package operation, not a blockchain transaction.
Do not attempt it on VM4706 or VM4707.

Because the initial Ubuntu VM starts with **NO repository**,
the bootstrap script itself must first be obtained through a
trusted source transfer or be included in a **future public signed
release image/cloud-init artifact**. Avoid circular directions
that tell an empty VM to run a path it does not possess.

## What remains for a true single-command permissionless join

1. Public checksum-pinned release bundle of GitHub source, signed
   verified genesis and exact Besu/Lighthouse images across
   independently hosted mirrors (not a private GitHub account).
2. On first boot, install OS packages and Docker/overlay or alternate
   direct public P2P transports, safely generate node-local identities,
   and configure isolated two-layer native client networking.
3. Multiple authentic, publisher-verifiable, dynamically refreshed
   EL enodes/Beacon ENRs; native peer handshake and finality evidence,
   graceful reconnect after IP/address changes, no permanent seed.
4. Clean optional validator ceremony (new BLS keys, actual funded
   deposit and activation without an operator whitelist).
5. Full provider/consumer/monitor service provisioning and real
   on-chain eligibility, actual resource capacity, private local
   wallet authorization, monitoring evidence and bounded settlement.
6. Multi-operator outside-ISP acceptance and reproducible adversarial
   scientific measurement.

No number of VMs/roles/validator IDs is fixed by the SSE architecture.
New larger VMs should join as nonsigning full nodes before validator
activation. Smaller 2-vCPU/4-GB machines are initially intended for
app-layer consumer/provider/monitor services, not automatically for
two resource-heavy blockchain clients.

## Source regression

```bash
.venv-tests/bin/python -B -m unittest discover -s tests \
  -p 'test_sse_pos_r145_fresh_vm_source_bootstrap.py' -q
.venv-tests/bin/python -B -m unittest discover -s tests
```
