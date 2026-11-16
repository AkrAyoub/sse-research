# R6 fast gate: real Ubuntu account isolation

**Status:** source-only acceptance utility and offline regression tests. NOT executed on Ubuntu; no machines, systemd services, contracts, signers or CI changed. Base commit `d03976d` was developer-validated (688 tests, 679 passed, 9 skipped), and optional real Anvil integration passed.

## What must be proven, not simulated

`ssemonitor` owns the 0700 private journal directory and 0600 journal. `sseagent` must read only the sanitized monitor snapshot, from a dedicated 0750 display directory with the file mode 0640, via `ssemonitor-display` group membership. It must NOT read private monitor journal, signing keys or raw evidence. This is a prerequisite to actually installing the separate role services.

`tools/sse_r6_ubuntu_isolation_acceptance.py` provides a no-operation default preview, a read-only POSIX ownership/mode `--layout` check, and an actual unprivileged `--as-ui` file-opening check. It never reads file contents, changes permissions, writes or sends Ethereum transactions. Failure to open the public snapshot or unexpectedly succeeding in opening private assets is a hard failure. This is **not proof of systemd runtime isolation, SELinux/AppArmor/ACL completeness or operator independence**.

Expected paths:

| Path | Owner:group | Mode |
|---|---|---|
| `/var/lib/sse-monitor/` | `ssemonitor:ssemonitor` | 0700 |
| `/var/lib/sse-monitor/events.sqlite` | `ssemonitor:ssemonitor` | 0600 |
| `/run/sse-monitor-display/` | `ssemonitor:ssemonitor-display` | 0750 |
| `/run/sse-monitor-display/tasks.json` | `ssemonitor:ssemonitor-display` | 0640 |

### Developer Windows test gate

```bash
git status --short
git fetch origin research/r6-ubuntu-isolation-acceptance-no-ci
git switch --detach origin/research/r6-ubuntu-isolation-acceptance-no-ci
git rev-parse --short HEAD
python -m unittest discover -s tests -p 'test_sse_r6_ubuntu_isolation_acceptance.py' -v
python -m unittest discover -s tests -q
```

The new 10 tests produce an **unverified target of 698 discovered, nine skipped, zero failures on Windows**. Do not repeat the unchanged real-Anvil integration unless diagnosing a regression.

### After provisioning on a disposable Ubuntu VM (read-only checks)

```bash
python3 -B tools/sse_r6_ubuntu_isolation_acceptance.py
id ssemonitor
id sseagent
sudo python3 -B tools/sse_r6_ubuntu_isolation_acceptance.py --layout
sudo -u sseagent python3 -B tools/sse_r6_ubuntu_isolation_acceptance.py --as-ui
```

All paths and users must already exist; the script does not provision them. The last command refuses root/wrong identity and requires `sseagent` membership in the display-only group. The monitor private group must remain inaccessible. These operations are owner-run, not remote actions by this branch.

## After this gate — prioritize implementation, not more wrappers

1. Freeze one known-good local commit and install *only on manually approved throwaway Ubuntu VMs*.
2. Connect independently owned consumer, provider and at least four eligible monitors to the same local/dev chain through private Tailscale. Four eligible independent monitors must exist after counterparty exclusions.
3. Prove funded bid, selected provider Docker execution, signed consumer receipt and distinct monitors' signed observations **across VMs**.
4. Inject disconnects, dishonest provider and monitor faults; keep financial monitor voting and automated settlement disabled until evidence is qualified.
5. Measure performance/economics and update R0-R11/P0-P6 tracker using actual acceptance evidence.

Remaining open research: operator independence, physical-SLA evidence qualification, timing and finality assumptions, VRF fairness and economic soundness.