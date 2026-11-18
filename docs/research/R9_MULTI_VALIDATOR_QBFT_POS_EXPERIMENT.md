# R9 — Independent validator blockchain pilot: QBFT baseline and Ethereum PoS comparator

**Status 2026-11-18:** Design and key-free Besu QBFT genesis generator **implemented**, five Python unit tests **actually executed successfully in isolated local Python**; source commits `65777af` and `7302f85`. **No Besu daemon has been installed, no independent validator network booted, no transaction replayed on this new chain, and no rewards measured.** The only currently running funded SSE chain is Anvil ID **31337**, which must remain untouched until lease #1 expiry/refund has been resolved.

## Research question and honest consensus taxonomy

Can a multi-VM consensus network preserve the SSE smart-contract workflow while achieving measured block throughput, deterministic liveness bounds, defined reward incentives, and failure recovery after VM IP changes? Distinguish **chain validators** (agree on blocks) from **SSE SLA monitors** (judge service-specific evidence). A machine could host both but same-machine cohosting confounds independence and CPU observations.

Ethereum mainnet currently uses **Proof of Stake**, not competitive Proof-of-Work puzzle mining. A validator is pseudorandomly selected as proposer for a slot, others attest, and rewards, penalties and possible slashing are protocol-level. **Do not call QBFT mining a PoW race or claim QBFT fixed blockreward is Ethereum staking income.** Bitcoin-style competitive mining is a separate research model and would require a different execution chain for Solidity. Reference: https://ethereum.org/developers/docs/consensus-mechanisms/pos/

## Pilot consensus: Hyperledger Besu QBFT on four **distinct validator VMs**

- New **chain ID 31338** and separate RPC port, never bind or overwrite SSE Anvil 31337 RPC at port8545, receipts, contracts, or key files. The validated code creates **only** a genesis manifest and research plan, not chain runtime.
- Baseline: **4 validator node identities**, **5-second target block period**, **10-second request timeout** (=2× period; per Besu documentation), **15 million block gas limit**, `epochlength=30000` (QBFT proposer/vote resetting parameter, **not** SSE service epoch), and optional **10^13 wei (0.00001 test ETH) block reward** to the proposer (synthetic incentive; do not equate to return on PoS stake). Four validators generally tolerate one unavailable consensus validator; two unavailable halt block production. Cite: https://docs.besu-eth.org/private-networks/how-to/configure/consensus/qbft
- Gas capacity scientifically determined by each EVM transaction's measured `gasUsed`. The earlier SSE Consumer lease-fund transaction used **667093 gas**, so the nominal empty-block 15M-gas capacity is **floor(15,000,000/667093)=22 such transactions/block**, before other overhead and real workloads. Do not present this arithmetic upper bound as measured throughput; `blockperiodseconds` is a requested minimum/target, not guaranteed wall-clock produced-block rate. Also report **encoded block bytes**, since bytes are not directly configurable as a fixed size.
- Baseline tests: **5 seconds and 12 seconds**; **15M, 30M, 60M gas**; offered loads **25/50/75/100/125%**; validator failures **0/1/2**; rewards **0 or 10^13 wei**. Use controlled, paired, seeded transaction trace, **not a blindly multiplied full-factorial**; start with baseline, one-variable-at-a-time comparator, and two outage arms. Warmup 100 blocks, measured 600 blocks per arm, 5 replication trials *when resources/time permit*; report which arms were truly executed vs preregistered only. Parameter selection references Ethereum's 12-second slots and 2026 60M-gas comparator, while 5s and 15M are explicit low-cost pilots, **not independently measured optima**. References: https://ethereum.org/developers/docs/consensus-mechanisms/pos/block-proposal/ ; https://ethereum.org/developers/docs/gas/ .
- Measurements: block arrival timestamps and variance; transactions submitted/included; throughput; gasUsed/gasLimit; encoded block byte size; tx receipt latency p50/p95/p99; proposer share and synthetic reward earned; consensus stalls at >1 offline; signature/seal evidence and heads agreeing; VM CPU/memory; EVM SSE contracts gas.
- Threats: all VMs under one administrator are not cryptoeconomically independent operators; isolated private lab != permissionless safety; synthetic rewards have no market value; no automatic mainnet-style slashing in QBFT; IP discovery/reconnection is a separate identity problem, see ADR-004.

## Generator

New `tools/sse_qbft_lab_config.py` uses only Python standard library. It takes **four DISTINCT validator PUBLIC Ethereum addresses** from Besu keys generated/stored by each validator operator, constructs QBFT genesis `extraData` using Ethereum RLP (vanity, sorted four validators, empty vote, round0, empty seals) and writes `genesis.json` and `benchmark-plan.json` under a pre-existing mode-safe output directory; O_EXCL prevents overwrite. It also allows explicitly approved PUBLIC app EOAs to receive 100 test ETH in genesis alloc. It stores **no private keys**, does not send transactions, and refuses mainnet ID1 and existing Anvil chain31337. This separate generator is not a production chain builder: independently verify chosen pinned Besu binary accepts the genesis, modern fork activation, block rewards, and secure network transport before production-like deployment.

Example after **four fresh validator node keys have been generated on different machines** and public addresses collected:

```bash
mkdir -m 700 ~/sse-qbft-output
python3 tools/sse_qbft_lab_config.py --out-dir ~/sse-qbft-output \
  --validator <PUBLIC_VALIDATOR_1> --validator <PUBLIC_VALIDATOR_2> \
  --validator <PUBLIC_VALIDATOR_3> --validator <PUBLIC_VALIDATOR_4> \
  --fund <PUBLIC_CONSUMER_EOA> --fund <PUBLIC_PROVIDER_EOA>
python3 -m unittest discover -s tests -p test_sse_qbft_lab_config.py -v
```

**DO NOT feed the placeholder angle-bracket strings to a shell.** Supply four actual node addresses and real EOAs. Each validator must be assigned to and owned by its intended VM; no duplication of a node private key. Never commit node keystores; never send private key material to ChatGPT, GitHub, or a shared dashboard. Pin software versions, instance types, CPU/memory, per-host machine identity and genesis hash. Generated QBFT genesis must be identical across validator VMs. Restrict RPC to trusted local or authenticated overlay access; P2P peers may use an authenticated mesh.

## True Ethereum PoS comparator

The independently documented comparator is a **Kurtosis ethereum-package** network with separate execution client (Geth) and consensus/validator client (Lighthouse), and genesis-funded validator keys. Start with 4 participants hosting 16 validator keys (4 per host, if supported/validated in deployment), **12 seconds per slot**, **32 slots per epoch**. Track block proposer per slot, attestations, head/finality checkpoints, rewards, missed slots/penalties and at least one validator outage. Reference: https://geth.ethereum.org/docs/fundamentals/kurtosis/ ; https://github.com/ethpandaops/ethereum-package . **Kurtosis on one Docker host creates multiple clients but does not by itself prove four independent physical VMs**; a multi-host orchestration plan is required before claiming spatial independence or IP failover.

## Critical-path implementation / acceptance stages

1. **First** preserve current Anvil: expire pending assignment #1 only after an actual current-time block moves beyond `requestedAt+3600`, then Consumer-owned `closeLease(1)` and check/withdraw unused escrow. Preserve the real receipts from blocks 25/26. Monitor4699 remains lost and cannot sign a normal requestExit.
2. Reconnect healthy app nodes 4700–4703 and provider4696 to Anvil4695's relocated IP `10.50.56.14` using original VM-pinned SSH host key `SHA256:Xw3anupwwpofutE6sm0c8sRHi1NjDHALCaLWfK17LUA`, NOT an arbitrary changed IP key. The four surviving monitors are still the only recovered online EOA owners; the old on-chain lost EOA remains bonded and eligible, so fresh lease may require seeded no-show replacement or new audited monitor-liveness contract upgrade.
3. Provision **four dedicated validator hosts** or explicitly document role cohosting when isolated machines unavailable. Install/pin Besu version and generate separate validator private/public node keys on each host. Apply the key-free genesis generator, verify identical genesis hashes, create P2P enodes, validated firewall/overlay/peer connectivity and full restart-persistence.
4. Run chain31338 on separate ports, test 4/4 agreement and rewards, kill one and then two validators, confirm expected continued/frozen block production and recovery. Validate *real* gas/tx metrics and genesis fork support before migrating a copy of the SSE contracts and a **new** request to chain31338. The old Anvil lease cannot be transported or replayed to a new chain.
5. Then run the PoS comparator and present security/performance/reward tradeoffs with statistical uncertainty and genuine multihost caveats.

**Status of live deployment:** R9 consensus extension is implemented as configuration/source and tests only; active user-facing implementation remains the existing Anvil/SSH/Provider/Monitor fleet. Do not rewrite original R/P phase percentages until real acceptance evidence exists.
