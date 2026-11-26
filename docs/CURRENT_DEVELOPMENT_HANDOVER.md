# SSE Intercloud — current development handover

Updated 2026-11-25. This file is a living public-only checkpoint, not a release certification. Update it alongside significant code changes and live test results. Never include credentials, encrypted keystore contents, private logs, recovery words or private keys.

## Resume here

Development branch: `feature/r226-adaptive-v2-operator-runtime`.
Latest implementation at this checkpoint: `2ba792017071041fe46ec7cb2d1f9444571597f7` (R358c). Main is not yet the consolidated release. Do not reset the chain, redeploy the marketplace or merge legacy experiments blindly.

Immediate task: on VM4707 and VM4709 fetch R358c and rerun R358 deposit preparation against existing deposit-data.json. Both BLS keys already exist; NEVER regenerate or copy them. R358b failed because eth_getCode returned null on a queried state; R358c tolerates missing historical genesis code only, requires exact pinned runtime at finalized numeric height and latest, and checks finalized anchor. If still unavailable, investigate before staking. Next implement durable deposit intent/reconciliation and actual pending-deposit duplicate protection, fund both deposit EOAs with 32 TEST ETH plus gas, import EIP2335 keystores in pinned Lighthouse and start one persistent VC per host with retained slashing protection. Confirm activation and actual duties. Do not broadcast duplicate deposits or start duplicate signers.

## Non-negotiable requirements

Actual permissionless native PoS blockchain, valueless TEST ETH, real resources and SLA measurements, no synthetic production evidence; arbitrary eligible role combinations; no compulsory private LAN, fixed public IP, individual SSH or central admission; no mandatory remote RPC. One-command installation with multi-role selection and necessary wallet security inputs; optional automatic test funding; persistent services and status/dashboard/logs CLI; public HTTPS role dashboards without browser-side overlay, SSH or forwarding; owner-only privileged operations. GitHub-only source changes; clean consolidated main eventually. No architecture churn. User runs VM commands; connector cannot execute them or work asynchronously. Distinguish committed, regression-tested, and live demonstrated.

## Chain identity and infrastructure

Chain 31340, native Besu + Lighthouse, Electra/Prague genesis, 12-second slots, 32 slots/epoch, standard ungated deposit contract 0x00000000219ab540356cBB839Cbe05303d7705Fa, genesis fork 0xa3400001. EL genesis 0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf; CL genesis validators root 0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd. Public release manifest release/chain31340-public-release.json. One active validator on VM4706 (do not disturb). Native full nodes VM4707 and VM4709 report sync_distance=0, not optimistic, EL online; each 4 cores, 10 GiB available RAM, 90/91 GB free. Local RPC 28545, beacon 25052. VM4707 native containers sse31340-r59-nonsigning-{el,bn}; VM4709 sse31340-r137-node-8be265272c35f3d8c3a0-{el,bn}. Finality lag previously 25–30 minutes, cause not established. Controllerless ZeroTier transport ff2328775f000000; vendor root dependency and external native full sync not fully verified.

## New validators (public metadata only)

Both hosts source ~/sse-validator-source, Python ~/.venvs/sse-validator/bin/python, py-ecc 8.0.0 and requirements installed. R358a generated independent encrypted EIP2335 keys in ~/.local/share/sse31340-validator. Both BLS proofs passed R358b before RPC failure. No deposit broadcast, no VC started.
- VM4707 consumer + planned validator, pubkey 0xaf37194a2e7ca353d45b62fc6a5387c28fe6e68c1578bf24c5de180e7a3aa415f4d7d1e800672bd99aca827cac865c03; withdrawal 0xd74a2abc5a906bafe39471cee222c48bdd62de3f.
- VM4709 provider + planned validator, pubkey 0x989c03ecd4ea3857249a7c446758da693638d4c34209bd92e2b63901298c480aa475eff86a774bc6bd9d782530b28c93; withdrawal 0xbbd4f07be80e1f4c40a1b470a180c0f38352beaf.
- New VM(s) available if necessary; test all roles concurrently, add/remove roles, contention, lease-specific conflicts, accounting, reboot and fresh external onboarding. Multiple VMs are not necessarily independent administrative domains.
- Legacy tools/sse_pos_validator_deposit.py targets chain31339; R358 uses its pure SSZ/ABI functions but explicit live chain31340 checks. Do not use legacy CLI for staking.
- R358a f0bf5be, R358b 1ce7b29, R358c 2ba7920. Independent Lighthouse import still untested.

## Marketplace live evidence

V2 market 0x6C01dBd7aA336a96d8Ab09Ea631E209612224080, ledger 0x6635849b77f037fab611736612d7d3493dc650ff; manifest evidence/r261_vm4707_latest_state_v2_deployment_candidate.json. Deployment block 25339. Lease 1 CLOSED; no more writes for this lease. Real Docker worker VM4714, 500m CPU/256MiB RAM, 8192-round deterministic compute, HTTPS signed reply. Four monitors VM4711/4712/4713/4715 collected 10 samples each, all 40 valid; no votes before deadline. Inconclusive settlement then bilateral allocation of 0.001 TEST ETH to provider; unused 0.0004 monitor reserve refunded consumer. Real canonical successful receipts:
- allocation block33765 tx 0xac8b1ec71c9a400db5c7d0cdefd0ed8808cb3940a245d3a7ba076e8ee0cdaa42
- close block33771 tx 0x37e28fe3b04b25c5201fbdb7b96200eb36f0e767fed3cb8daa67a1ac2e520186
- ledger withdrawal block33774 tx 0x8e71637aebad964713436f17f5a28e76cd6d1ad05b720c0c6e36c0c4f02dc579
- provider withdrawal block33777 tx 0x1e52d790063956ad57b0f548a080c5c3aa6a8e19d6a5837f794328ce79246812
Finality of these receipts not yet rechecked. No independent physical SLA truth or successful quorum settlement demonstrated. VM4707 source ~/sse-r351-source; VM4714 ~/sse-r352-provider-source (old backend requested stopped, not independently verified); monitor source ~/sse-live-monitor-source. Monitor/provider Python ~/.venvs/sse-v2-operator/bin/python. Existing public evidence archives ~/.local/share/sse-live-lease1 on each monitor. R351 local transaction journal ~/.local/share/sse-transaction-journal; never blindly retry unknown sends.

## Recent code and tests

- R349 real sample sessions; R353a archive verification all 4 live archives; R350/R353b-d canonical confirmation policy live read-only depth checks.
- R354a b96a910 live bilateral provisional signatures, successful allocation.
- R355a 6dc0dc6 owner-approved integrated monitor session, 42 regression tests per monitor plus CLI passed all four. R355b aef314d provider deadline guard, R355c 5fc9a0e wire canonical option, 47 provider regressions passed.
- R356a cd653de canonical monitor authorization (27 regressions passed); R356b 276eac9 canonical sampling (19 passed); R356c 4e16ee6 archive audit; R356d ddc9531 integrated vote (42 regressions and CLI passed VM4711). New canonical execution paths not yet live tested; fail closed on reorg, no automatic recovery.
- R357a 57331f4 canonical provider signer, R357b 7cac197 durable reply, R357c 5e66ac2 canonical startup (47 regressions, 3 CLI checks passed VM4714). Separate authentication submission remains; full live path untested.
- Scientific V3 contracts not deployed; R342e bdb1daa9 reported 36 tests and 768 fuzz runs passed. Conditional quorum policy false; evidence-dependent interval allocation, exposure accounting; agents V2 only. Do not claim V3 live.
- OpenTestEthFaucet.sol exists, not deployed/funded. R336 monitor-only installer untested combined; R335 permanent CLI demonstrated; quick tunnel dashboard URL changes on restart; unified multi-role installation and stable public dashboards outstanding. Main stale; release consolidation pending.

## Next release acceptance gates

1. Actual independent validator deposits and activation, native proposer/attestation duties and rewards; avoid duplication and preserve slashing state.
2. Optional self-service TEST ETH faucet funded and deployed; admission not centrally gated.
3. Live new lease with canonical provider/monitor paths, successful on-chain quorum voting and settlement; verify durable journals, reorg behavior, deadline and resource isolation.
4. Persistent multi-role services, automatic install/funding/dashboard, fresh external participant, concurrent roles and reboot tests.
5. Scientific V3 integration and evidence model review; complete tests and clean main, remove obsolete architecture safely. Keep public handover current.

## 2026-11-26 checkpoint (supersedes immediate task above)
R358c passed on both hosts at finalized height 36465. Historical genesis code unavailable, exact current/finalized deposit runtime verified, both BLS proofs and roots verified. VM4707 balance 8999997883882000 wei, VM4709 zero. Neither funded for stake. Proposed target 32.01 TEST ETH per wallet, difference only. R358d 6181fea661ee61ee86903a741cd313a194194559 implements local create-only prebroadcast deposit intent, no auto retry; untested and not global duplicate protection. Next fund from owner genesis treasury using existing local signer, then verify funding and stake. No deposit broadcast yet. No key regeneration.

## 2026-11-26 funding checkpoint (supersedes funding blocker)
R358e 93d5ade2acc905cf2633a8d39b45c9c2db0de2da successfully broadcast both bootstrap top-ups from VM4706 treasury: VM4707 nonce1 tx 0x10079dfa3e21f488f8d578fa78de0cfeb8636973cd1043e7052ccdb10e5f4791 value 32001000002116118000 wei; VM4709 nonce2 tx 0x2b909e96ec833d1624d22c26b63e95d447c505717a16b0117c0835b4e5270f24 value 32010000000000000000 wei. Both independent nodes now report 32010000000000000000 wei balances, deposit proof and runtime verified, finalized runtime height36593, gas estimate85633 at price1000, readyForOwnerDeposit true. Funding receipt finality not yet independently audited. Do not repeat funding. Next run R358d staking once per host using existing application keystores; then reconcile deposit intents and receipts, import keys into pinned Lighthouse and start persistent VCs. No deposit submitted yet. No key regeneration. Local journals do not exclude external duplicate deposits.
