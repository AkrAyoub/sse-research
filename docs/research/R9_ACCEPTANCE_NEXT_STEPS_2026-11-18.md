# R9 next acceptance cycle — 2026-11-18 — after Windows gate 5475bc7

## Actual observed operator results

On Windows Git Bash, exact reviewed Git SHA
`5475bc76e5d14ba3c176d93b7a8c94d5f54d6d00`:
- `bash scripts/manual_integrated_gate.sh` ended with
  `SSE_LOCAL_GATE_COMPLETED on 5475bc76...`
- **842 Python unit tests run, 0 failed, 20 skipped**, 71.447 seconds.
  822 ran successfully and 20 were skipped, including Linux-specific
  key-custody/SSH/account permission tests. Several displayed
  `BENCHMARK FAILED` strings belong to *negative* test fixtures; they are
  followed by an overall successful `OK` result and are NOT failed tests.
- **144 Foundry tests passed**, 0 failed or skipped, including WP09Q's
  10 batched-global recovery EVM tests and EIP170 runtime-size checks.
- `tools/sse_experiment_evidence.py` created
  `.local/manual-gate/r9-local-evidence.json` with SHA256 for two local
  logs. Output **explicitly says `rawDataPreserved: false`**:
  keep the original logs under separately backed-up storage before deleting
  the worktree or any VM.

This does NOT prove a single new Besu validator is running or any
Tailscale outside-host participant has joined. **No new live chain is deployed.**

## GitHub-only development, manual deployment (new release scope)

The next R9 package adds:
- a **POSIX-only Ubuntu test runner** that refuses to count skipped
  Linux identity/security cases as a pass;
- a **public identity record per fresh Ubuntu VM** binding its own
  Besu P2P key, locally reported Tailscale device and SSH host fingerprint,
  exact Git revision and collection timestamp; an operator-side four-report
  audit rejects clone-like collisions. It is a *consistency check*,
  **NOT** a cryptographic proof of separate host ownership;
- a **P2P-disabled, read-only genesis canary** whose isolated RPC at
  127.0.0.1:18559 yields block-zero hash; it does not send P2P traffic,
  doesn't import any original validator key and never touches
  Anvil 127.0.0.1:8545;
- operator runbook and strict source-only tests. No GitHub Actions.

## Safe operator sequence — FIRST NEW Ubuntu VM

Do not use the old VM4695 until its Anvil lease and escrow inventory is
resolved. Begin on one disposable, truly separate Ubuntu machine.

1. Provision Ubuntu 24.04. If possible obtain a VM outside the old campus
   10.50.56.0/24 to test NAT isolation. Record its cloud/provider ID in
   private experiment evidence; don't presume independent physical hardware
   just because DHCP address differs.
2. Obtain an authorized private Git checkout through the host's own
   read-only SSH deploy key, or reviewed signed public release archive.
   **Never copy a shared GitHub PAT**, another VM's SSH or Ethereum EOA keys.
   Select the exact approved GitHub SHA, not a moving branch head.
3. Manually install Python3.12, a local isolated venv and the minimal
   `infra/qbft-multivm/requirements.txt` (eth-account and
   pycryptodome). Record installed versions with `python -m pip freeze`.
   Future production releases require a stricter hash-locked dependency list.
4. Run the actual Ubuntu POSIX gate, as the nonroot checkout owner:

   ```bash
   python3 tools/sse_ubuntu_security_gate.py --expected-commit FULL_APPROVED_GIT_SHA
   ```

   **Expected:** no failures or skips. Do not use WSL to claim independent
   Ubuntu VM security checks.
5. Manually set up Tailscale tailnet admission using an operator-approved
   per-VM device. The central broker's `tag:sse-node` role tag currently
   covers application participants; don't assume it grants QBFT validator
   authorization. Establish restrictive Tailscale grants for P2P and deny
   public JSON-RPC. MagicDNS/Tailscale removes the need to purchase a domain.
6. Generate this VM's Besu P2P private key locally once using
   `sse_qbft_validator_identity.py init` from the R9 runbook. Never
   paste/export `node.key`. Share the derived **public** JSON via a
   pinned, independently authenticated SSH channel.
7. Execute public report collection (the report is public metadata but not
   a proof of remote integrity):

   ```bash
   python3 tools/sse_qbft_fleet_evidence.py collect \
     --private-dir /home/USER/sse-qbft-private \
     --public-file /home/USER/sse-qbft-private/validator-1.public.json \
     --expected-commit FULL_APPROVED_GIT_SHA \
     --output /home/USER/sse-qbft-private/validator-1.host-report.json
   ```

   The operator must separately verify host SSH fingerprint via trusted
   enrollment. Distinct report contents alone do not establish independence.
8. Repeat on three ADDITIONAL independently administered Ubuntu VMs,
   with distinct Tailscale identities, node keys and roles validator-2, -3,
   -4; do not clone an already-initialized disk image with node keys.
9. Operator pulls the four public reports to a private experiment workspace
   using pinned SSH/known_hosts identities and runs:

   ```bash
   python3 tools/sse_qbft_fleet_evidence.py audit \
     --expected-commit FULL_APPROVED_GIT_SHA \
     --report /trusted/validator-1.host-report.json \
     --report /trusted/validator-2.host-report.json \
     --report /trusted/validator-3.host-report.json \
     --report /trusted/validator-4.host-report.json \
     --output .local/r9-fleet-audit.json
   ```

   Then produce genesis from four public JSON files with
   `sse_qbft_network_assembly.py genesis`. In a reviewed, operator-approved,
   **digest-pinned** Besu image execute the disposable
   `genesis-canary.compose.yaml` with P2P/discovery disabled.
   Capture actual block0 hash; stop this isolated canary.
10. Generate `SSE_QBFT_PEERS_V1` from the actual hash, sign it offline,
    distribute the signer public key out of band, produce verified bootnodes
    locally and only THEN bring up four real validator Docker services.
    Observe 4-way consensus and fault testing before sending application
    transactions. Each VM's `node.key` stays local and each VM's data
    directory belongs only to that host.

**Docker permissions:** earlier legacy VM output showed a denied Docker
socket. Treat this as an actual setup gate. Docker group membership is
effectively root privilege: use a reviewed, dedicated operator identity or
an approved rootless setup, not an indiscriminate `chmod 666` on the
Docker socket or shared application-user Docker membership.

## Active R0–R11 gates

- G0 local source integration: **PASSED on 5475bc7 Windows**; new commit and
  Ubuntu-specific validation pending.
- G1 truly separate Ubuntu host identity/canary: NOT RUN.
- G2 4 real QBFT validators, peer agreement/quorum outage/recovery: NOT RUN.
- G3 outside-network onboarding via Funnel + secure broker: SOURCE ONLY.
- G4 real signed SSE marketplace application/monitor/escrow workflow on
  chain31338: NOT RUN.
- G5 block period/load/failure/rewards statistical study: NOT RUN.
- G6 manuscript, complete reproducibility, clean final genesis: NOT RUN.

A public bootstrap peer list is not validator governance, and Tailscale's
hosted control plane is not fully permissionless decentralization. We must
maintain those limits in experiments and in the final research report.

## Authoritative public client docs

- https://docs.besu-eth.org/private-networks/how-to/configure/bootnodes
- https://docs.besu-eth.org/public-networks/concepts/node-keys
- https://docs.besu-eth.org/public-networks/how-to/connect/configure-ports
- https://tailscale.com/docs/features/tailscale-funnel
