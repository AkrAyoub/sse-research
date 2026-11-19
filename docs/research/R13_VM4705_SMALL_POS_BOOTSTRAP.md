# R13 — VM4705 small-host SSE own-PoS bootstrap

Date 2026-11-19. Status: **FIRST ON-VM PoS CHAIN31339 ENCLAVE RUNNING**,
execution/finality/faucet balances not yet independently checked.
**First run emitted mnemonic and prefunded private keys: tainted smoke-only genesis.**

Fresh VM4705: Ubuntu 24.04.4, 4 vCPU, 11 GiB memory, 93GB free
storage, Docker 29.1.3. GitHub checkout and Kurtosis 1.23.0 now installed,\nwith reviewed Docker-group access and first running PoS enclave.
Destroyed VM4704's private keys and faucet are intentionally discarded.
DO NOT reuse the old faucet address or old genesis mnemonic.

The PRIVATE source repository is AkrAyoub/sse-research. Its branch is
integration/r7-wp09q-wan-multivm-no-actions. Install a *read-only*
deploy key unique to VM4705. Never move or post private SSH keys.

## 1. Bootstrap new host

    sudo apt-get update
    sudo apt-get install -y git python3-venv python3-pip curl ca-certificates jq
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -a 100 -N "" \
      -f "$HOME/.ssh/sse_pos_vm4705_readonly" \
      -C "sse-pos-vm4705-readonly"
    cat "$HOME/.ssh/sse_pos_vm4705_readonly.pub"

Add only this public key to the GitHub repository Settings > Deploy Keys,
without Allow write access. Authenticate github.com's host key with
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
before accepting it in SSH known_hosts.

    GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_pos_vm4705_readonly -o IdentitiesOnly=yes" \
      git clone git@github.com:AkrAyoub/sse-research.git "$HOME/sse-pos"
    cd "$HOME/sse-pos"
    git fetch origin integration/r7-wp09q-wan-multivm-no-actions
    git switch --detach APPROVED_R13_SHA

    python3 -m venv .venv-pos
    source .venv-pos/bin/activate
    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -p 'test_sse_pos_*.py' -v
    python -m pip freeze > "$HOME/sse-pos-dependencies-4705.txt"

## 2. Docker and Kurtosis operator permissions

Kurtosis requires Docker access for the nonroot operator. Docker group
membership on a dedicated disposable research VM is a pragmatic
option, but **grants root-equivalent power** on that VM. Do not do
this on shared or untrusted hosts. If approved:

    sudo usermod -aG docker "$USER"
    # LOG OUT and LOG BACK IN to activate group membership.
    docker info --format '{{.ServerVersion}}'

Official Kurtosis installation documentation:
https://docs.kurtosis.com/install/
The current Ubuntu instructions use an apt repository with trusted=yes;
review that trust tradeoff, and record the installed Kurtosis version
and binary hash before publication.

    kurtosis version
    docker info --format '{{.ServerVersion}}'

## 3. Fresh wallet and genesis

Our source generator now defaults to ONE Besu execution client,
ONE Lighthouse Beacon client and ONE validator client carrying 32
genesis validator keys. The network is our own Ethereum-compatible
PoS chain ID31339, with worthless test ETH only. This is a smoke
configuration, not the network's permanent participant limit.

    cd "$HOME/sse-pos"
    source .venv-pos/bin/activate
    mkdir -m 700 "$HOME/sse-pos-wallets"
    python tools/sse_pos_test_wallet.py \
      --role faucet --output-dir "$HOME/sse-pos-wallets" --apply

Keep the encrypted keystore and its password private. Use the printed
NEW public faucet address below (not the destroyed VM4704 address):

    export FAUCET="0xNEW_PUBLIC_FAUCET_ADDRESS"
    mkdir -m 700 "$HOME/sse-pos-secrets"
    python tools/sse_pos_devnet_plan.py \
      --faucet-address "$FAUCET" --nodes 1 \
      --validators-per-node 32 \
      --output-dir "$HOME/sse-pos-secrets" --apply

The generator creates a new 24-word BIP39 bootstrap mnemonic locally,
but never prints it. It allocates 1,000,000 test ETH in GENESIS only.
The small-host profile explicitly defers Fulu AND its five dependent
BPO epochs, because the inspected upstream ethereum-package input
parser rejects BPO forks before Fulu. Additional Dora explorer and
public P2P publication are disabled for this first resource-limited
smoke network.

Read-only launch preflight, which verifies source and config SHA256
without showing any secret:

    python tools/sse_pos_launch_preflight.py \
      --output-dir "$HOME/sse-pos-secrets" --verify-only
    bash scripts/sse_pos_launch.sh --plan

## 4. Operator-approved live launch

Upstream package pinned by source SHA:
d3014d6d23d683362025b9e23a0d69de49e77cca
Besu image pinned to observed R10 canary registry digest.
Lighthouse v8.3.3 tag must have its resolved image digest archived
before claiming full paper reproducibility.

    bash scripts/sse_pos_launch.sh --apply
    kurtosis enclave inspect sse-pos-research01
    docker stats --no-stream

A failed Kurtosis run MUST retain its logs for diagnosis.
Never run kurtosis clean -a, never destroy historical Anvil31337,
never copy VM4704 secrets, and never claim successful finality until
actual EL and Beacon RPC output confirms it.

After startup, inspect actual EL and Beacon ports from Kurtosis and run
tools/sse_pos_devnet_health.py with those localhost URLs. Verify
chainID31339, genesis block0, advancing heights, Beacon head slots,
a genuinely finalized checkpoint, and faucet balance. Then deploy
the actual SSE contracts via script/DeploySSEPos.s.sol, capture
receipts, and use tools/sse_pos_contract_attest.py for on-chain wiring.

## Scientific scope and limitation

One host with 32 bootstrap validator keys is NOT a decentralized set
of independent operators. It is a minimal PoS client smoke experiment.
A later, separately controlled validator must generate fresh BLS keys,
sync via public EL+CL P2P without Tailscale or administrator approval,
deposit worthless test ETH on chain31339, and become active by the
Beacon protocol. Real economic Sybil resistance is impossible to
claim from unvalued, freely issued research ETH. The SSE paper's
novelty must be evaluated through actual SLA monitoring/settlement,
soundness under partial observations and scalability experiments.

Acceptance:
- New read-only private GitHub checkout and exact source SHA
- Targeted R13 unit tests and protected genesis preflight pass
- Reviewed Docker/Kurtosis access on VM4705
- Actual EL+CL startup and advancing blocks
- Actual PoS finality and funded test EOA balance
- SSE contract deployment + bid/provider/monitor/settlement evidence
- Open external validator P2P join and native staking activation

## 2026-11-19 — VM4705 real operator evidence: preserve genesis, fix parser

Observed on the NEW VM4705:
- Read-only GitHub SSH deploy key created and private repo cloned;
  R13 exact checkout `67405e2ee36be27e91bfd77fcbc2e33935830bbf`.
- Owner-only encrypted faucet wallet created once:
  `0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7`.
- Owner-only R13 PoS genesis and new private BIP39 bootstrap mnemonic
  generated once. Initial configuration SHA256:
  `b2f97ce79e0e248865ef029ae2c8c8be870e717bd9d5304fef92f02d8638a280`.
- 25 targeted PoS tests run: 23 pass, 1 FAIL, 1 ERROR.
  The ERROR was a source-only preflight YAML syntax mismatch:
  `tools/sse_pos_launch_preflight.py` expected indented
  `    el_type: besu` rather than the correct YAML list entry
  `  - el_type: besu`.
  The FAIL was a test matching `kurtosis clean -a` inside an
  explanatory COMMENT, not a shell command.
- The operator ran `sudo usermod -aG docker "$USER"` but the existing
  SSH login still lacked Docker socket access. Log out and in, then
  verify `id -nG` and nonroot `docker info`; the Docker group is
  root-equivalent and not an SSE consensus authorization.
- No Kurtosis installation or PoS launch was observed. Calls to
  `sse_pos_launch.sh --plan` and `--apply` both correctly failed
  closed before any enclave was created.

**Correction in later GitHub source:**
1. Preflight recognizes the actual YAML list dash.
2. Test ignores COMMENT-only prohibited command mentions while
   continuing to forbid actual executable destructive commands.
3. New preflight explicitly recognizes the previously reviewed
   `67405e2...` R13 source manifest as a valid genesis origin
   across later clean GitHub source revisions. Every invariant and
   original SHA256 remain checked; a new wallet/mnemonic is NOT
   required. This is the **only** old generator revision permitted.
4. Targeted test demonstrates preservation of prior genesis source
   SHA while reporting the new verifier checkout separately.

Next: GitHub checkout of the approved correction SHA, run 25+
targeted tests, verify `sse_pos_launch_preflight.py --verify-only`
against the ORIGINAL unchanged `$HOME/sse-pos-secrets`; do NOT run
faucet/genesis creation again. Then resolve Docker group session
and install reviewed Kurtosis. Only then consider `--apply`.

**Acceptance remains:** real advancing EL/CL block height and finality,
genesis 1M worthless test ETH balance, deployed SSE EVM contracts,
actual SLA settlement, and later separate-host external PoS validator
deposit+activation. The initial one-host network is not decentralized.

## 2026-11-19 — FIRST REAL CHAIN31339 BOOT (verified operator log)

The **actual** VM4705 Kurtosis transcript now proves new chain
31339 reached RUNNING with these distinct services:
`el-1-besu-lighthouse` (Besu 26.11.1),
`cl-1-lighthouse-besu` (Lighthouse v8.3.3),
`vc-1-besu-lighthouse` (validator client),
and a one-off key-generation service.
Besu reported Ethereum protocol genesis, execution chainID31339,
and all 32 Electra-genesis validators. Real EL genesis block0 hash:

`0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5`

Real Beacon genesis validators root:

`0x016a9bddcf3e7fcd561895d5b75ab461ad6f75f0c5f8b5d74e9556b6df8cb425`

Public faucet address selected by owner:

`0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7`

Observed first-run **local** endpoints (Kurtosis dynamically maps
ports; verify these against `kurtosis enclave inspect` after restart):
EL RPC `http://127.0.0.1:32770`,
Beacon API `http://127.0.0.1:32774`.
3 core services were RUNNING at inspection. Actual chain height,
finality and funded test-ETH balance had NOT yet been measured by the
operator log. Use read-only commands:

```bash
python tools/sse_pos_devnet_health.py \
  --execution-url http://127.0.0.1:32770 \
  --beacon-url http://127.0.0.1:32774 \
  --expected-genesis 0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5 \
  --require-finality
curl -fsS http://127.0.0.1:32770 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7","latest"],"id":1}' \
  | python -c 'import json,sys; x=json.load(sys.stdin); print("Faucet test ETH:",int(x["result"],16)/10**18)'
```

### CRITICAL key exposure discovered in first live log

**The upstream pinned ethereum-package Starlark run printed a 24-word
bootstrap consensus mnemonic and numerous premine EOA private keys to
its ordinary CLI transcript, including a JSON object with all private
keys.** Do NOT duplicate these secrets in research notes, GitHub,
terminal excerpts, issues, chat or public release bundles. The
previously shared transcript exposed the bootstrap mnemonic. This
ONE-HOST current enclave is therefore **TAINTED for public admission**:
use only as an isolated, disposable smoke chain, with no externally
exposed validator admission or valuable assets. A future public
experiment MUST replace all exposed genesis bootstrap keys with
fresh independently generated secrets and a new genesis; it MUST NOT
claim independent operator decentralization merely because 32
validators share one machine. The operator's separately encrypted
faucet wallet password and private EOA are NOT shown as leaked in
this output, but its public address is known.

The upstream Kurtosis service metadata showed Besu and Lighthouse
discovery TCP endpoints bound to `0.0.0.0` on ephemeral VM4705 host
ports, **despite this R13 configuration disabling intentional P2P
publication**. Do not assume these binds are safe. Keep them blocked
by host/cloud firewall and do not provide Internet access for the
current exposed-key smoke network. DO NOT change SSH security groups
blindly or enable UFW without confirming SSH reachability.

**GitHub launcher source corrected for FUTURE RUNS**: raw upstream
`kurtosis run` stdout+stderr goes to a restricted, owner-only
`sse-pos-runlogs` directory with umask077 and unique mode0600 files.
The terminal instead displays safe stage markers and a warning that
the raw output contains secrets. This is a containment mitigation;
the upstream package may still log secrets inside Kurtosis. Treat
enclave outputs as sensitive. The already running enclave is
unmodified by source updates. Never rerun `--apply` into an
existing enclave and never print the raw private log.

### Next acceptance

1. Prove advancing EL height and finalized Beacon epoch/root, and
   real on-chain faucet funding. Save only non-secret evidence.
2. Install Foundry on the VM or use a verified secure SSH tunnel from
   the existing Foundry workstation; deploy the current SSE contracts
   through locally authenticated encrypted faucet EOA and chain31339.
3. Run real consumer-provider-monitor escrow and settlement receipts,
   collect gas costs/latencies/signed service artifacts.
4. Prepare clean independent, multi-host PoS validator joining on a
   NEW research genesis with no printed/distributed bootstrap keys,
   proof of remote networking and 32-test-ETH on-chain activation.
