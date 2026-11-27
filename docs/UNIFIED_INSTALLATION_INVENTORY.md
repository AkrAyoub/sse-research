# Unified installation inventory and release acceptance gate

This inventory records accumulated development operations that a clean installation must replace. It is a working inventory, not a claim of complete automation. Review actual installer scripts and fresh-host evidence before marking items complete.

## Installation stages

| Stage | Required automation | Current evidence / gaps |
|---|---|---|
| Host preflight | Supported OS/architecture, storage/RAM/CPU checks, outbound connectivity, required privileges, free ports, clock sync | Existing R147 and R336 component installers; consolidate |
| Software | Git, Python, isolated pinned dependencies, Docker engine and owner access when required, CA certificates, native client images, ZeroTier, HTTPS tunnel executable | Component installs/manual preparation; pin and verify distribution artifacts |
| Source | Public release source or signed artifact, exact version, integrity checks, stable installed paths, upgrade/rollback | Development branch/detached commits are not distribution mechanism |
| User lifecycle | Private configuration/data directories, systemd user manager, linger enabled, readiness polling, reboot recovery | R394 console live tested; VM4707 Linger=no, must correct |
| Network | Native peer discovery, dynamic addresses, outbound NAT traversal, optional overlay, bootstrap discovery and identity persistence | ZeroTier controllerless network tested; vendor root dependency and unrestricted independent Internet participation still need release assessment |
| Native full node | Original chain31340 EL/CL genesis, pinned Besu/Lighthouse, ports, JWT generation, P2P identity, sync and finalized chain verification | Existing original-chain node scripts; integrate, avoid regenerating genesis |
| RPC | Local native RPC or optional pinned TLS relay adapter, persistent unit, chain/genesis checks, method allowlist, endpoint discovery | R299/R361a tested; fixed development relay not acceptable as mandatory dependency |
| Application wallet | Owner-local encrypted keystore creation/import, address discovery, private permissions, secure recovery guidance | Existing wallet helpers; eliminate VM names and addresses from installer |
| Native validator | Owner BLS wallet and validator keys, withdrawal credentials, actual deposit funding, deposit verification, activation tracking, slashing protection, persistent VC, exit/recovery | R27/R358 paths; activation and duties need current verification; never redeposit or duplicate signer |
| Funding | Optional real TEST ETH faucet, balance verification, no genesis key distribution | Faucet contract exists but deployment/funding outstanding; no automatic admission authority |
| Provider | Docker workload image build/pull by digest, CPU/RAM limits, actual resource discovery, signed profile, TLS cert/key, endpoint publication, backend/frontend, owner consent for signing, persistent operation | R234/R304/R368 live; foreground V3 signing and fixed dev cert are not final installation |
| Consumer | Actual resource/policy discovery, request, choose bid/fund, epoch lifecycle, response evidence, settlement, refunds | R366/R371/R377 live; admission-only experiment is not production failure handling |
| Monitor | Register/bond, assignment discovery/confirmation, actual pinned TLS probes, evidence archives, vote/reward, abstention on uncertainty | R370/R377 live; automated persistent multi-lease discovery and qualified negative evidence outstanding |
| Marketplace | Verify actual deployment and runtime, contract/ledger addresses from authenticated release metadata, preserve escrow and transaction journal | R362 live; exact compiled runtime parity outstanding, development addresses hardcoded |
| Dashboard | Role-aware V3 status, bids, explorer, scientific accounting, unsigned forms, owner-local transaction authorization | R384–R394 live data/forms/service; remote owner authorization incomplete |
| Public HTTPS | Automatic public URL, stable discovery after restart, public-only listener, certificate/identity, rate limiting, verified access without SSH/overlay browser | Quick tunnel previously tested, changing URL and durable discovery unresolved; stable hostname requires provider/domain provisioning |
| Owner controls | Authenticate owner, role-specific permission, bounded spending, safe disconnect/reconnect, independent recovery, audit, no secret exposure | R381 actual V3 interruption tested; other roles and remote integration outstanding |
| CLI | Installed sse status/dashboard/logs, role management, health and URL discovery, works in new shells | R335 prior CLI; integrate V3 service |
| Release | Clean main/release, exact dependency pins, docs, test suite, clean-room independent VMs, reboot/logout verification, real multi-role workflows | Outstanding |

## State and security invariants

- Installation must be idempotent, detect existing state, preserve keys, genesis, validator slashing databases, journals and evidence. Never reset an existing network or duplicate validator signing.
- Role selection and explicit wallet/security decisions are legitimate user interactions. Do not request manual port numbers, VM names, peer addresses or deployment addresses in the normal installation flow.
- Native consensus and application roles are independent and may coexist. No mandatory hosted RPC or central admission.
- Do not store passwords in unit files, command-line arguments, environment variables, public dashboard or logs.
- Funding, deposits, bond, escrow, signing and fault actions require appropriate owner authorization; installer must not silently spend funds.
- Do not claim unattended reboot signing if the chosen wallet protection requires unlocking after boot; design and document explicit security tradeoff.
- Distinguish successful HTTP health, chain sync, finality, role eligibility, actual service and conditional SLA evidence.
- Fresh demo chain vs preservation of existing chain is an explicit release decision. Back up genesis, wallets, slashing databases and evidence before decommissioning development hosts.
- Final acceptance requires a newly provisioned host with no prior project setup. Install from release using documented single command; verify after logout/reboot, then demonstrate actual transactions and service across independently connected hosts. Do not rely on development paths or copied secrets.

## Recorded R394 result

VM4707: enabled/active sse-v3-console.service, HTTP startup retry successful, finalized height 38289, 3 accounted epochs, mask 7/4/6 respectively, exposure 1e15 wei, available 1e15, provider credit 2e15, conservation true. Linger=no: logout/reboot persistence unverified. Existing chain31340 is retained. Exact runtime parity remains false.
