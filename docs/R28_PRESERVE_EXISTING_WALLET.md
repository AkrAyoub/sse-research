# R28 — Preserve the real Cast wallet and repair Lighthouse CLI

**State: SOURCE ONLY, NOT YET VM TESTED.** On VM4706, the user explicitly approved the TEST-only EOA and pinned Cast v1.9.0 reported a newly created encrypted keystore and PUBLIC EOA address. The R20 schema checker then returned "unexpected keystore schema". Do NOT rerun the R20 creator or delete any existing wallet. The R27 Lighthouse BLS HD wallet attempted twice, but both attempts were stopped at the nonexistent singular --wallet-dir preflight, BEFORE any creation or owner approval. No BLS parent/validator is proven created.

## Real upstream causes

- Pinned Lighthouse v8.3.3 actual account_manager/src/lib.rs sets WALLETS_DIR_FLAG to **wallets-dir** (plural). R28 changes both the preflight help requirement and owner-private Docker command to --wallets-dir. The updated R27 owner script STILL separately requires explicit CREATE-BLS-HD-WALLET consent.
- Pinned Foundry v1.9.0 uses eth-keystore v0.5.0; that upstream encrypted UTC-V3 structure optionally omits its address field unless compiled with the geth-compat feature. R20 falsely required address in every encrypted keystore. R28 allows absent address but returns withdrawalAddress null, addressCryptographicallyVerified false; never invents an EOA from a filename.
- New owner-private tool tools/sse_pos_cast_keystore_shape.py outputs only sanitized top-level and crypto-envelope FIELD NAMES and safe boolean flags, never VALUES, ciphertext, addresses or passwords. If normal parsing fails, run this READ-ONLY schema diagnostic and paste only its output.
- New scripts/r28_verify_existing_cast_withdrawal.sh verifies exact clean Git commit, private owner keystore file, verified Cast SHA256 and safe structure; then uses the *same existing* keystore through Cast's local wallet address --keystore hidden-password prompt, strictly compares returned address to the PUBLIC address previously observed. It never runs wallet new, decrypt-keystore private-key output, file overwrite or network operation. The new wrapper has NOT yet run; if it refuses, preserve existing keys for safe follow-up.

## Owner procedure and limits

After GitHub exact-SHA checkout and NEW Python tests pass, verify existing EOA first, then separately run the corrected Lighthouse HD wallet creator ONLY when the owner wishes to type CREATE-BLS-HD-WALLET. Never paste EOA encrypted JSON, password, BLS mnemonic, keystores or private command logs in chat/GitHub. The old R20 creation script left an owner-private local .cast-wallet-output-private log on the post-creation reporter failure; preserve privately until recovery is verified, never display it. Back up both encrypted keystores and all distinct required passwords, plus the BLS HD mnemonic, OFFLINE.

The R28 source security suites are: 10 R20 wallet-report tests; 6 safe shape-probe tests; 6 existing EOA recovery script tests; 8 Lighthouse HD wallet script tests; **30 source-only methods, NOT OBSERVED as passing on VM4706**.

G0 source gate passed 38/38 previously. Current G1 still has no verified owner EOA decryption, no BLS HD wallet/signing keys, no EL+CL Genesis/SSZ, no chain31340 validator/client operation, no VM-to-laptop P2P, and no live funded SSE roles. Keep numerical participant counts open and honest; one-operator live lab is not an independent public validator network.
