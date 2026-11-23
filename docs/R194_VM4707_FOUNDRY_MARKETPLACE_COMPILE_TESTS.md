# R194 — Verified Foundry installation, compilation and SSE targeted tests on real VM4707

Source: actual operator-provided VM4707 Foundry and JSON-RPC logs, dated
2026-11-23. This is a reproducible research acceptance record, not a claim
that the contracts are already deployed to chain31340.

## Observed real results

- Official Foundry v1.9.0 linux amd64 installer R19:
  `R19_FOUNDRY_ARCHIVE_SHA256_VERIFIED=true`,
  `R19_FOUNDRY_ARCHIVE_REQUIRED_BINARIES_FOUND=true`.
  Installer source archive SHA256 pinned to
  `8d17599b42e3139f1a9c171be3798c4ed8e743ae17b84cc3435e57bf2a51ae99`.
  `forge Version: 1.9.0`, `cast Version: 1.9.0`.
  Local path `/home/ayoubakrvm4707/.local/share/sse-r19-toolchains/foundry-v1.9.0`.
- Real `forge build` compiled 65 Solidity files with solc 0.8.24;
  compiler ran to completion, with warnings. Dependencies forge-std,
  OpenZeppelin and their submodules were fetched from GitHub into
  the temporary checkout.
- `forge test --match-contract PoSDeploymentBootstrapTest -vv`:
  **3 passed, 0 failed, 0 skipped**.
- `forge test --match-contract MarketplaceEscrowTest -vv`:
  **9 passed, 0 failed, 0 skipped**, including the isolated
  `testMarketplaceLeaseSettlesAndWithdraws` scenario.
- Real localhost VM4707 Besu RPC:
  `cast chain-id --rpc-url http://127.0.0.1:28545` returned
  **31340**; `cast block finalized ... --field number`
  returned **16758** at actual capture.
- Pinned source used `a24819585b921e1c46f03c4fbc21c6611d37010e`
  at checkout `/tmp/tmp.khSXftvQs8/repo`.
- `script/DeploySSE31340.s.sol` is new chain31340 strict fork
  of original chain31339 script, in above pinned checkout.
  Neither broadcast nor test-ETH transfers were executed by
  the build and tests.

## Security and scientific truth

Compiler and Forge lint emitted **warnings** about timestamp
manipulation, potential reentrancy, event order after external
calls, weak on-chain randomness and some uninitialized local
variables, as well as mutability/shadowing. Warnings alone do
not establish an exploit, nor does test success establish
that the protocol is secure. Security review is required before
production claims. In particular the default delayed
future-block entropy scheme is a documented proposer-biasable
research baseline; do not call it unbiased VRF.

This is real compilation and actual local Foundry tests,
NOT live on-chain SSE execution. Tests may use Foundry simulation
internally and must not be represented as real provider compute
or real PoS service agreements.

## Next verified gates, no key disclosure

1. Read-only inventory test-only existing local Foundry keystore
   names only and explicit operator-owned deployment account.
   Never print JSON keystore contents or secret keys. Do not
   import validator signing keys, original owner Engine JWT
   or BIP39 material into Foundry.
2. Read-only query original chain31340 genesis/current finalized
   state, latest gas/basefee, and candidate EOA test ETH balance,
   if a known sender address is provided. Test account must
   be funded from approved original genesis/faucet policy;
   do not assume pre-funded signer accounts can be used.
3. Ensure any already-deployed committee/settlement/board
   contracts are discovered and audited before deploying a
   duplicate. R140 verifies runtime SHA256 + immutable
   bindings against a trusted manifest; it is not a
   generic on-chain discovery index.
4. Complete full Foundry test suite and separately inspect
   security-warning hotspots relevant to deploy path; stop on
   regressions.
5. Only after deployment preflight and explicit operator
   approval may a test-only EOA sign `forge script
   script/DeploySSE31340.s.sol:DeploySSE31340` with
   `--broadcast` to original localhost endpoint. Never
   supply or paste a private key on CLI or in chat.
6. Pin on-chain transaction receipts, finalized block,
   full contract runtime SHA256 and cross-bound contract
   addresses in approved R140 deployment manifest; audit
   against both actual VM4707/VM4709 nodes.
7. Real on-chain consumer/provider/monitor operations,
   resource allocation, physically measured SLAs and
   settlement remain not yet performed or verified.

Earlier R192 genuine two-VM original PoS finality agreement at
epoch571 is distinct and remains verified.
