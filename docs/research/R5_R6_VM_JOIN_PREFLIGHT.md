# R5/R6 VM join gate — read-only, pinned-code preflight

**Status:** first deployable onboarding primitive, not autonomous VM joining.
**Related phases:** R5 autonomous role agents, R6 Ubuntu bootstrapping, R9
multi-VM evaluation. Uses existing read-only role heartbeat / Ansible groundwork.

## What is validated

- A locally checked-out Git revision exactly matches an operator-pinned full
  40-character commit ID. This checks checkout identity **not** source provenance,
  distribution signatures, dependency integrity or tamper resistance.
- Only explicitly configured application roles: `consumer`, `provider`,
  `monitor`, `observer`. Ethereum validator/full-node setup is separate.
- The configured RPC self-reports the expected EVM chain ID.
- The expected SSESettlement address returns bytecode.
- SSESettlement `domainSeparator()` matches the on-chain contract address,
  chain ID, `SSESettlement` and version `1`. This checks application scope,
  not contract upgrade safety or independently authenticated chain finality.
- Optional public wallet native ETH balance is read (not key ownership,
  monitor bond eligibility, sufficient gas for any particular transaction).

The tool performs only `eth_chainId`, `eth_getCode`, `eth_call` and
`eth_getBalance`. Remote RPC URLs require HTTPS, with no username/password,
query string or redirect. RPC provider credentials encoded in a URL path are
never printed in the generated report. It never loads a private key, signs,
sends a transaction, deposits a bond, deploys, provisions a VM, touches Git,
or starts a role process. **A PASS is NOT proof that a VM joined the network.**

## Example on a VM with a verified checkout

Obtain the exact full commit SHA from a separately authenticated release
manifest or an operator-approved deployment record. Do **not** merely use
whatever the local checkout itself reports as the expected revision.

```bash
# Supply an EXACT immutable commit sha; example is the existing R1/R2 base.
# Use your actual deployed settlement contract and intended network ID.
python tools/sse_vm_join_preflight.py \
  --checkout . \
  --revision "APPROVED_FULL_40_CHARACTER_COMMIT_SHA" \
  --roles provider,monitor \
  --rpc-url "http://127.0.0.1:8545" \
  --chain-id 31337 \
  --settlement "0xYOUR_DEPLOYED_SETTLEMENT_ADDRESS"
```

For Sepolia, use chain ID `11155111`, **an HTTPS RPC provider**, and a
newly deployed compatible SSESettlement address. The old Anvil addresses do
not automatically exist on public testnets. Add `--wallet 0x...` to read the
wallet's native test ETH gas balance. No faucet, wallet or registration occurs.

Run offline regression tests:

```bash
python -m unittest discover -s tests -p test_sse_vm_join_preflight.py -v
python -m unittest discover -s tests -q
```

## Next required R5/R6 tasks before calling onboarding automatic

1. Verify a signed immutable **release artifact** or trusted commit provenance
   at initial VM bootstrap; checksum/package and supply-chain review.
2. Wire explicit role selections into a secure least-privilege service manager.
3. Provide independent key custody / wallet ownership proofs **without**
   placing keys in GitHub or publicly readable files.
4. Add discovery/failover among authenticated RPC endpoints and liveness
   monitoring; record block-hash/finality trust assumptions.
5. Implement role-specific registration and funding with safe permission checks;
   monitor `minimumBond` and all confirmations must be enforced on chain.
6. Launch multiple VMs, run provider/monitor roles under separate operators,
   verify real signed interactions and testnet-native ETH accounting.
7. Integrate with Ubuntu cloud-init/Ansible only after the read-only gates pass.

No production role actions or public-testnet transactions have been enabled.
