# R252 — Actual owner-created encrypted adaptive V2 deployer EOA on VM4707

## Owner terminal result (2026-11-24)

Owner executed GitHub source tool
`tools/sse_pos_test_wallet.py --role adaptive-v2-deployer --apply`
in an owner-owned private 0700 directory with password prompted
twice (never printed). The public output reported:

- `walletCreated: true`
- `address: 0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
- Role: `adaptive-v2-deployer`.
- Host: **VM4707** (non-signing observer node).
- Encrypted **application EOA**, **NOT** Lighthouse validator BLS key.
- Local private keystore (NEVER upload or show contents):
  `/home/ayoubakrvm4707/.local/share/sse-v2-app-only/adaptive-v2-deployer.keystore.json`
- `privateKeyPrinted: false`
- `passphraseStored: false`
- `ethereumTransactionsSent: false`
- `testFundsCreated: false`
- Reported initial wallet balance: **0 native TEST ETH** (the
  wallet-generation tool creates no funds; this figure is **not yet
  an independent on-chain balance observation**).
- This does **not** independently prove the user has verified
  decryption/recovery, backed up the encrypted file/password,
  or established funds from a spendable source.

Do not commit the actual keystore or secret password, mnemonic,
raw private key, BLS material or signed raw transaction to GitHub.

## Prior real original chain31340 state

VM4707 read-only R201 matched original execution genesis
`0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`.
At finalized block 24692, publicly funded Genesis account
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`
held **1,000,007.92902409 native TEST ETH**, finalized nonce 0.
**No signing-key custody for this public EOA was verified.**
Presence of value in the blockchain is not proof that anyone can
sign a transfer from that address.

At immutable SHA `6930c069b4e9738e63e2ce9d53b10d126053335e`,
the complete V2 Python, compiled Solidity ABI parity
and 21 V2 Foundry EVM regressions PASS. Do not rerun unchanged
code just because a new application EOA has been created.

## NEXT: funding, not more unit tests

1. On VM4707 inspect **only public balances** using verified local
   RPC: `cast balance 0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0 --rpc-url http://127.0.0.1:28545 --ether`.
2. Establish explicitly **which independently controlled, genuinely
   funded chain31340 EOA can sign a first transfer**. The
   Genesis public account is a possible source **only if**
   owner proves private signing custody and explicitly authorizes
   its use. No default deterministic test key, copied mnemonic,
   VM validator key, guessed key or accidental Genesis EOA
   signing is permitted.
3. If none has spendable funds, state `funding signer unavailable`;
   **cannot** truthfully deploy a live contract or magically mint
   TEST ETH. The public permissionless faucet is only a tested
   candidate source, not proven deployed/funded. Bootstrapping
   requires a genuine controlled funded source or explicit
   chain economic/governance decision, which must not silently
   alter the original genesis.
4. Only after identifying a funded signer and receiving explicit
   approval for an actual value transfer, prepare a bounded
   **single native TEST ETH funding transaction** to the new
   deployer, obtain real canonical/finalized receipt and current
   balance. Do not send a transaction yet.
5. Next set a scientifically justified positive `minimumBondWei`
   and EIP1559/legacy deployment gas budget, and explicitly authorize
   exactly one V2 deployment via
   `script/DeploySSEAdaptive31340.s.sol`.
   The constructor itself creates the linked vote ledger.
6. Independently prove deployment receipt, finalized runtime
   SHA256, bidirectional contract binding and bond via R206;
   only then run actual bonded monitor/lease/paid SLA experiments.

No VM/service/validator/chain mutation performed by this GitHub
documentation commit.
