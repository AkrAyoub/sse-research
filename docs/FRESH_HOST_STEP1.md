# R19 — Step 1: clean-VM inventory (no deployment yet)

**Status:** Implemented source and source tests, NOT independently executed on a new VM yet. This is the first *measurable* piece of the fresh-host onboarding pipeline, not a complete installer. The next steps are signed public release and exact genesis, native P2P join, fresh BLS deposit, multi-role services and a per-node HTTPS browser UI. Track [#32](https://github.com/AkrAyoub/sse-research/issues/32), [#33](https://github.com/AkrAyoub/sse-research/issues/33) and [#34](https://github.com/AkrAyoub/sse-research/issues/34).

## Hardware actually witnessed in prior lab — NOT the cloud VM catalog

| Previously observed lab host | Verified resources | Safe inference |
|---|---|---|
| VM4704 | 2 vCPU, 3.8 GiB RAM | Small onboarding/app/monitor pilot candidate only; **do not assume** enough RAM for independent Besu EL + Lighthouse CL/VC |
| VM4705 | 4 vCPU, 11 GiB RAM, approx. 93 GiB free disk | Ran a real **single-host** private Besu + Lighthouse PoS smoke; **not** proof of production-scale validator suitability, four independent operators, Internet reachability or safe public genesis |

The SSE chain is a **fresh, deliberately small valueless test-ETH research chain**, not Ethereum Mainnet. It may have much smaller state and disk requirements than Mainnet, but client memory/CPU, validator count, P2P ingress and actual usage must be measured. Do not invent role minimums or guaranteed host counts without benchmarking. See official Besu private-network system requirements and Lighthouse installation/advanced networking before deciding full-node allocations.

## First fresh-host experiment: provision ONE ordinary VM

- Choose a **new Ubuntu 24.04 x86_64 VM** with around **4 vCPU, 11 GiB RAM and at least ~90 GiB free disk**, if this flavor is available on the infrastructure. Do not destroy old VMs just to run this read-only step. If the largest available VM is smaller, run the same probe and let measured hardware inform role placement; this first step makes no service launch.
- No static/fixed IP, shared VM infrastructure, Tailscale enrollment, preexisting role wallet, previous chain or old local secrets are required.
- For an external participant, **a separately owned Ubuntu PC/VM in a different network must follow exactly the same future public installer**. This first developer-only command still uses a PRIVATE GitHub repo, so it is NOT the promised frictionless external join.
- The final installer must provide a PUBLICLY reachable, signed and content-pinned release without requiring source-repository credentials or owner approvals. After the initial approved install step, participants choose only roles; all other parameters come from a verified public manifest or local automatic discovery.
- Every participant must host their OWN browser-accessible HTTPS UI, with public read-only status and owner-authenticated state-changing actions. **No public UI has been deployed in this step.** Never expose EL Engine API, keystores, raw signer APIs or unprotected JSON-RPC.

## Test on the freshly provisioned Ubuntu VM (development-only)

The repository is private at this stage. Obtain it only using a **reviewed read-only GitHub credential** for the development trial, never a personal token published in shell history, logs or onboarding artifacts. On the fresh VM after cloning to the home directory (the clone/setup process itself is currently a manual automation gap):

```bash
cd ~/sse-research
git fetch origin feature/r19-fresh-external-node-preflight
git switch --detach origin/feature/r19-fresh-external-node-preflight
git rev-parse HEAD
python3 -m unittest discover -s tests -p 'test_sse_fresh_host_probe.py' -v
python3 tools/sse_fresh_host_probe.py --roles full_node,validator
```

For an Ubuntu app/monitor machine you may instead select `--roles monitor,provider`. The probe never enrolls, activates, deposits, starts Docker, changes firewall rules, queries cloud metadata, makes network requests, reads wallets or changes any file. It only returns local measured CPU, RAM and root disk with conservative explicit **not verified** network/role/UI flags. It does not assert that your machine has a public IP or is behind CGNAT, because neither is reliably knowable from local resource inventory alone.

**Please report:** the Git commit SHA, unit test results, the printed JSON (it deliberately excludes usernames, hostnames, wallet secrets and local IPs), and whether you used a smaller VM flavor. Do not report private keys, genesis mnemonic, passwords, raw Kurtosis runlogs, SSH deploy keys, or API tokens.

## Required next phases — acceptance, not simulation

1. **Immutable signed public bootstrap:** publish release trust anchor, genesis/config/contract hashes, public bootnode ENRs/enodes, pinned Besu/Lighthouse binaries and reproducible install packages. The current preflight does not cryptographically authenticate remote release bytes.
2. **Real clean-host installation:** install EL/CL/VC and requested app agents under least privilege, generate independent local encrypted secrets, verify chain 31340, sync actual peers and maintain a restartable local service. No 31339 credentials or genesis reuse.
3. **Open reachability:** use native devp2p / discv5 TCP+UDP over the Internet and independently operated reachable seeds; dynamic IPs via refreshed records and ENRs, CGNAT detection and realistic relay requirements. Public HTTPS web UI on each node must work without requiring a VPN or SSH forwarding.
4. **Permissionless roles:** independent full node connects without operator approval; separately funded BLS validator deposits and activates; provider/consumer/monitor use local wallet, on-chain bid/bond/selection and real service evidence.
5. **Independent hosts and faults:** at least four genuinely independent validator operators and independently controlled monitors, real provider/consumer on separate hosts, transactions, settlements and measured faults. Four VMs on one cloud account are useful for test setup but do not prove independent operator control.

**Operational integrity:** The 31339 private PoS smoke chain previously printed a genesis mnemonic/private keys; it is forbidden for public exposure. PR #31 cleanup is still draft and needs full `scripts/verify_current.sh` before merging to main. This new step is deliberately stacked on its proposed refactor branch.
