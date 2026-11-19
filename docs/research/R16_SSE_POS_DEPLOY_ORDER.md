# R16 — Fix observed VM4705 SSE contract deployment Unauthorized()

**2026-11-19, chain 31339.** We have an independently running,
private Ethereum-compatible PoS smoke chain with **zero real ETH**.
RPC measured execution height269, Beacon finalized epoch6, and
faucet balance 1,000,000 test ETH. All 29 PoS Python and 144
Foundry Solidity tests passed with OpenZeppelin v5.7.0,
forge-std v1.17.0 and Foundry 1.9.0.
Runtime code sizes at solc0.8.24: Committee22670 B,
Settlement22311 B, Board3739 B (<EIP170 24576 B).

## Live R15 failure reproduced from observed trace

Both operator commands (simulation and `--broadcast --slow`)
stopped with:
`DeploySSEPos::run() -> committee.bindSettlement(...) [Stop]
-> committee.enableDelayedBlockEntropy() [Revert Unauthorized()]`.

The failure is **deterministic**: OpenMonitorCommittee requires
`settlement==address(0)` to turn on delayed entropy,
`enableGlobalMerkleElection`, and
`enableGlobalBatchedRecovery`. The prior deployment script bound
the settlement BEFORE those opt-ins, so a valid smart contract
correctly refused the late changes. No live receipt or deployment
addresses were produced by these failed runs. Addresses in Foundry's
simulation trace MUST NOT be described as actual on-chain contracts.

**R16 source fixes order, NOT chain state:**

1. Deploy OpenMonitorCommittee with positive test-ETH bond.
2. Call `enableDelayedBlockEntropy()` on the still-unbound pool.
3. If global Merkle requested, call `enableGlobalMerkleElection()`
   and `enableGlobalBatchedRecovery()`, in that exact order,
   while the roster is empty.
4. Deploy SSESettlement and OpenResourceBoard.
5. Call `committee.bindSettlement(settlement)` ONCE.
6. Call `settlement.bindResourceBoard(board)` then
   `board.bindSettlement(settlement)` ONCE.
7. Check all onchain references and that global Merkle election
   and batched recovery opt-ins are both either on or off.

Added `foundry/test/PoSDeploymentBootstrap.t.sol` with 3
EVM regression tests for both modes and rejection of late opt-ins,
and `tests/test_sse_pos_deployment_order.py` with static order tests
that directly analyze the actual script's executable statements.
Strengthened `sse_pos_contract_attest.py` to reject a Merkle mode
whose batched recovery switch disagrees with it.

## Run on VM4705 (DO NOT restart or recreate PoS genesis)

    cd ~/sse-pos
    source .venv-pos/bin/activate
    export PATH="$HOME/.foundry/bin:$PATH"
    git fetch origin integration/r7-wp09q-wan-multivm-no-actions
    git switch --detach APPROVED_R16_COMMIT
    git submodule update --init lib/forge-std lib/openzeppelin-contracts

    python -m unittest discover -s tests -p 'test_sse_pos_*.py' -v
    forge build --sizes
    forge test

All above MUST pass, and all deployed EIP170 runtime sizes remain
below 24576 bytes. Test counts should increase to 31+ Python and
147 Foundry (new regressions); these counts are not claimed to have
passed until observed on the VM. If any fail, STOP.

Then read-only chain gate:

    export SSE_EL_RPC="http://127.0.0.1:32770"
    export SSE_FAUCET="0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7"
    cast chain-id --rpc-url "$SSE_EL_RPC"
    cast balance "$SSE_FAUCET" --ether --rpc-url "$SSE_EL_RPC"
    cast nonce "$SSE_FAUCET" --rpc-url "$SSE_EL_RPC"

The RPC chain ID MUST equal 31339. Do not treat old R15
simulation addresses as deployed contracts. Encrypted faucet
private key remains at
`$HOME/sse-pos-wallets/faucet.keystore.json`;
NEVER publish its contents or your passphrase.

Use an unbroadcast simulation FIRST:

    export SSE_MIN_MONITOR_BOND_WEI=1000000000000000
    export SSE_USE_GLOBAL_MERKLE=false
    forge script script/DeploySSEPos.s.sol:DeploySSEPos \
      --rpc-url "$SSE_EL_RPC" \
      --keystore "$HOME/sse-pos-wallets/faucet.keystore.json" \
      --sender "$SSE_FAUCET"

Inspect for COMPLETED simulation and full binding invariants,
no Unauthorized() and no reverted opcode. If successful and only
then, submit actual test-ETH transactions on our research chain:

    forge script script/DeploySSEPos.s.sol:DeploySSEPos \
      --rpc-url "$SSE_EL_RPC" \
      --keystore "$HOME/sse-pos-wallets/faucet.keystore.json" \
      --sender "$SSE_FAUCET" --broadcast --slow

Collect actual deployed addresses, TX hashes, successful receipts,
and on-chain bytecode, then run:

    python tools/sse_pos_contract_attest.py \
      --rpc-url "$SSE_EL_RPC" \
      --committee ACTUAL_COMMITTEE_ADDRESS \
      --settlement ACTUAL_SETTLEMENT_ADDRESS \
      --board ACTUAL_BOARD_ADDRESS \
      --source-commit "$(git rev-parse HEAD)"

The attestation requires positive monitor bond, delayed entropy,
valid contract code, all bidirectional bindings, and globally paired
Merkle/recovery settings. It does not prove physical SLA delivery,
unbiased entropy, live validator admission or code-source equality.

## Research-critical warnings

Foundry 1.9.0 emits security lint warnings (e.g. reentrancy
and weak block-derived PRNG). Passing the 144 EVM tests does NOT
equate to a security audit, and **delayed block entropy is
proposer-biasable**. This mode is specifically a laboratory
fallback, not an unbiased production selection oracle.

The original upstream Kurtosis launch printed genesis validator
mnemonic and prefunded private EOA keys in terminal output.
These bootstrap keys are TAINTED; do NOT open this existing
one-host chain to remote validators or stake assets with real
value. Later permissionless validator admission must be tested
on a fresh, independently keyed and safely launched PoS network
with public EL+CL discovery and verifiable 32 worthless test ETH
deposits. The present smoke chain is NOT physical decentralization.

Once SSE contracts deploy, the next milestone is funded resource
request, real provider bid, leased resource selection, bonded
monitor registration, quorum evidence and test-ETH settlement
against these ACTUAL contracts. Those transactions have NOT
yet been observed or performed on chain31339.
