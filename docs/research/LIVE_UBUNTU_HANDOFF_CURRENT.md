# SSE Blockchain Research — CANONICAL LIVE UBUNTU HANDOFF

**As-of:** 2026-11-17, after successful on-chain Consumer request #1 (block 12) and Provider bid (block 13).  
**Repository:** private `AkrAyoub/sse-research`. **Active working branch:** `research/r7-vm-role-operator-no-ci`.  
**Purpose:** restart work immediately in a new ChatGPT conversation with **no VM re-provisioning, no repeated blockchain deployment, no wallet overwrites, no accidental request duplication**. Append a checkpoint and update the current-state sections **after every new operator result or implementation change**, then commit to this same file. This is a living handoff, not a fixed November 17 retrospective.  
**Trust:** All remote-VM observations below are copied from operator-pasted console evidence unless specifically labeled code inspection, offline test, or pending. Do not claim a command passed merely because it was suggested. No private keys, passphrases, GitHub deploy keys, or runtime signer-file contents may be committed.

## 0. NEW CHAT: READ THIS FIRST / EXACT CONTINUATION POINT

> **LATEST OPERATOR OUTPUT — 2026-11-17, after request/bid read check:** Provider VM `ayoubakrvm4696@10.50.56.2` reports `sse-compute-lease01` **Up 45 minutes**, Docker container `57e2f3e4ab64`, image `c2aba72e4543`, loopback publish `127.0.0.1:8877->8877/tcp`; `curl --noproxy '*' --max-time 3 http://127.0.0.1:8877/healthz` returned `{"localComputeWorker":true,"ok":true,"onChainAuthenticated":false,"service":"sse-local-challenge"}`. This confirms official-port HTTP health, **not** signed service/delivery or new launcher source deployment. **FIVE NEW MONITOR VM SHELLS CREATED/IDENTIFIED ONLY** (see §2); no source, signer, RPC, bond or monitor service installed on them yet. The known committee `candidateCount=1` is unchanged pending registrations. Next: install authenticated Provider/Consumer controller-to-Monitor SSH provisioning authorized key with restricted `from=10.50.56.8`, pin each host key against portal output, batch first-install release handoff, securely bootstrap monitor wallet/SSH RPC tunnel and bond. No new blockchain transactions in this latest user output.


> **LATEST READ-ONLY CHAIN CHECK — 2026-11-17 ~14:03 UTC:** From Consumer/controller VM `ayoubakrvm4693@10.50.56.8`, `cast call` verified `OpenResourceBoard.requests(1)`: Consumer `0xCC595b02Ff79315E5036f3B978bA081600C8201B`, resource hash `0x7182ffec1ceba3c569714de05ca441bdc17b114c7ae98e9f91fcb9e6a858abf0`, SLA hash `0xffc573392c83037e18907bfaea6234dfc6b2d58081f3e1c21950f00108d1f147`, maxEpochFeeWei `100000000000000`, biddingClose **`1794923778` (2026-11-17T13:56:18.000Z)**, `selected=false`; `bidCount(1)=1`; `getBid(1,0)` gives Provider `0x5B048852F909f47FfEb94B288bAc1a243eE54255` and fee `25000000000000` wei; `OpenMonitorCommittee.candidateCount()=1`. **Bid index 0 CONFIRMED**, not just presumed. No evidence of lease funding. Bidding close does not invalidate an existing unselected request; selection is allowed after close, conditional on >=4 eligible monitors. The co-located monitor on Consumer VM cannot be called independent for this lease. Do not attempt to fund at candidateCount 1.


**Observed as-of last console transcript:**

1. On VM **4693** (Consumer) a real request #**1** was mined on Anvil 31337 at block **12**, tx `0xfad7db198829391c6f46309c7ada984830cbb407d6622f27fa32e574f4784427`. Consumer used locally encrypted wallet `0xCC595b02Ff79315E5036f3B978bA081600C8201B`; CLI status `MINED_UNFINALIZED`. The request committed the manifest hashes in §6, with maximum **100000000000000 wei/epoch**, and a **600-second** bidding window. Its exact `biddingClose` is now verified **1794923778** (2026-11-17T13:56:18.000Z); an earlier Provider read showed **387 seconds remaining** at that moment, `selected=false`. This is historical; selection must check on-chain timestamp.
2. On VM **4696** (Provider) an actual bid on **request 1** was mined at block **13**, tx `0xf62541423d11d5adf1e3ed8f3c248c4b9a40c3d6d14dfb1d8573ee67d9da7c53`, fee **25000000000000 wei/epoch = 0.000025 ETH**. The signer is locally encrypted Provider wallet `0x5B048852F909f47FfEb94B288bAc1a243eE54255`. CLI `MINED_UNFINALIZED`, exit code 0. Temporary `/run/sse/provider-market-01.key` was deleted afterward by the displayed command. **Bid index 0 is independently confirmed** by read-only `bidCount(1)=1` and `getBid(1,0)` matching Provider and 25000000000000 wei; `selected=false`. See newest check above.
3. **No bid selected, no lease funded or accepted, no committee elected, no epoch admitted, no cross-VM EIP-712 delivery, no monitors voted, no settlement payout, no final independent SLA claim** as of these transcripts.
4. **CRITICAL BLOCKER FOUND BY SOURCE INSPECTION:** `OpenResourceBoard.chooseBidAndFundLease` invokes `SSESettlement._createLease`, which invokes `OpenMonitorCommittee.requestAssignment`. This **reverts `InsufficientCandidates()` unless at least four eligible bonded, distinct monitor addresses** are active after excluding Consumer and Provider. **Only one candidate is known registered**: co-located Consumer/Monitor on VM4693, which must NOT monitor its own Consumer lease. Therefore **DO NOT run funding transaction now**. Need at least **4 additional independently operated monitor VMs with bonded monitors**; 5+ outside this Consumer host is preferable for standby/no-show resilience. Distinct Ethereum EOAs alone do not establish independent operators. No way around research-quality independence by creating fake monitor wallets on same VM. `requestResource` bidding deadline is only the **minimum time after which selection is allowed**; the contract has **no post-close expiration on an unselected request**. Once enough eligible monitors exist, request #1 can still be selected/funded unless state otherwise changed. **Do not create a duplicate Consumer request just because the bidding window closed.**
5. Next immediate actions: (a) read-only verify chain `request #1, bids, active candidates, block`; (b) provision *new independent monitor hosts* efficiently using secure first-install handoff and distinct encrypted wallets; (c) verify the Provider's official worker later reaches HTTP 200 and update/install the committed Docker fixes safely; (d) fund only after strict eligibility and approved endpoint checks; (e) Provider accept, delayed-block entropy committee, four monitor confirmations, Consumer epoch admission, signed Docker-based direct exchange, monitor evidence/votes/quorum, financial settlement; (f) evaluate end-to-end, formal R/P acceptance; (g) later wipe/redeploy a **clean automated research release** after code freeze. Maintain exact existing source tree/phase tracker, not a made-up alternative tracker.

**Anvil contract addresses and role-VM identities are listed next.**

## 1. High-level objective, research boundaries, and design

Project SSE: blockchain-backed resource service marketplace with independent Consumer, Provider, bonded monitoring committee, Ethereum smart contracts, direct authenticated SLA workload execution, evidence policies, escrow/settlement, node-specific UIs and global read-only observer. Future goal: scientifically defensible, independently reproducible multi-VM trials and paper, not merely toy transactions. Preliminary work includes EIP-712 typed evidence and work orders, finite observation/uncertainty model, fairness/accounting constraints, failure-aware aggregation, evolving committee randomness/selection ideas and workload-specific evidence. Validate *what evidence proves*; never equate wallet signatures, success hash, timeouts or Docker config with verified physical service/delivery time or Ethereum PoS finality.

Choices/limits:
- **Anvil** is a private/local EVM test blockchain, not public Ethereum, VRF coordinator or production L1. Real chain 31337 transactions over SSH-tunneled loopback RPC. `sse-anvil.service` on blockchain VM.
- **Contracts already deployed**; do not run fresh `forge script` or redeploy during this incremental experimental lab. Contract state should survive via Anvil managed state, but reboot/restore persistence acceptance remains to be tested.
- **On deployed committee** future-block delayed entropy mode is enabled (4-block delay), NOT a genuinely unbiased/verifiable VRF. `OpenMonitorCommittee` also contains optional RSA/global-roster research code, but those modes **were not enabled** and cannot be retroactively enabled on this bound/registered deployment. WP09D/E drafts are not production features on this chain. A quorum of **3 matching votes from four selected monitors** is conceptually relevant to sealed epoch evidence, but four distinct eligible selected and confirmed monitors are required before starting a valid epoch; 3 votes do not excuse 4 confirmations. Failure votes do not automatically prove physical SLA violation.
- **R7 Docker service**: deterministic SHA-256-chain 8192-round workload, immutable image ID in a V2 resource profile, local Docker CPU 500 milli and RAM 536870912 bytes; signed Provider service must inspect container and independently compare actual result before signing. Docker daemon itself is a highly privileged local trust boundary.
- **Network**: SSH authenticated host-key-pinned private tunnels and loopback services. Tailscale Serve private HTTPS/ACL integration is a future task. A `http://127.0.0.1:8881` endpoint commitment must be interpreted carefully: loopback on Consumer and Provider are **different** hosts; a Consumer-initiated authenticated tunnel to Provider `8881`, plus exact matching origin validation, needs engineering and an approved key that permits port-forwarding. Provisioning SSH key on Provider was installed with `restrict` (disallows forwarding). Do **not** expose `8881` or `8545` to public interfaces, change on-chain endpoint hash, or misstate cross-VM service availability.
- **Monitoring**: 4-slot selection and 3-vote threshold. Consumer and Provider conflicts excluded by contract wallet identities, but a Consumer/Monitor colocated on the same VM cannot independently monitor Consumer's own lease. Need >1 truly independent monitoring host/operator and collusion/network partitions/failure truth testing.

## 2. Existing VM inventory — exact identity, access, roles

**IMPORTANT:** Two *different* VMs have the **identical portal hostname** `patch-dil-template-s2-service-base-g68-20260628-044954`. Never decide destination by hostname alone. All command instructions MUST state portal username and private IP before each block.

| VM | Portal Linux username | Internal IP | Hostname | Roles | State |
|---|---|---|---|---|---|
| Original Participant VM | `ayoubakrvm4693` | `10.50.56.8` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Consumer + Monitor + Observer, source/controller | Running; existing wallets and Anvil tunnel |
| Blockchain VM | `ayoubakrvm4695` | `10.50.56.20` | `patch-dil-template-s1-service-base-g68-20260628-050503` | Anvil EVM RPC | Running systemd Anvil |
| Provider VM | `ayoubakrvm4696` | `10.50.56.2` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Provider + Observer | New signed-source-handoff repo and encrypted Provider wallet; Docker and UI active |
| Monitor M1 (new) | `ayoubakrvm4699` | `10.50.56.14` | `patch-dil-template-s1-service-base-g68-20260628-050503` | Intended Monitor + Observer | Identified only; no SSE install/wallet/RPC/bond yet |
| Monitor M2 (new) | `ayoubakrvm4700` | `10.50.56.18` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Intended Monitor + Observer | Identified only; no SSE install/wallet/RPC/bond yet |
| Monitor M3 (new) | `ayoubakrvm4701` | `10.50.56.21` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Intended Monitor + Observer | Identified only; no SSE install/wallet/RPC/bond yet |
| Monitor M4 (new) | `ayoubakrvm4702` | `10.50.56.22` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Intended Monitor + Observer | Identified only; no SSE install/wallet/RPC/bond yet |
| Monitor M5 (new; standby target) | `ayoubakrvm4703` | `10.50.56.23` | `patch-dil-template-s2-service-base-g68-20260628-044954` | Intended Monitor + Observer | Identified only; no SSE install/wallet/RPC/bond yet |

VM4696 independent identity evidence: `whoami=ayoubakrvm4696`, `eth0=10.50.56.2/24`, Docker **29.1.3**, Ubuntu **24.04.4**, Python **3.12.3**, Git **2.43.0**, `python3-venv` installed, 4 vCPU/11 GiB/96 GB root. Its Ed25519 SSH host key verified **on Provider VM itself and from VM4693**: `SHA256:mRUhzUOtlxE1Ug8mRYJ0CB5BQzzGQ0PWikY0bT+GARs`. Provider hashed machine ID prefix: `80c52466654f77fa`. Its **persistent SSE nodeId**: `sse-81322ab79a2ee6a795952306` (not duplicate Linux hostname).

VM4693 earlier SSH host fingerprint `SHA256:HulbLhb3yurT0jsL0m/44mzvzIngekxtxryKifEq4PQ`, machine-id hash prefix `aeeef7ef0fa61d4d`. These are **VM4693**, NOT VM4696. VM4695 Anvil host SSH fingerprint as independently pinned on Provider: `SHA256:Xw3anupwwpofutE6sm0c8sRHi1NjDHALCaLWfK17LUA`. Reverify host keys when provisioning any NEW machine.

Environment: private subnet `10.50.56.0/24`; SSH reachability proved VM4693→4696; GUI/console accessed via portal gateway. Portal paste occasionally corrupts long pasted commands or Python heredocs (observed `PYint(...)`), and Ctrl+C sometimes does not interrupt portal session; use short independent commands and `timeout` for probes, and new SSH terminal when stuck. Distinguish transient service startup races from persistent failures. **Do not run arbitrary OS upgrades/reboots during unfinished Anvil lab acceptance.**


**Monitor fleet identification, directly observed from each portal SSH shell (2026-11-17)**. These are **SSH SERVER** host fingerprints (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`), not client keys, and 16-character prefixes of SHA-256 hashes of `/etc/machine-id` are NOT secrets or full host identifiers. All five are Ubuntu24.04-template hosts on private subnet, Python **3.12.3**; portal shell identity and address were independently printed:

| VM user | IP | SSH ED25519 server fingerprint (SHA256:) | Machine-id SHA-256 prefix |
|---|---|---|---|
| `ayoubakrvm4699` | `10.50.56.14` | `9V9VyYCuS33nJZlU0oUIr5IgergeGNrfRApBGnkcrnM` | `b4c5debb80b323d5` |
| `ayoubakrvm4700` | `10.50.56.18` | `OvcWc98T6/JO6IfsE9I8UwWQ+WSbf8tBTAg0gW77ojo` | `e121d93c1cd74dce` |
| `ayoubakrvm4701` | `10.50.56.21` | `OujgGrcvNsylX8E4lYLAR7/Dj3o3pU+gUz72mATgDT4` | `4663fc11e4957e60` |
| `ayoubakrvm4702` | `10.50.56.22` | `BPAoYECnfaJg8GTPWkl/Agimz4EehBT04/+a/4390gA` | `03a1e26afa105310` |
| `ayoubakrvm4703` | `10.50.56.23` | `YQYN8sJsKQ0kczgPKcLY2vp6WHoYshZNE0QI3YGBVhA` | `e24d48d10763954b` |

**Interpretation:** separate VM/SSH/Machine identities support infrastructure separation, not independently controlled administrative organizations; single portal owner/operator may have control over all machines. The scientific claim of operator independence remains unproven and must not be inferred merely from five VMs.

## 3. Repo versions, worktrees, history and sources of truth

Private GitHub: `AkrAyoub/sse-research`. Primary active lab-engineering branch `research/r7-vm-role-operator-no-ci`. **The live branch advanced AFTER Provider install**; newer files do not magically update Provider VM.

- VM4693 main checkout `/home/ayoubakrvm4693/sse-research`, historically branch `research/r6-ubuntu-isolation-acceptance-no-ci` at approximately `a6f8a69`. It contains Python virtualenv `.venv`, Foundry in `~/.foundry/bin`, and persisted public contract configuration `.local/live-chain/contracts.env`.
- VM4693 separate Git worktree `/home/ayoubakrvm4693/sse-r7-onboarding`, initially `5d2985b`, then fetched and detached at `c9c3afa3b9c3016c9e4ca5a7ad7437e8959e850c` for first Provider transfer. **It may not be at newest remote R7 HEAD.** For new updates use `git fetch` and source inspection; do not trample local modifications.
- VM4696 code `/home/ayoubakrvm4696/sse-research`, installed as **clean, shallow verified Git checkout at** `c9c3afa3b9c3016c9e4ca5a7ad7437e8959e850c`. Python venv `.venv` and pinned `requirements.txt` dependencies installed. It intentionally has **no GitHub credentials / remote authority**. Its role manifest is persistent in `~/.local/share/sse-lab/roles.json`, wallet encryption file `provider.json` and node-binding file `node-binding.json`. Do NOT rerun `init`.
- **Source corrections committed to remote R7 branch AFTER VM4696 checkout:** `Dockerfile.sse-compute` chmod after `COPY` before nonroot `USER`, commit `3dd2129`; regression for file readability `f74f2bc`; launcher HTTP readiness verification in `tools/sse_docker_worker_launch.py`, commit `453b867`; launch regression tests `9b72c72` and syntax correction `6f036a6`. Master tracker subsequent commits `fc09eae`, `13664f3`, `22f4935`. **New source has not yet been installed/tested on VM4696**; source-level tests added but the new test suite itself has not been executed there. Do not claim it is accepted. Do not re-run `sse_lab_release_handoff.py --apply` on existing Provider repo: receiver explicitly refuses existing `sse-research` checkout, correctly protecting identity/state.
- Source reading: `tools/sse_vm_role_setup.py`, `tools/sse_lab_release_handoff.py`, `tools/sse_node_marketplace.py`, `tools/sse_sla_build.py`, `tools/sse_docker_worker_launch.py`, `tools/sse_compute_docker.py`, `tools/sse_docker_sla_runner.py`, `tools/sse_chain_read.py`, `services/role-agent/agent.py`, `services/provider-agent/direct_work_service.py`, `services/provider-agent/compute_http_service.py`, `contracts/OpenResourceBoard.sol`, `contracts/SSESettlement.sol`, `contracts/OpenMonitorCommittee.sol`, and the research guide `docs/research/R7_PINNED_DOCKER_SLA_RUNNER.md`.
- Formal original project progress source: `docs/research/MASTER_TRACKER.md` + `docs/research/PHASES_TRACKER.csv`. Historical phase percentages **engineering 309/1200 ≈25.75%, research 180/700 ≈25.71%, overall 489/1900 ≈25.74% (~26%)**. Do not create substitute stages or inflate without evidence. See §10.
- Older checkpoint `docs/research/R5_R6_NOV17_LIVE_UBUNTU_CHECKPOINT.md` is intentionally **historical and partially obsolete**: it says the Provider was not yet installed; **this current handoff supersedes it** on those facts, while the old snapshot remains valid for its own time.
- GitHub issue **#28** `https://github.com/AkrAyoub/sse-research/issues/28` tracks the real R7 Docker permission/early-exit/readiness regression and acceptance gaps. Keep it synchronized with subsequent operator output.

## 4. Real Anvil on-chain deployment (DO NOT REDEPLOY)

- Anvil VM4695: `sse-anvil.service` enabled/active, private loopback RPC `127.0.0.1:8545`, chain ID **31337** (hex `0x7a69`), Foundry/Anvil **1.9.0**. State at `/var/lib/sse-anvil/state.json`. Block height now at least **13**. No public mainnet/testnet ETH; all amounts are experimental Anvil wei.
- `OpenMonitorCommittee` / `COMMITTEE`: **`0x5FbDB2315678afecb367f032d93F642f64180aa3`**. Min registration bond **1000000000 wei (1 Gwei)**; exit delay **86400 sec**; randomness timeout **3600 sec**, committee size **4**, delayed-block-hash entropy enabled. Distinct active EOA candidate count last observed **1**, not independently verified after block 13; can recheck.
- `SSESettlement` / `SETTLEMENT`: **`0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`**, bound to Committee + ResourceBoard. It enforces EIP-712 domain, escrow accounting, lease lifecycle, 4 confirmations, evidence voting and time windows.
- `OpenResourceBoard` / `BOARD`: **`0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`**, bound to Settlement. Methods `requestResource`, `placeBid`, `bidCount`, `getBid`, `requests`, `nextRequestId`, `chooseBidAndFundLease`.
- Known Anvil unlocked public **DEV-ONLY** funder EOA: `0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266`. Never use this wallet for production, Sepolia, private-file secrets or claim public funds. Lab funding should guard chain ID 31337.
- VM4693 monitor **`0xCa8978d722fAe6738D00cDE24961F7C4240B42e3`**, bonded 1 Gwei and active on chain at block **10**, tx **`0x2d6c57fe440a0147bb4d51e2badf1da23ba0aa2f16df7f0bd6cf95240daaf741`**. Since monitor and Consumer are on SAME VM/operator, do not count it as independent for this Consumer lease, even if contract excludes only consumer EOA.
- VM4693 Consumer **`0xCC595b02Ff79315E5036f3B978bA081600C8201B`**, encrypted at `~/.local/share/sse-lab/consumer.json`; previously funded.
- VM4696 Provider **`0x5B048852F909f47FfEb94B288bAc1a243eE54255`**, encrypted `provider.json`; funded **0.02 ETH** by Anvil dev funder tx **`0xa9fd17cdd72c2050e1ab0ce1aee970b8579ca7632aa1a227a1206cc45d5676e6`**, mined **block 11**, status 1. Provider read-only role status returned `chainId=31337` and `balancesWei.provider=20000000000000000` **before bid gas**. Never fund again without checking balance.

**Authoritative public env on VM4693:** `~/sse-research/.local/live-chain/contracts.env` with `CHAIN_ID=31337` and above addresses. A fresh Provider install does **not** automatically have this local file. Provider UI systemd has corresponding explicit public address env vars.

## 5. SSH, chain RPC, role UI and security setup actually performed

### VM4693 → VM4695 Anvil
Previously verified Anvil host key, supervisor `sse-rpc-tunnel.service` active/enabled. Private SSH port forwarding maps **VM4693 local `127.0.0.1:8545` → VM4695 local `127.0.0.1:8545`**. VM4693 remote RPC verification returned `eth_chainId=0x7a69`, contracts deployed and bound, and real funding/monitor/request txs mined. Do not expose raw RPC to public network.

### VM4693 → VM4696 private code release
On VM4693 created dedicated Ed25519 SSH private provisioning key at `~/.ssh/sse_vm_provision_ed25519`, **NEVER share contents**; Provider independently verified Ed25519 fingerprint `mRUhz...` and VM4693 pinned it in `~/.ssh/known_hosts`. Public key (not secret) starts `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK/851YudMkf77lEOSoJ1qMxhZFCmJw7k/NmwBkEpXMP`. On VM4696 added to `~/.ssh/authorized_keys` restricted to **`from="10.50.56.8",restrict`**. VM4693 verified `ssh -T -i ... -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes ayoubakrvm4696@10.50.56.2 'whoami'` → correct user. Actual secure handoff from VM4693 clean pinned R7 worktree to new VM used `tools/sse_lab_release_handoff.py --source ~/sse-r7-onboarding --revision c9c3afa... --dest-ip 10.50.56.2 --dest-user ayoubakrvm4696 --ssh-key ... --roles provider,observer --apply` → **`VERIFIED_PRIVATE_VM_RELEASE_INSTALLED`**, archive SHA-256 `b9df7255833530bc450537a333b017e60faab542989571bfaeccb70051606c0a`. Receiver declared `pythonEnvironmentInstalled:true, walletKeysInstalled:false, githubCredentialsInstalled:false, roleActivated:false` (correct at that point).
### VM4696 local role
`python tools/sse_vm_role_setup.py init --roles provider,observer` prompted twice for a 16+ character secret and generated encrypted Provider wallet `0x5B0488...`, unique `nodeId=sse-81322ab79a2ee6a795952306` and owner-only local files; `status` succeeded. A first attempted init failed `ModuleNotFoundError: Crypto`, then `python -m pip install -r requirements.txt` showed dependencies including `pycryptodome==3.23.0` installed; subsequent init succeeded. Don't repeat init.
### VM4696 → VM4695 chain
Separate Provider Ed25519 key `~/.ssh/sse_rpc_tunnel_ed25519` (DO NOT share private key), public starts `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPs5n2PSxt8nNoq+iZZpLWdB6IRX44RVBpi394GXQvNU`. Provider pinned Anvil SSH host fingerprint `Xw3anup...`. Anvil VM4695 authorized only from `10.50.56.2` with `restrict,port-forwarding,permitopen="127.0.0.1:8545"`. Provider `/etc/systemd/system/sse-rpc-tunnel.service` enabled/active, `User=ayoubakrvm4696`, `ssh -NT -L 127.0.0.1:8545:127.0.0.1:8545` using strict host key. First immediate `curl` refused while starting; **subsequent** `python tools/sse_vm_role_setup.py status --rpc-url http://127.0.0.1:8545 --chain-id 31337` showed correct chain and 0.02 ETH. Later listener `127.0.0.1:8545` confirmed and a real Provider bid mined through it.
### Provider + Observer console
`/etc/systemd/system/sse-provider-role-agent.service` enabled/active, starts `.venv/bin/python services/role-agent/agent.py` as Linux user `ayoubakrvm4696`, loopback host `127.0.0.1`, port `8765`, `SSE_NODE_ID=sse-81322ab79a2ee6a795952306`, `SSE_ROLES=provider,observer`, revision c9c3afa, chain/address env variables. Systemd hardening includes `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `UMask=0077`. `curl http://127.0.0.1:8765/healthz` succeeded with `ok:true, chain_verified:false`. `curl .../v1/status` succeeded with `software_running:true`, `blockchain_synced:null`, `provider_capacity_verified:null`, correct roles/node ID. `http://127.0.0.1:8765/ui` is a **read-only draft/preview UI**, not a connected trading UI and it cannot broadcast transactions or attest workloads.
### Docker group
Docker Engine `29.1.3` running. Initially nonroot `docker info` yielded permission denied; experimental workaround `sudo usermod -aG docker ayoubakrvm4696`, then `sg docker -c 'docker info ...'` succeeded `linux / 29.1.3`. Membership in Docker group effectively grants root-level host capabilities; for final research deployment use restricted daemon access/rootless or a tightly controlled launcher and document threat boundary.

## 6. Docker worker: exact failure, fix, manifest hashes and observed results

Original source `Dockerfile.sse-compute` uses `python:3.12-slim`, installs `pycryptodome==3.23.0`, copies `tools/sse_challenge.py`, `tools/compute_workload.py`, `services/provider-agent/compute_http_service.py`, then switches to `USER 10001:10001`. VM4696 built tag `sse-compute:r7`; **original BAD image ID** `sha256:c513259296110d080221d610e481fa336eaf5b0219fd1937883bcc2f87f5888f`. Its Docker worker launched with `--detach --rm --log-driver none`, 0.500 CPU, 512MiB RAM, 512MiB swap limit, PIDs ≤64, readonly root FS, dropped all caps, no-new-privileges and built-in seccomp, local bridge and loopback publish `8877:8877`. Launcher briefly reported healthy Docker *inspect* and container ID `1bc79a9d56281b9f33a94bc0441d38f380dec0d4f5a5a808c764f84002c17ebc`, but `curl 127.0.0.1:8877/healthz` refused repeatedly; another portal terminal found **no container**. `--rm` automatically removed the exited process; no logs under `--log-driver none`.

Diagnosed with `sse-compute-debug` image c513 on host port 8878, retained logs `--log-driver local`, same security limits; `docker inspect` → **`Status=exited ExitCode=2 OOMKilled=false`**; log: **`python: can't open file '/app/services/provider-agent/compute_http_service.py': [Errno 13] Permission denied`**. Therefore COPY source had restrictive modes untraversable/unreadable by UID10001; **not** bridge networking or a cgroup OOM. Source Dockerfile fix `RUN chmod -R a+rX /app/tools /app/services` before `USER 10001:10001` committed to R7; additionally launcher readiness poll + regression tests committed (see §3).

For immediate lab verification without altering source installed checkout, Provider built corrective **diagnostic derived image**:

```Dockerfile
FROM sha256:c513259296110d080221d610e481fa336eaf5b0219fd1937883bcc2f87f5888f
USER root
RUN chmod -R a+rX /app/tools /app/services
USER 10001:10001
```

Corrected image ID **`sha256:c2aba72e454367e5b7586da3455457b49ab141109e65a3b68f0bb072a4c3441f`**, tag `sse-compute:permission-fix`. First `sse-compute-smoke` port 8878 immediate `curl` yielded `Recv failure: Connection reset by peer`; later **independent portal session** found `State=running Exit=0 OOM=false` continuously up **7 minutes**, log **`SSE compute worker ready on :8877`**, and `GET http://127.0.0.1:8878/healthz` → **HTTP 200** with `localComputeWorker:true, ok:true, onChainAuthenticated:false`. Real independent host-local verification then **PASSED**:

```bash
cd ~/sse-research
PYTHONPATH=tools timeout 30s .venv/bin/python -c 'from sse_compute_docker import run_compute_probe; r=run_compute_probe("http://127.0.0.1:8878",1,0,"0x"+"11"*32); print(r); assert r["workloadResultVerified"]; print("COMPUTE WORKER TEST PASSED")'
```

Observed `rounds=8192`, `resultDigest=sha256:1a0585f4ea7e6316ba7cc5042309a55d8a34d12788f9c5078b2574a44dee8c9a`, `elapsedSecondsLocal=0.01582`, `workloadResultVerified=True`, `trustedHardwareAttestation=False`, `independentMonitorHost=False`. **This is an actual Docker compute test, not an on-chain lease.** The given challenge `0x11..11` and `leaseId=1` were a LOCAL SMOKE FIXTURE; no actual lease #1 yet.

### Manifest #1 — BAD original image, NEVER use in new lease
Provider generated `~/sse-lab/compute-01/sse-resource-profile.json` and SLA policy from BAD original image `c513...`, endpoint `http://127.0.0.1:8881`; resource hash `0xa135cdbbbc1831775a0267c82c9664ac6766c9eea86a58267533c80d44eca8e9`; SLA hash `0x1fba3f0d41e6b2f4032457aaf6939d4a1466f6d26350e97e8297a64d4538a557`. Local only, never submitted. Do not silently reuse these.

### Manifest #2 — corrected c2 image, ACTUALLY used by Consumer request #1
Generated independently on Provider `~/sse-lab/compute-02/` and Consumer `~/sse-lab/market-01/`:
- `serviceKind=deterministic_compute`, `workloadSpec=SSE_SHA256_CHAIN_8192_V1`.
- **`imageDigest=sha256:c2aba72e454367e5b7586da3455457b49ab141109e65a3b68f0bb072a4c3441f`**.
- `cpuMilli=500`, `memoryBytes=536870912`, `endpoint=http://127.0.0.1:8881`; chain ID 31337, Settlement `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`.
- **resourceProfileHash** `0x7182ffec1ceba3c569714de05ca441bdc17b114c7ae98e9f91fcb9e6a858abf0`.
- **slaPolicyHash** `0xffc573392c83037e18907bfaea6234dfc6b2d58081f3e1c21950f00108d1f147`.
- **serviceEndpointHash** `0xafb662a7f8be90ea0c472efab2fe46191e03a6658e517179b72226a308b53c06`.
- The current `sse_sla_build.py` sets versioned proposed SLA with `DELIVERY_ONLY_ZERO_RESERVATION_V1`, timeout inconclusive, signed observations not physical proofs. Check live files before later funding; **never modify committed profile or policy in place**.
- Provider `sse-compute-lease01` launched with corrected c2 image, CPU/memory hardening, host loopback `127.0.0.1:8877`, container ID `57e2f3e4ab640f072ce57f5ed1eb50e3a1c6b098bed2f5d050a02d4d294dda95`. Old launcher on pinned c9c3 code immediately reported `running=true` but first `curl` → reset. **Subsequent HTTP 200 / computation on this specific official-port container NOT YET verified**. Diagnostic `sse-compute-smoke` on 8878 has passed. Before funding, use single `curl --noproxy '*' --max-time 3 http://127.0.0.1:8877/healthz` and verify Docker inspect; do not claim readiness solely from startup JSON.

### Old installed script caveat and future releases
The installed c9c3 launcher still has insufficient readiness gate. Remote R7 fixes not copied to Provider. Its working corrected **derived image** is immutable and **already committed on chain** by the Consumer request; don't rebuild a different image and silently substitute its digest for request #1. For final production-ready release, build a new pinned image from corrected source and make a **new** request against that specific digest. Automated release upgrades must preserve existing `~/.local/share/sse-lab` encrypted keystores and systemd configuration; current SSH handoff is **first-install only** and refuses overwrite.

## 7. REAL marketplace transactions, full values, signers and exact timing

**Consumer (VM4693):**
- Source used `cd ~/sse-r7-onboarding`, activated venv from `~/sse-research/.venv`; created output `~/sse-lab/market-01`.
- Locally encrypted Consumer `consumer.json` decrypted interactively using its passphrase. Temporary `/run/sse/consumer-market-01.key`, owner-only mode 0600 in owner-only `/run/sse`, created by one-line Python to pass to `tools/sse_node_marketplace.py`; **plaintext signer file removed** by end of displayed execution. Never record key/passphrase; do not repeat transaction.
- `BOARD=0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0`, `SETTLEMENT=0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`, `COMMITTEE=0x5FbDB2315678afecb367f032d93F642f64180aa3`.
- Before request, `cast call BOARD 'nextRequestId()(uint256)'` returned `1`.
- `params`: `{"profileHash":"0x7182ff...","policyHash":"0xffc573...","maxEpochFeeWei":100000000000000,"biddingClose":<VM4693 timestamp plus 600 seconds>}`. Exact `biddingClose` not copied, **read on chain**.
- `python tools/sse_node_marketplace.py --role consumer --action request --params-json "$PARAMS" --chain-id 31337 --board ... --settlement ... --pool ... --rpc-url http://127.0.0.1:8545 --signer-file /run/sse/consumer-market-01.key --max-total-wei 1000000000000000 --execute`.
- Mined block **12**, gasUsed **141137**, hash **`0xfad7db198829391c6f46309c7ada984830cbb407d6622f27fa32e574f4784427`**, status `MINED_UNFINALIZED`, exit code **0**. Chain requests ID=1, max fee 1e14 wei (0.0001 ETH).
**Provider (VM4696):**
- A manual `requests(uint256)` read via `eth_call` returned `REQUEST=1 CLOSING_IN_SECONDS=387 SELECTED=False / BIDDING_OPEN` **at that time**, not persistently.
- Locally encrypted `provider.json` decrypted interactively, owner-only temporary `/run/sse/provider-market-01.key` created and afterwards removed. No wallet address or encryption secret copied from Consumer machine.
- `python tools/sse_node_marketplace.py --role provider --action bid --params-json '{"requestId":1,"epochFeeWei":25000000000000}' --chain-id 31337 --board ... --settlement ... --pool ... --rpc-url http://127.0.0.1:8545 --signer-file /run/sse/provider-market-01.key --max-total-wei 1000000000000000 --execute`.
- Mined **block 13**, gasUsed **97339**, hash **`0xf62541423d11d5adf1e3ed8f3c248c4b9a40c3d6d14dfb1d8573ee67d9da7c53`**, `status=MINED_UNFINALIZED`, **exit 0**. Price `25000000000000` wei = 0.000025 ETH per epoch. **Do not duplicate bid**.
- Successful `request` and `bid` receipts are on-chain transaction evidence only. They are **not** a completed auction, escrow, signed workload, monitoring result or payout.

**Read-only verification commands** (the latest execution confirmed request1, bid index0, and candidateCount1; rerun if current state might have changed) (run with `export PATH="$HOME/.foundry/bin:$PATH"` on VM4693; only if correct RPC tunnel active):
```bash
RPC=http://127.0.0.1:8545
BOARD=0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0
POOL=0x5FbDB2315678afecb367f032d93F642f64180aa3
cast chain-id --rpc-url "$RPC"
cast block-number --rpc-url "$RPC"
cast call "$BOARD" 'nextRequestId()(uint256)' --rpc-url "$RPC"
cast call "$BOARD" 'requests(uint256)(address,bytes32,bytes32,uint256,uint64,bool)' 1 --rpc-url "$RPC"
cast call "$BOARD" 'bidCount(uint256)(uint256)' 1 --rpc-url "$RPC"
cast call "$BOARD" 'getBid(uint256,uint256)(address,uint256)' 1 0 --rpc-url "$RPC"
cast call "$POOL" 'candidateCount()(uint256)' --rpc-url "$RPC"
```
The `requests` getter order from Solidity is `consumer, resourceProfileHash, slaPolicyHash, maxEpochFee, biddingClose, selected`. If `getBid(1,0)` does not match Provider `0x5B0488...` and proposed `25000000000000`, **stop and investigate**. If candidates <4 eligible **do not choose+fund**. Do not depend on wall clock without reading the actual `biddingClose`; Ethereum execution uses `block.timestamp` and must be after closing.

**Future funding planning (NOT executed and not authorized yet):** `sse_node_marketplace.py --role consumer --action fund` expects JSON fields `requestId,bidIndex,selectedEpochFeeWei,endpointHash,reservationFeeWei,exposureBudgetWei,maxEpochs,responsePeriodSeconds,monitorGraceSeconds,evidenceWindowSeconds`. It binds trusted Settlement internally, checks actual bid price with `getBid`, and pays `maxEpochs * selectedEpochFeeWei`. The V2 SLA proposed in §6 expects `reservationFeeWei=0`. Choose economically coherent `exposureBudgetWei >= epochFee`, positive timing windows, and validate committee candidate count and endpoint before signing. **If called while only one monitor candidate exists it will revert `InsufficientCandidates` inside `requestAssignment`; do not waste gas/mark request selected.** The board transaction is atomic: revert means no selection was committed. An unselected request is not automatically expired by the bidding close.

## 8. Research implementation components and evidence limits

Contract responsibilities:
- `OpenResourceBoard`: immutable request manifest hashes/max fee/auction close; provider-specific bids; selection + transfer to Settlement escrow, creates lease.
- `SSESettlement`: escrow terms, provider acceptance, committee link, EIP-712 ack/response, epoch admission, monitor vote/3-of-4 sealing, exposure bounds, close/refund/pull-based withdrawals, optional incentive economics and randomness fee. **Provider response signature authenticates a commitment, not physical correctness by itself.**
- `OpenMonitorCommittee`: permissionless bonded candidate registry, eligible exclusion of Consumer+Provider addresses, frozen membership/seed selection, four seats, standby/no-show replacement and lock-release. Current deployed mode derives entropy from future blockhash; **not a VRF**.
Off-chain:
- `sse_node_marketplace.py`: role-owned dry-run-by-default transaction planner; explicit `--execute` signs from protected local `/run/sse/` file, caps total spending and requires mined receipt. This CLI does not run Docker or prove service delivery.
- `sse_vm_role_setup.py`: local encrypted wallet role bootstrap, node machine binding, lab funding, monitoring bond registration; default preview/no tx; no private key transport.
- `sse_lab_release_handoff.py`: first-install-only host-key pinned SSH shallow source transport; receiver verifies Git SHA and archive digest; no GitHub access on receiving machine.
- `sse_sla_build.py`: generates canonical immutable resource V2 / SLA V1 JSON + Keccak commitment hashes **offline**. Output dir must exist and refuses overwrite.
- `sse_docker_worker_launch.py`: validates profile/policy, immutable local image, Docker limits, strict host config; old installed version inspects container but doesn't verify actual HTTP readiness. New remote source now includes readiness check, still awaiting operator acceptance.
- `sse_compute_docker.py`: probes Docker local HTTP and compares known deterministic compute result; reports observed local elapsed time, never physical SLA attestation.
- `direct_work_service.py`: planned winning-Provider-only loopback signed EIP-712 request/result/receipt server, wallet signer, pinned chain state and **owner-only SQLite replay journal**; `--serve` enforces real worker and SLA; NOT yet activated on separate VMs. Endpoint and private transport remain to be integrated.
- `role-agent/agent.py`: loopback UI draft/status/read-only, cannot spend or authenticate chain service by itself. Global observatory should remain nonparticipant.
- `sse_chain_read.py`: read-only Ethereum lease/epoch inspection (block-hash pinning with EIP-1898); proves identity/state **at observed block** not PoS consensus finality.
- Research baseline includes nuanced evidence grading. Monitors must produce independently interpretable signed raw observations, not merely self-declared `success` or `failure`. Three matching timeout reports may be inconclusive under shared network partition; negative evidence must follow policy, with explicit soundness and fairness caveats.

## 9. Prior validation and failure/fix ledger (preserve exact distinction)

**Earlier results before 3-VM work:** VM4693 baseline reported **698 Python discovered, 695 passed, 3 skipped**; Solidity `forge build` compiled **56** files with warnings. R7 onboarding **10/10** tests and R7 SSH handoff **6/6** offline tests passed on VM4693 at `5d2985b`. These were specific historical suites/commits, not global current R7 source acceptance. Other WP research docs in `MASTER_TRACKER.md` track 88 Foundry/403 Python/source CI for stacked experimental PRs; not deployed to Anvil.

**Issues and demonstrated outcomes:**
1. Foundry PATH missing on VM4693 earlier: use `export PATH="$HOME/.foundry/bin:$PATH"` before `cast`; future automatic bootstrap should ensure reliable executable discovery. No redeploy.
2. Gas estimate on unfunded monitor earlier: initialized/funded via dev chain, registered bonded monitor once; add identity/funding preflight, not blind retries.
3. Duplicate portal VM hostnames: new cryptographically random persistent nodeId and host machine-id binding; Provider now really uses it. Avoid hostname-only scripts.
4. Initial Provider role `ModuleNotFoundError: Crypto` on first attempt; installed/verified requirements; later role init succeeded. Future release receiver Python dependency/venv smoke preflight.
5. Secure SSH handoff succeeded real VM; build later safe in-place update mechanism. Do not provision GitHub private key on Provider.
6. RPC SSH tunnel immediate `curl` failed while systemd unit starting; a later chain status succeeded. Add readiness/retry checks, no tunnel reinstall.
7. Provider UI immediate `curl` failed while unit started; later health/status passed and port 8765 listened. Add HTTP startup health gating.
8. Nonroot Docker socket permission denied; `usermod -aG docker` plus `sg docker` allowed lab, but group grants root-equivalent power; future restricted design needed.
9. Original Docker `c513...` nonroot Python source file permission denied, exit 2; trace captured only after retained-logs diagnostic container. Derived c2 correction verified HTTP 200 after startup; real host-side independent `8192` SHA256 workload passed. Permanent Dockerfile chmod and readiness-poll source fixes committed; newer launcher untested and not deployed. Issue #28 open.
10. `curl` connected then reset immediately after launching corrected c2 image on host ports 8878 and later 8877. Diagnostic c2 on 8878 later stayed running, returned HTTP 200. Distinguish startup race hypothesis vs proven cause; official 8877 specific HTTP check pending.
11. Portal shells can get stuck/uninterruptible even when services functional; new portal terminal works; long Python heredoc sometimes corrupted by paste. Prefer single-line bounded `python -c` and `timeout`, and no giant combined paste commands.
12. Consumer request tx block12 success, Provider bid block13 success. Never recreate these for convenience; contract next state must be read first.
13. **Newly discovered guard:** 1 eligible monitor blocks `chooseBidAndFundLease` through `InsufficientCandidates`; need at least 4 eligible independent committee candidates before funding.

**Deployment automation acceptance tasks**: immutable pinned verified release; host-key identity; idempotent role wallet creation, no overwrite; SSH/RPC restricted keys and health checks; chain-id+addresses+code/domain preflight; approved endpoint private reachability; rootless/restricted Docker or explicit documented lab limitations; Docker source readability; post-launch HTTP readiness and digest computation; protected persistent signing; not overstating signature/EIP-712 evidence; independently deployed monitors; failure handling; state snapshot/recovery; deterministic replay + clean-rebuild and audited release. Ansible/cloud-init/systemd/Tailscale/health/readiness are candidates but don't claim they're already automated.

## 10. Original R0–R11 / P0–P6 phase tracker (historical numbers, DO NOT inflate)

Source `docs/research/PHASES_TRACKER.csv`. **Engineering**: R0 Reproducible baseline **100%**; R1 Formal SSE evidence protocol **62%**; R2 Settlement and economics hardening **26%**; R3 Open verifiable monitoring registry **38%**; R4 Shared signed evidence/SDK **38%**; R5 Autonomous role agents **10%**; R6 Automatic Ubuntu onboarding **5%**; R7 Heterogeneous cloud workloads **15%**; R8 Read-only chain observatory **10%**; R9 Independent distributed experiments **5%**; R10 Publication-grade evaluation **0%**; R11 Independent replication/release **0%**. **Research**: P0 Systematic novelty analysis **37%**; P1 Formal problem and assumptions **55%**; P2 Theorems and proofs **29%**; P3 Publishable protocol specification **39%**; P4 Pre-registered experiments/baselines **20%**; P5 Original scientific manuscript **0%**; P6 Publication artifact/reproduction **0%**. Aggregate equal-weight 489/1900 ≈25.74% (~26%). These are *historical planning estimates*, not a claim of 26% validated production functionality.

Source references: `docs/research/MASTER_TRACKER.md`; `docs/research/PHASES_TRACKER.csv`; 42-item audit ledger `docs/research/AUDIT_ISSUES_42.csv`; work-package documents `R3_WP09A...` through `R3_WP09E...` and `R4_WP08F...`; `docs/research/R5_R6_NOV17_LIVE_UBUNTU_CHECKPOINT.md`; `docs/research/R7_VM_ROLE_OPERATOR.md`; `docs/research/R7_PINNED_DOCKER_SLA_RUNNER.md`; issue #28. A number of advanced R3/R4 draft-stack PR capabilities were not merged/deployed onto these real VMs; do not silently claim they operate in this lab.

## 11. Exact immediate plan for next operator and new chat

**MUST DO, in order, without rerunning old transactions:**

**(A) Read-only chain verification** on VM4693 user `ayoubakrvm4693`, IP `10.50.56.8`: see §7 commands. Confirm `chainId 31337`, request 1 matches Consumer, profile and policy hashes, `selected=false`, `bidCount>=1`, `getBid(1,0)` = Provider and fee 25000000000000 (if not, discover correct index), and `candidateCount=1`. This is safe and does not require passphrases. Note max epoch fee and close time; no need to recreate request after close.

**(B) Monitor VMs**: need minimum **four independent external monitor VMs**, with additional standby recommended, unless user explicitly authorizes a clearly labeled *non-independent emulator* for debugging only. For each NEW VM: record portal username, IP, independently verified SSH fingerprint, machine fingerprint and unique SSE node ID; provision dedicated restricted SSH key and approved first-install R7 source (do NOT reuse the consumer/provider key stores), set private chain RPC tunnel, `python tools/sse_vm_role_setup.py init --roles monitor,observer`, fund DEV ETH on chain 31337 with idempotent `lab-fund`, then `register-monitor --bond-wei 1000000000 --execute` locally and verify chain candidate count, active bond, owner identity, and independent runtime health. Do not assign Consumer/Provider identities as monitors. At least 4 eligible externally operated monitors needed before creating lease. Distinguish signer-only lab from scientific independence.
**IMPORTANT CO-LOCATED MONITOR SELECTION RISK:** The already registered VM4693 monitor `0xCa8978d722fAe6738D00cDE24961F7C4240B42e3` is **eligible on-chain** because its EOA differs from Consumer, but is not independent of the Consumer's host. If four additional external monitors register and the VM4693 monitor remains active, the committee randomly selects 4 out of 5, typically including this co-located monitor; **4 external registrations alone do not guarantee an independent selected committee**. Before funding a scientific lease, have the VM4693 monitor signer execute `OpenMonitorCommittee.requestExit()` only after explicitly reviewing the consequences and verifying `pendingSelections==0` and `activeAssignments==0`. Contract source shows `requestExit` deactivates and removes it immediately from the active roster, but its bond becomes withdrawable **only after 86400 seconds** and after all locks clear. After exit, four external eligible monitors give an all-external committee but no standby; **five** external hosts give a standby. This action has not been executed; current `candidateCount=1`. Separate external VM instances do NOT by themselves prove independent *operators*, so scientifically qualify identity/control trust before claiming independence. If exit is not desired, do not claim independence for any committee that might contain VM4693. 

**(C) Recheck running Provider worker** on VM4696: `sudo docker ps -a --filter name=sse-compute-lease01`; `sudo docker inspect ... State`; `curl --noproxy '*' --retry 0 --max-time 3 http://127.0.0.1:8877/healthz`; verify c2 immutable digest, limits and actual digest. Diagnostic `sse-compute-smoke` on 8878 may still run; don't delete until no longer needed. Fix release upgrade safely rather than copying old secret files or blindly rerunning initial handoff.
**(D) Private signed service transport**: choose approved VM4693→VM4696 port 8881 authenticated SSH tunnel using a separate forwarding-authorized key or private Tailscale HTTPS; *current provision key is restricted without forwarding*. Ensure endpoint hash on chain (loopback 8881) matches actual Client URL from Consumer host. Provider direct service must have protected local signer, owner-only SQLite journal, pin block hash, Docker inspected worker; no service exposure or read-only UI wallet signing.
**(E) Fund/accept/select only after gates**: request1 exists with submitted bid; after `biddingClose` and >=4 eligible external monitors, Consumer chooses correct bid via `chooseBidAndFundLease` with exact hash, coherent fee/exposure/timers; read receipt + new lease ID. Provider signs `acceptLease(leaseId)`. Delayed entropy mode requires mined future block +4 and bounded deadline; permissionless `fulfillDelayedBlockEntropy(assignmentId)`, then `finalizeMonitorCommittee(leaseId)`, each 4 selected monitor signs own confirmation. If any fail, test standby/no-show logic with strict conditions. Consumer `admitEpoch`, winner computes and signs, consumer signs receipt, independent monitor observations, vote threshold, seal/settle/close, verify escrow invariants.
**(F) Research standards**: actual independent trials including partition/drop/time skew/reorg/service misbehavior, reported-vs-verified evidence, gas and latency, fairness/committee sample, performance stats; replayable traces and scientific paper. Later freeze, wipe lab, and run clean automated deployment end-to-end; never prematurely declare all phase completions.

## 12. Running append-only operator ledger

| Date (UTC) | VM / role | Observed action | Result / reference |
|---|---|---|---|
| Before Nov17 | VM4693 + VM4695 | Foundry, isolated Anvil RPC, signed monitor bond and roles | Block10 monitor tx `0x2d6c57...`; active count1 |
| 2026-11-17 | VM4696 | Verified user, private IP, SSH host fingerprint, machine ID | `ayoubakrvm4696@10.50.56.2` |
| 2026-11-17 | VM4693 → 4696 | Strict host-key SSH; pinned first SSE release | sha `c9c3afa`; `VERIFIED_PRIVATE_VM_RELEASE_INSTALLED` |
| 2026-11-17 | VM4696 | Encrypted Provider wallet and node ID created | `0x5B0488...` / `sse-81322ab79a2ee6a795952306` |
| 2026-11-17 | VM4693 | Dev-fund Provider wallet | Block11 tx `0xa9fd17...`, 0.02 ETH |
| 2026-11-17 | VM4696 → 4695 | Private RPC SSH, supervised service | chain31337, local8545 active |
| 2026-11-17 | VM4696 | Node-local Provider/Observer UI enabled | port8765 health and status working; read-only |
| 2026-11-17 | VM4696 | Docker nonroot group lab workaround and image build | Docker29.1.3; image `c513259...` |
| 2026-11-17 | VM4696 | First Docker worker exits, logs missing; reproduce | Exit2 and `Errno13` source file permission; issue #28 |
| 2026-11-17 | GitHub R7 branch | Permanent chmod fix, readiness checks, tests | commits `3dd2129`, `453b867`, `6f036a6` |
| 2026-11-17 | VM4696 | Corrected c2 diagnostic image and 8878 service | HTTP200, stable 7min |
| 2026-11-17 | VM4696 | Real 8192-round deterministic compute probe | PASS `sha256:1a0585f4...`; no physical SLA proof |
| 2026-11-17 | VM4693/4696 | Both generated identical c2-backed manifest hashes | resource `7182ff...`, SLA `ffc573...` |
| 2026-11-17 | VM4693 Consumer | RequestResource #1 | block12 tx `0xfad7db...`, mined, fee cap1e14 wei |
| 2026-11-17 | VM4696 Provider | placeBid(request1, 2.5e13 wei) | block13 tx `0xf625414...`, mined, exit0 |
| 2026-11-17 | Source inspection | Committee assignment gate requires >=4 eligible | **Funding blocked at 1 known candidate**; no lease yet |
| 2026-11-17 14:03 UTC (approx.) | VM4693 / public on-chain read | Verified request 1 exact hashes, max fee, close unix 1794923778, selected=false; bidCount=1; getBid(1,0)=Provider/25000000000000; candidateCount=1 | **Correct bidder/index verified; no funding permitted yet** |
| 2026-11-17, later | VM4696 Provider | Up 45min Docker c2 worker on port8877 with successful local health response | Running/healthy at observation, not signed delivery or readiness-poll source acceptance |
| 2026-11-17, later | VMs4699,4700,4701,4702,4703 | Portal identified distinct private IPs, Linux users, host ED25519 fingerprints, machine-id hashes, Python3.12.3 | New **unprovisioned** monitor hosts; no wallet/RPC/bond installed yet |

**Next append here after the next user command output**, update §0 current state, inspect any changed branch code, revise issue #28 or new issue as needed, commit file update. Avoid stale attributions. Existing VM, wallet, contract and transaction facts are durable; current health status is a last observation, not a guarantee. Latest transcript ends with the Provider's successful port8877 HTTP check and five new Monitor VM portal identity outputs; no new Ethereum transactions or monitor registrations.

## 13. Handoff safety invariants

1. Use **exact portal username + IP** for every terminal instruction because hostname duplicates.
2. Do NOT copy/print/decrypt/publish private Ethereum or SSH keys; never put a plaintext signer in Git. Role `init` is once per VM.
3. Do NOT redeploy existing contracts or resend same `request`, `bid`, `fund` without read-only current state first.
4. Distinguish real Anvil transaction **MINED_UNFINALIZED** from independently finalized consensus.
5. Distinguish local Docker HTTP/digest pass from independent remote SLA truth and a paid on-chain lease.
6. Do NOT fund until >=4 eligible monitors, independent of Consumer; validate on-chain `candidateCount` and actual identity roster.
7. Do NOT mutate hash-committed manifests or image IDs after chain request; mismatching source release requires a *new* request/research trial.
8. Do NOT claim true VRF: deployed randomness is delayed future blockhash entropy.
9. Do NOT claim full nonparticipant read-only observatory can broadcast or that role UI has live signing.
10. Keep original R0-R11/P0-P6 tracker values until explicit evidence review; preserve research novelty/soundness caveats.
11. **After EVERY new operator output/fix**, update this GitHub handoff and add a dated ledger entry; GitHub is the portable source of truth if chat context ends. If GitHub becomes unavailable, produce a local Markdown snapshot and reconcile at next connection.

---
**Canonical handoff path:** `docs/research/LIVE_UBUNTU_HANDOFF_CURRENT.md` on `research/r7-vm-role-operator-no-ci`. This document intentionally avoids secret values but includes public contract/wallet addresses, SSH fingerprints, image hashes, transactions, exact paths and troubleshooting. It supersedes obsolete progress wording in older November 17 checkpoints, without rewriting the original historical records.
