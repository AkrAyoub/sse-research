# R27 — Step31 verified; G1 owner-controlled private wallet custody

**Date:** 2026-11-20. **Observed G0:** VM4706 exact SHA `f1ddae763735fe365e49e7286ae83e5fb689ed3a`, `13/13` genesis builder + `9/9` EIP-2335 public exporter + `16/16` contribution regressions = **38/38 PASSED**, zero failures; final Step31 marker observed. No real wallet, BLS signing keys, genesis, validator or chain31340 was created by that test batch. See journal Entry043.

**R28 operational correction (2026-11-20):** The owner actually ran R20, confirmed `CREATE`, and pinned Cast successfully created an encrypted EOA keystore. The old structural reporter then rejected the schema. **Do not run the R20 creator again: the original wallet must be preserved and verified with R28 existing-wallet recovery.** The R27 HD-wallet creator was also tried twice, but stopped BEFORE approval because we mistakenly used the singular `--wallet-dir`; pinned Lighthouse v8.3.3 correctly uses `--wallets-dir` (plural). That is now fixed in source but not yet VM verified. Follow [R28 existing-wallet recovery](R28_PRESERVE_EXISTING_WALLET.md) for the current commands and evidence. No BLS wallet exists yet.

## Chain31340 G1 private custody steps — NOT an executed result

The system uses **two distinct private key types**; neither should be copied to GitHub or chat:

1. **TEST-only execution/withdrawal EOA:** existing reviewed `scripts/r20_create_local_operator_withdrawal.sh <exact sha>` verifies the pinned Foundry `cast` binary and Lighthouse help, then *only after the local human types literal `CREATE`* creates one password-encrypted Ethereum keystore. It deliberately declines any other response. Never fund with real ETH or reuse a personal/mainnet wallet. Keep a private encrypted backup and independent password backup offline. The owner subsequently approved creation in Step32 and the encrypted EOA keystore EXISTS; only the reporter failed. DO NOT rerun the creator.
2. **Actual independent Lighthouse EIP-2386 parent HD wallet:** `scripts/r27_create_local_lighthouse_hd_wallet.sh <exact sha>` (attempted twice, correctly refused before approval; fixed R28 source not yet retested) verifies immutable clean source, owner TTY and pinned Lighthouse v8.3.3 image ID, probes real offline CLI for `--name`, `--password-file`, `--mnemonic-output-path` and `--wallets-dir`, and requests a *separate, explicit* `CREATE-BLS-HD-WALLET` confirmation. No wallet is created before that consent.
   - The actual upstream Lighthouse v8.3.3 tagged source `account_manager/src/wallet/create.rs` **prints the BIP39 recovery mnemonic to stdout** unless suppressed. The script redirects stdout to `/dev/null` and uses `--mnemonic-output-path` to store the recovery phrase **only on owner-controlled 0600 private local disk**. It saves a separate randomly generated password file by `--password-file`; Docker mounts only the owner-private directory, runs with `--network none`, non-root UID, no-new-privileges, dropped capabilities and read-only filesystem. No BLS validator *signing keystores* are created yet. A private stderr file is removed after success and kept locally on failure (NEVER paste that file).
   - The HD parent wallet can later derive genuine independent BLS signing keys with Lighthouse `account validator create` only after a reviewed, correctly forked chain31340 consensus configuration is available. The same parent seed is not reused across independent operators. A second VM may host an ordinary nonvalidator full node with zero mnemonic/TEST ETH.
   - Owner MUST back up the mnemonic file, generated password file and encrypted wallet directory offline with separate physical access controls before deriving stakes. Do not accidentally expose the wallet mnemonic via `cat`, `tee`, terminal recording, shell `set -x`, `docker logs`, GitHub or cloud files. Never import this research-only wallet to Ethereum Mainnet.
3. **Next actual network artifacts:** public EL `genesis.json` + CL `config.yaml` consistent for chain31340 and a verified real deposit contract at the advertised address, real owner-derived validator signing keys and slashing protection, then a real upstream `eth-genesis-state-generator` SSZ generated from **only public keys**. Verify Besu+Lighthouse compatibility using actual clients, not just YAML preflight; chain31340 remains NONEXISTENT until that succeeds.

**Non-negotiable:** owner must type exactly the approval phrase on the VM interactive terminal. A response other than either phrase is a refusal, NOT a reason to bypass or restart without consent. No script called from GitHub Actions. No fake independent operators or synthetic validator keys. One-host lab is genuine single-operator PoS if operationally observed but **NOT** independent public-network acceptance. No permanent caps on network roles.

## Source tests

`tests/test_sse_pos_lighthouse_hd_wallet_guard.py` originally contained **7** static tests actually passed on VM4706 before CLI failure; R28 adds an eighth unexecuted test, including `bash -n` syntax, exact pinned executable identity checks, no-network Docker invocation, owner-only private writes, mnemonic stdout suppression, no filename overwrite and explicit separate authorization. These are NOT yet run on VM. A passing static test is not proof that upstream wallet generation/backup has been performed safely; the real owner must observe results and retain secrets privately.

## Immediate read-only and optional owner-authorized procedure

At exact current PR SHA (provided separately by ChatGPT after this document commit):

```bash
python3 -B -m unittest discover -s tests -p 'test_sse_pos_lighthouse_hd_wallet_guard.py' -v
bash -n scripts/r27_create_local_lighthouse_hd_wallet.sh
```

**Never run the R20 wallet creator again on VM4706.** It has already created a real encrypted wallet. Follow the **R28** owner-password hidden-prompt verification flow to derive and confirm its public address. Only thereafter and **only when the owner wants a new BLS HD wallet** may they independently run the R27 script with the exact new Git SHA and type `CREATE-BLS-HD-WALLET` after the corrected read-only `--wallets-dir` help verification.

The old command snippets for R20 creation are intentionally removed here to avoid accidental duplicate keys/overwrite. Do not paste wallet outputs containing secrets, private logs, mnemonic or passwords. The only safe results to report are short `R20_...` and `R27_...` boolean success/refusal statuses and public withdrawal EOA address (optional).

## Multi-VM timing

G0 observed pass; G1 and G2 run first on VM4706; **immediately after G2's native finalized PoS blocks**, the next actually available VM joins with verified public genesis as its own genuine Besu+Lighthouse full node (no validator staking required). The user's one external laptop follows as another full peer across a distinct Internet path. This is an experiment with finitely many real machines, never a fixed role-count protocol restriction. Additional independently owned operators can add actual validators through live post-genesis deposit/activation when enabled. Refer to [R26 execution roadmap](R26_EXECUTION_ROADMAP_AND_HOST_ROLES.md).
