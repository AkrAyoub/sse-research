# R14 — first real SSE chain31339 evidence + test-ETH contract deployment

Date: 2026-11-19. Source commit: check the newest verified branch head.
Observed VM4705 Kurtosis created **the first real, independent Ethereum-PoS
SSE chain31339** (zero real ETH). The genesis includes 32 BLS validator
records and Besu+Lighthouse EL/CL/VC processes. The initial network's
validators all run under one VM and it has not yet demonstrated external,
independent validator activation. This is a *single-host smoke network*,
not proof of open operational P2P membership.

## STOP: first launch output leaked bootstrap credentials

Pinned upstream ethereum-package prints genesis validator mnemonic and
privately derived EOA keys in its ordinary CLI output. The user's
already shared transcript therefore exposed these credentials. Keep
this actual chain strictly local and disposable; do **NOT** allow
public validators/valuable assets or open public peer ports on it.
A clean public validator experiment requires NEW, NON-LEAKED genesis
keys and separately operated machines. The actual output also maps
EL and CL P2P TCP endpoints to 0.0.0.0 despite explicit public
port_publisher being disabled; verify the cloud firewall blocks
incoming traffic to those ports while keeping SSH intact. Do not
assume Docker host bindings are safe public exposure.

Source launcher now uses umask077, an owner-only private runlog folder
and a unique mode0600 file, rather than streaming Kurtosis secrets
to terminal. Do not upload the raw runlog; this mitigation does not
remove sensitive information from Kurtosis internal service metadata.

## Observed first-run identifiers and ports (pin in evidence)

ChainID: 31339
Execution genesis block0:
0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5
Consensus genesis validators root:
0x016a9bddcf3e7fcd561895d5b75ab461ad6f75f0c5f8b5d74e9556b6df8cb425
Faucet public EOA:
0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7
EL JSON-RPC on VM4705: http://127.0.0.1:32770
Beacon API on VM4705: http://127.0.0.1:32774
Ports are runtime bindings and may change if Kurtosis services restart.
Confirm them with kurtosis enclave inspect sse-pos-research01.

## 1 — Confirm ACTUAL PoS blocks/finality (NOT only running Docker)

On VM4705 at the current pinned source checkout:

    cd ~/sse-pos
    source .venv-pos/bin/activate

    python tools/sse_pos_devnet_health.py \
      --execution-url http://127.0.0.1:32770 \
      --beacon-url http://127.0.0.1:32774 \
      --expected-genesis 0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5 \
      --require-finality

If finality fails due to young network, retry without
--require-finality, and do NOT claim finality before a later
successful real Beacon checkpoint result.

Check faucet balance through safe public-EOA RPC; NEVER display raw
private keys:

    curl -fsS http://127.0.0.1:32770 \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7","latest"],"id":1}' \
      | python -c 'import json,sys; j=json.load(sys.stdin); print("Faucet test ETH:",int(j["result"],16)/10**18)'

Expected *before any spending*: 1,000,000 TEST ETH. Observed RPC
balance is required; a YAML allocation alone does not prove it.

## 2 — Reproducible Foundry dependency (GitHub-first)

Previously, tests and script imported forge-std but the repo had
NO lib/forge-std tracked. R14 added an immutable submodule:

    lib/forge-std -> foundry-rs/forge-std
    Git SHA: f3dae6e6ee381f25eb6a246f7da9b85c91a68219
    Official release: v1.17.0

Update GitHub source to the approved new R14 commit, then:

    cd ~/sse-pos
    git submodule update --init --recursive
    git submodule status

This is read-only, GitHub-pinned dependency acquisition; do NOT run
forge install or manually patch Solidity files outside GitHub.

Install a verified official Foundry release on the new Ubuntu VM.
Official workflow: https://book.getfoundry.sh/getting-started/installation
Inspect the installer before running it; do NOT paste output
containing private keys. Example:

    curl -fsSL https://foundry.paradigm.xyz -o /tmp/sse-foundryup-install.sh
    less /tmp/sse-foundryup-install.sh
    bash /tmp/sse-foundryup-install.sh
    export PATH="$HOME/.foundry/bin:$PATH"
    foundryup
    forge --version
    cast --version

Record the actual Foundry build version and solc0.8.24.

    forge build
    forge test

Full gates must pass in this new clone before deploying
the SSE contracts. Check no contract exceeds EIP170 24576B.
No real mainnet or testnet ETH is required.

## 3 — Real SSE contract deployment to own chain31339 (after checks)

Keep only the encrypted faucet keystore. Never pass a raw private key
as a CLI argument or environment variable. Forge prompts for the
keystore password interactively; the password must stay private.
Use the actual current VM local RPC, not Anvil31337 or QBFT31338.

    export SSE_EL_RPC="http://127.0.0.1:32770"
    export SSE_FAUCET="0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7"
    cast chain-id --rpc-url "$SSE_EL_RPC"
    cast balance "$SSE_FAUCET" --ether --rpc-url "$SSE_EL_RPC"

First dry-run simulation without --broadcast:

    export SSE_MIN_MONITOR_BOND_WEI=1000000000000000
    export SSE_USE_GLOBAL_MERKLE=false
    forge script script/DeploySSEPos.s.sol:DeploySSEPos \
      --rpc-url "$SSE_EL_RPC" \
      --keystore "$HOME/sse-pos-wallets/faucet.keystore.json" \
      --sender "$SSE_FAUCET"

After the dry run succeeds, **explicitly authorize broadcasts**
on chain31339 only:

    forge script script/DeploySSEPos.s.sol:DeploySSEPos \
      --rpc-url "$SSE_EL_RPC" \
      --keystore "$HOME/sse-pos-wallets/faucet.keystore.json" \
      --sender "$SSE_FAUCET" --broadcast --slow

This will spend only the valueless TEST ETH allocated in our
independent genesis. Contracts to deploy and link:
OpenMonitorCommittee, SSESettlement, OpenResourceBoard. The deployer
cannot select monitors by arbitrary admin-fed randomness after delayed
block-entropy is enabled; such entropy remains proposer-biasable and
NOT an unbiased VRF. Do not claim live protocol security from this
single-host smoke run.

Store TX receipts and deployed addresses, then independently verify
the actual code and bindings:

    python tools/sse_pos_contract_attest.py \
      --rpc-url "$SSE_EL_RPC" \
      --committee 0xACTUAL_DEPLOYED_COMMITTEE \
      --settlement 0xACTUAL_DEPLOYED_SETTLEMENT \
      --board 0xACTUAL_DEPLOYED_BOARD \
      --source-commit "$(git rev-parse HEAD)"

This check does not itself verify Solidity source-to-bytecode equality
or physically correct SLA evidence; it does verify actual deployed
bytecode presence, positive monitor bond, delayed-block entropy
and mutual contract addresses.

## 4 — Remaining scientific acceptance

1. Observed PoS finality and funded wallet balance.
2. Three on-chain SSE contracts linked and receipts saved.
3. Multiple independent wallets: consumer, provider and selected
   bonded monitors, actual off-chain service receipt and settlement.
4. Separate reproducible 0/1/2 monitor Byzantine/outage and
   validator fault/partition experimental arms.
5. New SAFE public research genesis with independently held
   validator mnemonic/keys and non-discretionary faucet; independently
   provisioned machines sync via public EL+CL P2P without Tailscale.
6. At least one new validator deposits 32 TEST ETH and gets
   activated by Beacon consensus without administrator approval.
7. Measurements, baselines, and research manuscript reflecting
   observed safety/liveness/gas/settlement costs.

The first single-host smoke chain is **not** a permissioned QBFT
deployment, but it is also not yet an observed geographically
decentralized, fully open operational network.
