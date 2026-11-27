# R253 — V2 deployer really has zero native TEST ETH; historical Genesis signing custody EXISTS on VM4706

## Actual new VM4707 read-only result (2026-11-24)

- Private encrypted application deployer keystore exists with
  **directory 0700 and file 0600**:
  `ENCRYPTED_WALLET_PERMISSIONS_OK=true`.
- Actual node RPC on VM4707 returns **chain ID 31340**.
- Actual public account
  `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
  has exactly **0.000000000000000000 native TEST ETH**.
- No new app transaction sent. There is no basis to claim a funded
  deployer, contract deployment or paid on-chain service.

## Important recovered earlier actual custody evidence

**Historical owner-run R28 custody validation** recorded in
`docs/R28_PRESERVE_EXISTING_WALLET.md`, dated 2026-11-20:
the existing encrypted **Cast TEST-only execution/withdrawal EOA**
on original owner **VM4706** was successfully unlocked at a hidden
password prompt and the public key derived by pinned Cast v1.9.0
**matched the same genesis-funded address**
`0x13fb73aace8A11Be2899D047635A757a224Ce00B`.
`R28_WITHDRAWAL_ADDRESS_VERIFIED_BY_PINNED_CAST=true`
was actually observed at that time.

The known original private owner keystore is at
`$HOME/.local/share/sse-r20-operator-private/withdrawal-keystore/sse-r20-withdrawal`
on **VM4706**, NOT VM4707. It is NOT a Lighthouse BLS key and
must not be newly generated, migrated, uploaded, printed or
accidentally used for marketplace role operations.

This historical **real custody proof** corrects R252's overly broad
statement that the Genesis EOA signing-key custody had never been
verified. It does not establish that VM4706 still has the file,
that the password still works, that the EOA is spendable right now,
or permission to sign a value transfer from it.

At the last live VM4707 R201 snapshot, the Genesis EOA had
**1,000,007.92902409 TEST ETH** at finalized block 24692,
nonce 0. This is a real chain balance; fresh VM4706 read-only
balance and chain-id checks are still required.

## Efficient next single VM4706 read-only check

Use existing owner VM4706 terminal, **no key/password unlock**:

```bash
(
  set -euo pipefail
  CAST="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0/cast"
  KEY="$HOME/.local/share/sse-r20-operator-private/withdrawal-keystore/sse-r20-withdrawal"
  EOA="0x13fb73aace8A11Be2899D047635A757a224Ce00B"
  RPC="http://127.0.0.1:18545"
  test "$(id -u)" -ne 0
  test -x "$CAST"
  test -f "$KEY"
  test ! -L "$KEY"
  test "$(stat -c %a "$(dirname "$KEY")")" = 700
  test "$(stat -c %a "$KEY")" = 600
  test "$(stat -c %u "$KEY")" = "$(id -u)"
  echo "VM4706_EXISTING_ENCRYPTED_GENESIS_EOA_FILE_OK=true"
  test "$("$CAST" chain-id --rpc-url "$RPC")" = "31340"
  echo "VM4706_ORIGINAL_CHAIN_ID_OK=true"
  "$CAST" balance "$EOA" --ether --rpc-url "$RPC"
  "$CAST" nonce "$EOA" --rpc-url "$RPC"
)
```

This is **not** private-key custody revalidation or owner approval
for signing; it is current evidence of existing encrypted key path,
file permissions and actual spendable-address public balance/nonce.

If the key is still present and the chain matches, the owner may
explicitly authorize **one bounded native TEST-ETH transfer** from
this VM4706 owner-controlled execution EOA to the new VM4707
separate encrypted app deployer. Use pinned Cast interactive
keystore password (never CLI plaintext); require a fresh exact chain
and destination check, send only **one** signed transaction with
operator consent and report only public tx hash/receipt. Neither
the Foundry source gate nor current read-only checks authorize
this future transaction.

The genesis owner's key must not be copied to VM4707.
After actual successful finalized funding, V2 can be deployed from
the app-only EOA on VM4707 with an independent explicit authorization.
Do not rerun already green source-only regressions at
`6930c069b4e9738e63e2ce9d53b10d126053335e`.
