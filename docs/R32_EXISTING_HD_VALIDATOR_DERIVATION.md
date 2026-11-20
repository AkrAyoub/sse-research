# R32 — Derive REAL Lighthouse voting keys from the existing owner HD wallet

**Status:** 2026-11-20, GitHub source only, **NOT yet VM-tested or executed**. VM4706 operator DID explicitly authorize R27 parent HD wallet generation with `CREATE-BLS-HD-WALLET` and observed `R27_ENCRYPTED_HD_WALLET_CREATED_ON_OWNER_VM=true`. The random EIP-2386 parent HD wallet, password and private mnemonic recovery file are real, owner-local and must NOT be recreated. Actual offline backup has NOT yet been separately confirmed. Previously the owner verified a separate Cast TEST-only EOA, public address `0x13fb73aace8A11Be2899D047635A757a224Ce00B`. Neither password nor mnemonic was pasted to ChatGPT or GitHub. See journal Entry050.

## New source script, intended G1 key ceremony

`scripts/r32_derive_existing_lighthouse_validators.sh EXACT_GIT_SHA POSITIVE_LOCAL_BATCH_COUNT VERIFIED_PUBLIC_TEST_EOA` is a **different, one-time, human-approved step from R27**. It ONLY uses the existing encrypted HD parent wallet under `~/.local/share/sse-r27-bls-operator-private`; never creates a new parent wallet or mnemonic. It runs pinned, image-identity-verified **REAL Lighthouse v8.3.3** (`account validator --validator-dir /owner/validators create --wallets-dir /owner/wallets --secrets-dir /owner/secrets --wallet-name sse31340-operator --wallet-password /owner/owner-wallet.pass --count N`) inside an offline `--network none`, unprivileged UID, no-extra-capabilities Docker container with constrained CPU/RAM.

**Two independent owner confirmations required before file creation**: type `BACKUP-CONFIRMED` only after wallet directory, password and mnemonic have been backed up to offline owner-controlled storage; then separately type `DERIVE-BLS-VALIDATORS` to authorize the specific local count. The code cannot verify that an external backup exists: it only records the human acknowledgment. Any different input causes a refusal. If a creation fails or partially writes files, it preserves them and REFUSES rerun. Never delete/overwrite real keys, HD wallet, slashing-protection DB or logs to force a green result. Never paste the secrets, EIP-2335 voting-keystore JSON, private stderr, recovery phrase or password into chat or GitHub.

After the REAL local signing keystores exist, the same script enforces 0700 directories/0600 files, preserves the generated slashing-protection database, and runs existing `tools/sse_pos_public_keystore_export.py` locally, outputting ONLY public BLS voting pubkeys + 32-worthless-TEST-ETH `0x01` withdrawal credentials pointing at the explicitly supplied owner TEST EOA. The public source file is create-only and remains under the owner's private directory until manually reviewed. No BLS mnemonic/keystore, password or signing key is uploaded. Generic `account validator create` deposit transaction payloads **must not** be reused for bespoke chain31340: the later genesis source independently constructs appropriate withdrawal credentials and must prove real EL+CL compatibility.

**One-host batch count** is an explicit real resource constraint (1..64 per this initial local script), NOT a validator/miner/network role hard cap. Additional operators/validators must be able to join the actual future permissionless beacon network through real deposits and activation after genesis; one real host still represents ONE administrative fault domain, regardless of how many keys it derives. Do not treat first-host lab as decentralized or fake four organizations.

## Scientific status, remaining gates

New `tests/test_sse_pos_existing_lighthouse_validator_derivation_guard.py` contains **8 SOURCE-ONLY** checks of Bash syntax and fail-closed shell/pinning/owner authorization/secret isolation. These are NOT results from the real VM yet. A static test PASS cannot verify actual BLS key generation, valid signatures/PoP, native finality or independent ownership.

The actual new real user event was **parent HD wallet creation only**, NOT validator signing-key derivation. After derivation, G1 still requires authentic Ethereum Beacon deposit-contract runtime, real reviewed EL and CL genesis configs (e.g. Besu/Lighthouse fork compatibility), real upstream generator SSZ and actual client acceptance. Next G2: local real Besu+Lighthouse+validator client signs blocks/attestations and FINALIZES. **Immediately** G3: next actually available VM becomes real EL+CL peer, without needing BLS keys or TEST ETH; G4: user's one outside laptop joins through public native P2P, no mandatory static IP or whitelist. No GitHub Actions, VM tracked source edits, wallet uploads or release claims.

## Expected operator workflow after source-only verification

First, checkout the exact GitHub revision given in chat and run:

```bash
python3 -B -m unittest discover -s tests -p 'test_sse_pos_existing_lighthouse_validator_derivation_guard.py' -v
bash -n scripts/r32_derive_existing_lighthouse_validators.sh
```

Only after BOTH owner-managed offline backup and human approval, derive an explicit nonzero count (initial lab may use one genuine validator as one honest host, not a fixed number of global participants):

```bash
bash scripts/r32_derive_existing_lighthouse_validators.sh <EXACT_IMMUTABLE_SHA> 1 0x13fb73aace8A11Be2899D047635A757a224Ce00B
```

The angle-bracket span is a placeholder, not executable until replaced with the reviewed SHA. This invocation is **key generation, not a harmless test**. Do NOT run without actual offline backup and intent to authorize. Report only the `R32_...` status lines, no private source or key files.

