# R20 — Fresh Ethereum PoS genesis with independent validator custody

**Status, 2026-11-19:** source/tools/test preparation ONLY. VM4706 has real Besu 26.11.1 and Lighthouse v8.3.3 verified by immutable Docker digest, Foundry tests passed, but there is **NO public SSE chain31340, no Genesis SSZ/EL genesis built, no independent BLS signing proof, and no real external P2P connectivity yet**.

## What MUST happen (no shared mnemonic or central chain administrator)

1. A group of **actually independent real operators** (initial research fault-domain target: four, not a protocol maximum) each locally generates its own encrypted validator BLS keystores and locally controls its *own* EVM withdrawal address. No participant discloses validator secret keys, mnemonic, deposit-cli secret files, signer API, or keystore passwords to the original project operator or a GitHub repository. Distinct operator labels alone **cannot** establish independent people or physical hosts.
2. Each original genesis operator publishes **only public** validator pubkeys and execution withdrawal credentials in one contribution JSON file using schema `SSE_R20_PUBLIC_GENESIS_VALIDATORS_V1`. For current conservative test-ETH research settings each validator's initial Beacon effective balance is **32,000,000,000 Gwei (32 worthless TEST ETH)**. The first research ceremony has a nominal minimum of 64 active genesis validators, e.g. 16 each from four unrelated operators. This is an explicit configurable **experiment policy**, not a permanent validator limit or a claim that 64 is scientifically optimal; protocol config and performance benchmarks must justify the selected count.
3. A participant with no privilege to sign for any other participant runs `tools/sse_pos_genesis_contributions.py` against these public files to produce a deterministic `validators.txt` for upstream `eth-beacon-genesis --additional-validators`. The collector rejects duplicate pubkeys, duplicate operator labels, cross-operator same withdrawal address, unversioned/corrupted JSON, secret-key fields and wrong test-ETH balances. It gives a SHA-256 digest of the text. **This is only structural verification**: a 48-byte string is not proof of a valid BLS key; a self-declared operator label is not proof of independence.
4. **Before a public genesis is trusted:** verify every actual BLS pubkey's subgroup validity and possession through an *independent local signed challenge or valid deposit-data proof* tied to the new genesis fork version and withdrawal credentials. This cryptographic verification is NOT implemented in the R20 collector and is a launch blocker. The actual independent node owners must demonstrate control, not a coordinator forging a validator roster.
5. Generate an EVM EL `genesis.json` for chain31340 with the proper genuine post-Merge fork schedule, standardized deposit contract/runtime and disclosed native test-ETH allocations. Generate CL `config.yaml` and `genesis.ssz` using a **pinned upstream genesis generator**, matching EL genesis hash, fork activation, deposit contract address and genesis timestamp. Publish actual immutable SHA-256 hashes and Beacon genesis validators root. Verify Besu and Lighthouse actually load them and agree. No 31339 keys/config or shared generated mnemonic.
6. **Initial Beacon genesis validators are legitimately *preloaded in the Beacon genesis state***, as allowed for a new real PoS chain, rather than pretending to have sent 32 TEST ETH on-chain deposit transactions before block 0. A **post-genesis validator**, including any completely unrelated outsider, must fund its own locally owned wallet via available *valueless* native TEST ETH and make a **real 32-TEST-ETH Ethereum deposit-contract transaction**, wait for genuine Beacon activation and attest/propose. Never count genesis preload as evidence of post-genesis admission.
7. Once at least two independent operators provide real Internet-reachable EL+CL discovery seeds and genesis/config artifacts are independently mirrored, outsiders obtain public hash-pinned genesis and software without this private GitHub deploy key or approval. P2P join is open to zero-balance full nodes. Validators, consumers and monitors require their objective on-chain deposits/escrows/bonds, not sign-up by a chain owner. Static IP is not mandatory, but at least some reachable peers and independent observed TCP+UDP paths are necessary; DDNS cannot overcome CGNAT by itself.

## Official generator and public-only input syntax

The **upstream ethPandaOps `eth-beacon-genesis` v0.0.8** release (published 2026-10-09, tag commit `0cc79d6ef62a4577d34f926accfa5673d9092b33`) ships `eth-genesis-state-generator`. Release Linux amd64 asset:

- [Release](https://github.com/ethpandaops/eth-beacon-genesis/releases/tag/v0.0.8)
- [Source usage](https://github.com/ethpandaops/eth-beacon-genesis/blob/v0.0.8/README.md)
- [Public validator list parser](https://github.com/ethpandaops/eth-beacon-genesis/blob/v0.0.8/validators/list.go)
- **Official GitHub asset SHA-256**: `73b5e33ed309e7bd98bd5f115b032a462b7ed8f1b67b204ac2000016c2f1856b`, path `eth-beacon-genesis_0.0.8_linux_amd64.tar.gz`

R20 GitHub script `scripts/r20_install_beacon_genesis_generator.sh` downloads only the exact HTTPS release, verifies the official archive hash, extracts ONLY the expected `eth-genesis-state-generator` executable to the unprivileged user-space toolchain directory and prints its real `--help`. **It does not generate a genesis or request keys**. The executable's presence and published checksum are to be verified on the user's VM before generation.

The public `validators.txt` parser expects lines shaped:

```text
0x<96 lowercase hex characters (48-byte BLS pubkey)>:<64 lowercase hex characters (withdrawal credentials, no 0x)>:32000000000
```

These placeholders are syntax examples, **NOT usable validators**. Do NOT paste seed phrases into this file. The upstream CLI supports `beaconchain --eth1-config <EL_GENESIS> --config <CL_CONFIG> --additional-validators <PUBLIC_VALIDATORS_TXT> --state-output <GENESIS_SSZ>`. Actual EL+CL config and public contributions need to be independently verified first. Until then, no such command should be executed with fabricated fixture keys.

## Public contribution file shape (local-generated, real public key data only)

```json
{
  "schema": "SSE_R20_PUBLIC_GENESIS_VALIDATORS_V1",
  "operatorId": "operator-independent-1",
  "validators": [
    {
      "pubkey": "0x<48-byte real locally generated BLS public key>",
      "withdrawalCredentials": "0x01<11 bytes of zero><20-byte nonzero owner withdrawal address>",
      "balanceGwei": 32000000000
    }
  ]
}
```

The placeholders intentionally are **NOT a runnable JSON example**. Substitute actual PUBLIC data from each operator's independently generated keys; never derive or invent BLS pubkeys from test fixtures.

After four actually independent contributions with actual genesis key material and a verified minimum active count have been collected locally, an unbiased aggregator may run:

```bash
python3 -B tools/sse_pos_genesis_contributions.py \
  --contribution /path/to/operator-1-public.json \
  --contribution /path/to/operator-2-public.json \
  --contribution /path/to/operator-3-public.json \
  --contribution /path/to/operator-4-public.json \
  --output /path/to/new-public-validators.txt
```

This only creates a new deterministic PUBLIC validators text file, refusing overwrite and reporting explicit `blsProofOfPossessionVerified=false`, `operatorPhysicalIndependenceVerified=false`, `consensusGenesisSszBuilt=false`, `readyToLaunch=false`. The output is **not** a genesis and does not create fake validators.

## Critical next engineering pieces (not optional)

- Bind operator contributions to independently verified BLS signatures/deposits, and audit the actual withdrawal credentials and fork version.
- Construct, hash-pin and cross-client verify proper EL Genesis + CL SSZ + fork config + deposit contract. Work with genuine post-Merge fork compatibility rather than hardcoding obsolete pre-Merge fields.
- Verify actual signed blocks, attestation finality, real independent outside P2P clients and new validators' **actual transactions**, not only same-host Docker tests.
- Package a PUBLIC installer/release with multiple optional mirrors, local encrypted EOA/BLS wallets, replacing one-off developer private GitHub key; support multi-role runtime and self-hosted HTTPS UI.
- Protect the host: Ubuntu security updates before exposure, least-privilege Docker/provider sandbox, wallet/Engine API restrictions, tested port mapping and real NAT/CGNAT diagnostics.
- Preserve complete VM4706 experiment ledger, errors and automation gaps in `docs/experiments/VM4706_2026-11-19.md`.

This is a reproducible source checkpoint, not a proposal to create centralized chain governance or an approved-operator list. After genesis, nobody controls eligibility beyond Ethereum protocol deposits and objective on-chain SSE contract rules.
