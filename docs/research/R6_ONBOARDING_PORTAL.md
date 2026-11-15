# R6 Onboarding Portal — existing Ubuntu VMs

**Status:** static HTML onboarding helper, not a live joined node or production wallet.

## Why this exists

Cloud VMs are launched with **ordinary preinstalled Ubuntu**; the operator
does not require access to cloud-init or provider VM-template customization.
After the VM is created, the operator opens the publicly hosted SSE onboarding
page (or source page) and copies an installation command into the VM's Ubuntu
terminal or SSH session.

The static page is `docs/index.html`. It uses only built-in HTML/CSS/JS:
no backend server, cookies, browser wallet, private-key submission, or
secret collection. It generates commands for a version-pinned `sse_vm_bootstrap.py`
at commit `97bd3d434af1bb20ce08b763b90b58cce7e4c036`.
This SHA refers to the *installer source*, which is present at that exact
commit, not to a mutable branch. It can be updated in a future reviewed
portal release. The installer and downloaded dependencies are not yet
independently signed or hash-locked.

### What users actually do

1. Start a normal Ubuntu VM from their existing provider/private cloud.
2. Obtain a web console or SSH terminal on that VM with outbound HTTPS.
3. Open SSE onboarding website on their own browser, select provider,
   monitor, consumer or observer, and enter public RPC, deployed
   `SSESettlement` address, node ID and optional public wallet address.
4. Copy Ubuntu package-install and pinned-script download commands.
5. Review generated dry-run; explicitly run `sudo` install only after
   checking the exact SHA, network chain ID and contract.
6. Verify the local read-only service status.
7. **Later R5/R6:** provision private keys out-of-band, register monitor
   bond if needed, start role transactions; not implemented by this page.

A role heartbeat is **not** proof of permissionless network entry.
The installer intentionally refuses final installation without a real
SSESettlement contract on the chosen chain. Thus the page is usable
for downloading and preparing the setup today, while public testnet
activation awaits a verified contract deployment.

### How to host using GitHub Pages (manual repository owner action)

1. Go to `https://github.com/AkrAyoub/sse-research/settings/pages`.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Set branch `research/r6-onboarding-portal-no-ci`, folder `/docs`.
4. Save; inspect the GitHub Pages deployment. After successful publication,
   use the **Visit site** link in repository settings.
5. You may later choose a stable dedicated publishing branch after review.

The expected GitHub Pages project-site address *if* the project is hosted
under standard GitHub Pages naming is
`https://akrayoub.github.io/sse-research/`, but do not assume this URL
works until the owner's Pages configuration and publication have succeeded.
Publishing Pages may itself trigger a Pages deployment workflow, which
must be separately authorized/managed by the repository owner; these
source commits do not trigger or configure that workflow.

**Important security note:** GitHub Pages is public even in some scenarios
where source repository visibility is restricted. Do not put SSH keys,
wallet seeds, API credentials, or private cloud addresses in the page.

### Alternative: show the page from an existing VM (no GitHub Pages)

On a **trusted, isolated VM** with Git and Python 3, clone the approved
repository revision and serve the `docs/` directory via a locked-down
reverse proxy or tunnel. For an entirely local developer preview:

```bash
cd docs
python3 -m http.server 8080 --bind 127.0.0.1
```

Open `http://127.0.0.1:8080` **on that same VM** (or via SSH
local port forwarding). Do not expose Python's development HTTP server
directly on the public internet. Production hosting should use HTTPS
and appropriate firewall controls.

## Constraints

- A wallet's **public address** is informational only. Gas funding, key
  ownership, monitor registration, service role activation and signed
  evidence remain independent steps.
- A hostname is not an on-chain peer address; application VMs primarily
  need outbound access to RPC, and provider endpoint reachability/TLS must
  be designed and tested separately.
- A public testnet uses valueless *native* test ETH, not ERC-20 or an SSE
  custom token. No real mainnet ETH is required for this research plan.
- Current site does not upload any form values and stores no credentials.
- Every VM must use the same intended chain and deployed contract,
  but **different independent role keys** for honest multi-host tests.
