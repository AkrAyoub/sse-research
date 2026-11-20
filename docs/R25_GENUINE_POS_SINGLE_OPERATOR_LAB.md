# R25 — Genuine chain31340 SSZ genesis from real owner-held BLS keys

**Status 2026-11-20:** New R25 source ONLY, not yet run on VM4706. Actual previous VM evidence: **31/31 R24 funded-V2 tests and 196/196 entire Solidity suite PASS at SHA `298518e51eeaf59477a92450fbec48bb8980eccd`**. New one-host LAB Genesis builder source has NOT produced or validated `genesis.ssz` or launched EL/CL yet.

## Why the R25 lab path exists

The eventual SSE chain is fully permissionless and has **no fixed number of participants in ANY role**, including validators. Genesis, however, is necessarily a finite initial snapshot. The project's machine inventory is limited to its provisionable VMs and exactly one physically external non-VM laptop. It is scientifically dishonest to invent four distinct administrators, four VMs, or 64 true independent signing operators to satisfy an early "real client smoke" gate.

The original public contribution collector required at least two independent operators; the R25 change admits exactly **one locally controlled operator** ONLY with the explicit command flags `--min-operators 1 --single-operator-lab`. It labels results `singleOperatorLabOnly=true`, `publicMultioperatorNetworkReady=false`, BLS PoP/physical independence unverified, network not started. The regular multioperator collector policy remains explicit, with `min_operators>=2` if not in lab mode. **No R25 lab can be presented as public decentralization or external community acceptance.**

## What the real code does (no synthetic blockchain, no fake validators)

- `tools/sse_pos_genesis_build.py` reads only a REAL owner-provided execution `genesis.json`, consensus `config.yaml` and actual public BLS validator contribution JSON. No mnemonic or keystore upload, dummy BLS generator, fake PoS peers, fake funding or simulated SLA workload.
- Strictly validate chain ID **31340** (NOT compromised 31339), PoS terminal difficulty 0, non-QBFT/non-Clique client configuration, distinct execution deposit contract address matching the Beacon config, explicitly selected Shanghai/Cancun/Prague/Osaka fork schedule, correct genesis minimum for the actual number of validator keys, custom non-mainnet Genesis fork version, and honest protocol-baseline 12-second slots. These are *preflight schema* checks; they do NOT prove fork schedule parity or runtime compatibility.
- The default `--inspect` path is **read-only**. It returns only PUBLIC hashes and flags `blsPubkeySubgroupAndPossessionVerified=false`, `independentAdministratorsVerified=false`, `permissionlessPublicNetworkReady=false`. It does not create files or launch processes.
- For one actual operator's **owner-generated REAL BLS keys only**, optional `--build-single-operator-lab` verifies a clean exact source SHA and the previously verified official `ethpandaops/eth-beacon-genesis v0.0.8` executable SHA256 `5ee29389cb29e8a1ace8cfc83ff30a1726409152e88cf07681764740ca9244d2`, then runs the **real** `eth-genesis-state-generator beaconchain --eth1-config ... --config ... --additional-validators ... --state-output ...` with an actual, validated PUBLIC validators list. Output is create-only, never overwrites; records SSZ hash and provenance without printing any keys. No use of `--mnemonics`.
- If actual generator errors, the tool fails closed; it never substitutes mock genesis bytes or forged signatures. After successful SSZ generation it still reports **NO real client acceptance, validator activation, secure independent proof, public chain or cross-host networking** until observed separately. The public network release must verify BLS PoP, deposit contract, EL/CL compatibility, actual Beacon slot/finality and outsider P2P.

## Required owner inputs — not invented by source code

1. An independently controlled new **test-only EOA** for execution/withdrawal credentials. The previously reviewed owner-local script `scripts/r20_create_local_operator_withdrawal.sh <exact SHA>` requests the literal `CREATE` and a hidden wallet password. The user previously entered a different value, so wallet creation was correctly refused; **no wallet was generated**. Do not retry it automatically, store password in GitHub or use a Mainnet wallet.
2. Real owner-controlled **Lighthouse BLS validators** generated using the verified v8.3.3 CLI, encrypted keystores and slashing protection. The R20 step probed the actual available flags `account wallet create --name --password-file`, `account validator create --wallet-name --wallet-password --count`, `validator_manager create --mnemonic-path --eth1-withdrawal-address --testnet-dir`. These are only prior observed `--help` outputs, not a verified end-to-end keygen workflow. Do not assume a named generated key is a cryptographically valid validator without checking custody and fork/withdrawal binding.
3. Actual, mutually consistent owner-approved EL `genesis.json` and Lighthouse `config.yaml`. The tool does **not guess a deposit-contract runtime**, fake a deployed deposit contract, or make up scientific network timings. Current Besu genesis documentation lists `depositContractAddress`, `terminalTotalDifficulty` and timestamp-based post-Merge milestones. The official eth-beacon-genesis CLI accepts exact files and public `--additional-validators`. Manual/protocol review is mandatory before real startup.

## Actual CLI workflow after owner has real public data

**Read-only preflight (safe, no key creation):**

```bash
python3 -B tools/sse_pos_genesis_build.py \
  --eth1-genesis /absolute/path/to/public/genesis.json \
  --consensus-config /absolute/path/to/public/config.yaml \
  --contribution /absolute/path/to/operator-local-PUBLIC-keys.json \
  --min-operators 1 --min-validators <ACTUAL_POSITIVE_KEY_COUNT> \
  --single-operator-lab --inspect
```

**Only after real BLS custody and explicit operator approval**, run:

```bash
python3 -B tools/sse_pos_genesis_build.py \
  --eth1-genesis /absolute/path/to/public/genesis.json \
  --consensus-config /absolute/path/to/public/config.yaml \
  --contribution /absolute/path/to/operator-local-PUBLIC-keys.json \
  --min-operators 1 --min-validators <ACTUAL_POSITIVE_KEY_COUNT> \
  --single-operator-lab --build-single-operator-lab \
  --generator "$HOME/.local/share/sse-r19-toolchains/eth-beacon-genesis-v0.0.8/eth-genesis-state-generator" \
  --expected-commit <IMMUTABLE_GITHUB_SHA> \
  --output-dir "$HOME/sse-pos31340-fresh-onehost-public-artifacts"
```

The angle-bracket spans are **placeholders and NOT runnable instructions**: replace them only with actual owner-owned key count and approved SHA. This generator's success is still NOT sufficient to launch a public chain. No key/password/seed/keystore should be put into these public artifacts.

## Native PoS acceptance that must follow

- Hash-pin `genesis.json`, `config.yaml` and `genesis.ssz`; verify deposit-contract address/runtime, EL block0 hash and CL genesis validator root using **actual** client RPC/Beacon API.
- Start pinned Besu26.11.1 and Lighthouse8.3.3 in isolated, unprivileged, resource-limited single-host Linux containers; private Engine JWT, loopback-only Engine API, no public wallet/keymanager; only deliberate controlled P2P publishing. Start a real validator-client process from the owner's actual BLS keys and observe actual signed attestations/proposals, slots and finalized checkpoints. No static-IP or human admission service may be required by the *protocol*, even if limited lab connectivity is not yet public.
- After genuinely working 1-host lab, bring a different VM and the **one external laptop** as real independently networked peers, check actual TCP+UDP ingress, different network paths and recovery. Same owner controlling VM+laptop remains a shared organizational fault domain; do not call it two independent operators.
- A public release requires real externally independent validator custodians and proven public reachability; otherwise mark security acceptance incomplete, never fake identities. The live Beacons deposit contract must accept real 32-worthless-TEST-ETH transactions for NEW post-genesis validators, not just genesis preload.

## Test discipline

`tests/test_sse_pos_genesis_build.py` contains **12** pure Python unit fixture tests of parsing, wrong-chain/unsafe genesis refusal, secret fields, duplicate input, config mismatch, one-real-operator lab flag, and no generator execution in inspect. These synthetic *unit fixture values* are only shape tests and **must NEVER be used in real Genesis**. New R25 test methods are SOURCE ONLY; none is VM-passed until exact Git checkout and operator `python3 -B -m unittest ...`.

Existing old `scripts/sse_pos_launch.sh` is **31339 historical** and must NOT be used for public chain31340: upstream old package emitted known compromised/shared mnemonic; it intentionally refuses public exposure. No main merge or GitHub Actions. This R25 builder provides the actual new Genesis path rather than reusing the compromised historical launcher.
