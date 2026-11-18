# SSE's OWN Ethereum proof-of-stake blockchain — chain 31339

**2026-11-18 architecture correction. NO REAL ETH, NO PUBLIC TESTNET,
NO ADMIN-APPROVED VALIDATORS.** All code changes in GitHub.
STATUS: source completed for smoke test, NOT yet deployed or proven.

## Decision

We abandon deployment of our experimental Besu QBFT 31338 chain:
fixed QBFT validator-set voting is permissioned. It was not acceptable
for SSE's required open consensus. Keep R9/R11 sources as *historical
comparison artifacts*, not as the SSE launch procedure. VM4704 already
has a local experimental key; DO NOT delete, copy or repurpose it
as an Ethereum PoS BLS validator key. VM4695 / Anvil31337 stays intact.

New network:
- Our OWN custom, independent Ethereum-compatible execution+consensus
  network, chain ID **31339**, genesis-created **worthless test ETH**.
- Ethereum PoS validator deposit/activation, attestations, slots, finality,
  validator rewards, withdrawals/slashing supplied by an established
  CL+EL protocol, not ad-hoc miners whose reward logic is faked in app.
- Two provisional Besu execution clients + Lighthouse beacon/validator
  clients, with 32 bootstrap validators each (64 keys for the first
  smoke test). Not a permanent membership cap: later validators need
  their OWN independently generated BLS keys, a 32-unit **test ETH**
  deposit in our own network, activated via Beacon consensus rules.
- New chain is separate from mainnet, Hoodi, Sepolia and QBFT31338.
  **ZERO real ETH.** Faucet's EOA gets 1,000,000 *test ETH* in genesis,
  then can send test ETH for gas, deposits, provider bonds and escrow.
  Faucet distribution and public trustless onboarding/anti-Sybil still
  require acceptance work; fund requests should be automated, not owner
  vetoes. An initial bootstrap mnemonic owned by an operator is NOT
  physical independence or equivalent to a decentralized production
  genesis, and cannot prove credible Sybil resistance with worthless
  tokens.
- No user must join or switch the owner's Tailscale account. After
  controlled smoke, public P2P requires NAT/firewall, public bootstrap
  peers, EL+CL discovery, external remote join and a permissionless
  faucet test. **Default smoke config has public P2P DISABLED** and
  cannot be honestly advertised as externally permissionless yet.

## Verify compatibility before starting

Upstream deployment environment is the official
[ethPandaOps ethereum-package](https://github.com/ethpandaops/ethereum-package),
source pinned **d3014d6d23d683362025b9e23a0d69de49e77cca**.
A Kurtosis CLI (upstream states >=1.23), Git and Docker are required.
The script clones/verifies the exact upstream Git revision before
Kurtosis is allowed to start containers. Image choices:
- Besu 26.11.1 with immutable digest observed in our earlier R10
  successful native Besu canary:
  \`hyperledger/besu:26.11.1@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d\`.
- Lighthouse v8.3.3 security release, 2026-11-09, current tag
  \`sigp/lighthouse:v8.3.3\`. **Record/lock Lighthouse's actual
  registry digest before scientific runs; this tag alone is mutable.**
  Do not assume the latest upstream package's defaults are safe.

VM4704 was reported as ~2 vCPU/3.8GiB RAM. It is **not verified**
large enough for TWO full Besu+Lighthouse stacks plus Kurtosis. First
smoke should use a dedicated, more capacious experimental Ubuntu host
(prefer at least 8 vCPU/16GiB RAM and sufficient SSD for two pairs;
measure actual consumption). Never turn VM4695 into a PoS host or
grant unsupervised root-level Docker access.

## Execution sequence — NOT dependent on actual ETH

### Step 1 — fresh TEST EOA wallet, encrypted locally

On the deployment host, from the exact approved SSE GitHub checkout
and the project's isolated Python venv with eth-account:

\`\`\`bash
mkdir -m 700 "$HOME/sse-pos-wallets"
python tools/sse_pos_test_wallet.py \
  --role faucet --output-dir "$HOME/sse-pos-wallets" --apply
\`\`\`

The script prompts for a 16+ character password and writes a new
EIP-2335? **No: Web3 Secret Storage v3** encrypted EOA keystore (not
a validator BLS key), owner mode0600. It prints the public address.
Never put password/private key into shell history or GitHub.

### Step 2 — create private network params and genesis funding

Copy the printed public faucet address into \`FAUCET\`. The command
does NOT spend real ETH or generate a fake chain ID on Ethereum mainnet.

\`\`\`bash
export FAUCET="0xYOUR_PUBLIC_FAUCET_ADDRESS"
mkdir -m 700 "$HOME/sse-pos-secrets"
python tools/sse_pos_devnet_plan.py \
  --faucet-address "$FAUCET" \
  --output-dir "$HOME/sse-pos-secrets"
python tools/sse_pos_devnet_plan.py \
  --faucet-address "$FAUCET" \
  --output-dir "$HOME/sse-pos-secrets" --apply
\`\`\`

The private network_params.yaml includes a fresh 24-word secret
mnemonic for provisional genesis validators and the custom
\`prefunded_accounts\` allocation **without any real ETH**.
It must NEVER be committed/uploaded, cloned across public devices,
or reused after publishing research results.

### Step 3 — launch isolated devnet (only on a reviewed Docker host)

Install a reviewed official Kurtosis >=1.23 CLI, verify Docker access
for a dedicated operator, and run:

\`\`\`bash
bash scripts/sse_pos_launch.sh --plan
bash scripts/sse_pos_launch.sh --apply
kurtosis enclave inspect sse-pos-research01
\`\`\`

\`--plan\` does not clone or launch. \`--apply\` pulls actual
execution/consensus images, creates an isolated Kurtosis enclave,
starts the services, and does not execute \`kurtosis clean -a\`.
It refuses to overwrite an existing named enclave or checkout.

### Step 4 — observe REAL EL+Beacon blocks and PoS finality

Read the mapped loopback EL RPC and beacon HTTP ports from Kurtosis
output. Set these to the ACTUAL values (they are dynamically mapped,
not assumed to be 8545/5052). Example placeholders:

\`\`\`bash
export SSE_EL_RPC=http://127.0.0.1:ACTUAL_EL_PORT
export SSE_BEACON_API=http://127.0.0.1:ACTUAL_BEACON_PORT

python tools/sse_pos_devnet_health.py \
  --execution-url "$SSE_EL_RPC" \
  --beacon-url "$SSE_BEACON_API" \
  --require-finality
\`\`\`

Expected: chain ID 31339, real nonzero block0, positive execution
height, Beacon head slot, real finalized epoch/root. First observe
without \`--require-finality\` if the chain is too young; do not
claim finality until the Beacon API reports it. Record actual genesis
hash and require \`--expected-genesis HASH\` in repeat experiments.

### Step 5 — deploy existing SSE smart contracts using only test ETH

The faucet EOA was funded at OUR genesis; no one buys real ETH.
Use an unlocked interactive keystore with Foundry. Exact \`--sender\`
is required so the local simulation matches the signer. Never put a
raw private key or keystore password into CLI arguments:

\`\`\`bash
forge build
export SSE_MIN_MONITOR_BOND_WEI=1000000000000000
export SSE_USE_GLOBAL_MERKLE=false
forge script script/DeploySSEPos.s.sol:DeploySSEPos \
  --rpc-url "$SSE_EL_RPC" \
  --keystore "$HOME/sse-pos-wallets/faucet.keystore.json" \
  --sender "$FAUCET" \
  --broadcast -vvvv
\`\`\`

The script rejects any chain other than 31339, deploys
\`OpenMonitorCommittee\`, \`SSESettlement\`, and \`OpenResourceBoard\`,
binds all in an explicit order, and permanently disables the legacy
arbitrary seed callback in favor of permissionless future-block
finalization. **This entropy is proposer-biasable**; genuinely
unbiased PoS committee selection requires separate research-grade
randomness and griefing/withholding evaluation. For the scalable
Merkle research arm set \`SSE_USE_GLOBAL_MERKLE=true\` BEFORE a
SEPARATE NEW contract deployment, never toggle a live instance.

After actual receipts, capture deployed addresses and check:

\`\`\`bash
python tools/sse_pos_contract_attest.py \
  --rpc-url "$SSE_EL_RPC" \
  --committee ACTUAL_MONITOR_COMMITTEE_ADDRESS \
  --settlement ACTUAL_SETTLEMENT_ADDRESS \
  --board ACTUAL_RESOURCE_BOARD_ADDRESS \
  --source-commit "$(git rev-parse HEAD)"
\`\`\`

A check passing means the three actual deployed bytecodes exist
and the references match, NOT that real physical SLA correctness,
code source equivalence or permissionless validator onboarding was
proved. Save transaction receipts and build artifacts.

### Step 6 — public participation acceptance (PENDING)

1. Open **both** EL and Beacon gossip ports to eligible external
   participants with independent discovery bootstrap nodes and
   secured network-layer access. Keep RPC/EngineAPI authenticated
   or localhost/tunnel only; do not expose privileged validator APIs.
2. A new host generates its own Ethereum EL P2P identity and BLS
   validator keys; obtains signed chain descriptors and public EL+CL
   bootnodes, syncs chain independently and checks genesis/root.
   It must NOT receive the bootstrap mnemonic or a Tailscale invitation.
3. It obtains 32 worthless test ETH through a public non-discretionary
   faucet (with rate-abuse/DoS defenses), submits a genuine staking
   deposit and independently confirms \`pending_queued\` then
   \`active_ongoing\` from at least two Beacon clients.
4. Validators get proposed/attested slot rewards and penalties
   through the actual PoS consensus accounting; no invented
   per-block SSE-admin mining reward.
5. Any account requests consumer/provider/monitor roles. Monitor
   registration requires the positive on-chain bond and committee
   selection per lease. Provider must prove SLA delivery; a signed
   self-report alone is not physical truth.
6. Run actual funded consumer/provider/monitor leases and adversarial
   observation experiments on chain31339 with published full logs,
   payments and real consensus finality evidence.
7. Acceptance of truly independent validator admission must be
   demonstrated on at least two independently provisioned hosts
   (not multiple containers sharing one genesis mnemonic).

The source in this milestone implements steps 1-5 **up to live
operator testing**, and provides read-only status checks for step 6.
It does **not yet** automate independent participant staking deposits,
public NAT/relay discovery or a trustless faucet. Calling the network
fully permissionless before those tests would be false.

## Safety and scientific novelty

The fact that the independent chain is PoS is an implementation choice,
NOT the scientific novelty of SSE. The proposed contributions are
observation-aware settlement under partial SLA evidence, globally
auditable monitor selection, honest resource verification and
quantified security/gas/liquidity/finality costs. Never claim
real-economic proof against Sybil attacks when test tokens are free.

Other chain state deliberately preserved:
- 31337: previous Anvil VM with historical contracts/obligations.
- 31338: earlier QBFT experimental source and canary artifacts,
  not the final SSE network.
- 31339: NEW own independent PoS blockchain, no real ETH.


## NEW — real self-service staking deposit for an external validator

No administrator grants the validator role. A separate participant,
on a separate machine and using their OWN BLS keys, creates standard
\`deposit_data.json\` for this **chain's actual GENESIS_FORK_VERSION**
using a reviewed Ethereum validator deposit/keystore generator.
They do not receive or import the lab's bootstrap mnemonic. They
must control an EOA with 32 worthless test ETH on chain31339
plus enough additional test ETH for gas. Native ETH on Ethereum mainnet
is NOT used or required.

Verify the actual version from this blockchain's Beacon REST API,
not a hard-coded mainnet or Hoodi value:

\`\`\`bash
# Replace ACTUAL_BEACON_PORT from kurtosis enclave inspect.
curl -fsS http://127.0.0.1:ACTUAL_BEACON_PORT/eth/v1/config/spec
# Locate data.GENESIS_FORK_VERSION in that response.
\`\`\`

On the **independent participant's machine**, after safely transferring
ONLY the public deposit_data.json (never validator keystore/mnemonic):

\`\`\`bash
mkdir -m 700 "$HOME/sse-pos-deposit-evidence"
python tools/sse_pos_validator_deposit.py \\
  --deposit-data /PRIVATE/PATH/deposit_data.json \\
  --fork-version 0xACTUAL_GENESIS_FORK_VERSION \\
  --output "$HOME/sse-pos-deposit-evidence/validator-deposit.json"
\`\`\`

The script verifies 48-byte BLS public key, 32-byte withdrawal
credentials, 96-byte BLS signature byte length, exactly 32 test
ETH (32000000000 gwei) and rederives the SSZ DepositData root.
It outputs calldata for the standard DepositContract
\`deposit(bytes,bytes,bytes,bytes32)\` at
\`0x00000000219ab540356cBB839Cbe05303d7705Fa\`.
**It does NOT verify the BLS proof signature or submit a
transaction.** A consensus client decides validity and activation,
not SSE. Always confirm that the actual deposit contract bytecode
exists at this address on chain31339 before depositing.

After verifying the actual execution chain ID31339 and the deposit
contract, the independent participant can explicitly submit their
test-ETH-funded transaction using their OWN encrypted EOA wallet:

\`\`\`bash
CALLDATA="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["calldata"])' "$HOME/sse-pos-deposit-evidence/validator-deposit.json")"
cast send 0x00000000219ab540356cBB839Cbe05303d7705Fa \\
  --data "$CALLDATA" --value 32000000000000000000 \\
  --rpc-url "$SSE_EL_RPC" \\
  --keystore /PRIVATE/PATH/participant-EOA.keystore.json \\
  --sender 0xPARTICIPANT_PUBLIC_EOA_ADDRESS
\`\`\`

**This sends/spends ONLY test ETH on our own chain.** Save the
transaction receipt. Independently observe the newly created
validator's BLS public key through:
\`python tools/sse_pos_devnet_health.py --execution-url ...
--beacon-url ... --validator-pubkey 0xBLS48BYTE_HEX\`.
First expect a pending status, then an active status only after
the actual beacon protocol transitions. Do not equate a mined
deposit transaction with immediate permission to sign blocks.

The protocol admission path is implemented as a *read-only deposit
data preparation and validation* layer and an explicit ordinary
Ethereum deposit transaction. Fully automated public faucet
distribution, independent BLS key generation for a custom fork,
remote peer bootstrap/advertisements, validator execution/consensus
containers on arbitrary machines and 2+ externally observed
stake activations are still ACCEPTANCE WORK, not completed facts.
