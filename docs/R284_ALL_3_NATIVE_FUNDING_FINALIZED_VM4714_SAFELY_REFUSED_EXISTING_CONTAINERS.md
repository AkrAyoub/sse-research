# R284: all THREE original native TEST ETH grants FINALIZED; new four-wallet grant exact READ-ONLY quote passed; VM4714 Docker worker refused existing containers; R283 test fixture corrected

## Actual VM4707 owner observations (Nov 24 2026)

Exact original native chain31340 public R278 forensic:
- Last owner-approved Monitor2 native funding nonce3 TX `0x0c6b2e79f930b8e23e5ee9b32bd151733bb09d88a7ecbc8c145cec091cdb389a` **MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED**, included block26008, finalized block26100, EL head26250. Native latest and finalized VM4707 Monitor2 balance both **5000000000000000 wei**. Previous consumer nonce1 and Monitor1 nonce2 funding had already been proven finalized. **ALL THREE ORIGINAL APPROVED TRANSFERS ARE NOW FINALIZED**. Source latest/pending nonce4; never replay any of original nonce1-3 or reset one-shot attempt markers.

R282 actual one-shot read-only pass:
- `READONLY_SCENARIO_QUOTE_ELIGIBLE_FOR_SEPARATE_APPROVAL`.
- Original app funder `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`, latest native balance **979999993320597000 wei**, next nonce4, current native gasPrice1000wei/gas.
- Each of four real owner-created wallets was verified currently empty, nonce0, no code. All four actual `eth_estimateGas` calls returned exactly21000.
- Proposed **only**, no authorization or signing: 0.005 native TEST ETH to each new EOA:
  - nonce4 VM4711 `0x1a89D81288522912643e15D8e06a2a7D9dc4bc08`
  - nonce5 VM4712 `0x30dc70daA83B2D4199B98Cf1b93f31f1BA80f0Aa`
  - nonce6 VM4713 `0x001f529E8d17A243078631100CA7Ad93c001Ea2d`
  - nonce7 VM4714 `0x016B91ED50Ec350e600327C4287F2ED882E0Cf66`.
- Combined proposal exactly **20000000000000000wei value plus at most 84000000wei fees**, maximum **20000000084000000wei = 0.020000000084 TEST ETH**. NOT yet approved, no new transfer sender or signing, no grant sent. R282 is genuinely read-only.

## VM4714 R283 test FAILURE and worker safety refusal

VM4714 owner ran source commit `7d28b78e66ca862ca52ccc27e17cdb9fee6daafa` R283 test suite. Seven assertions passed; one failed:
`test_owner_script_noninteractive_explicit_sudo_refuses_before_mutation`.
Observed error:
`/tmp/tmp.../id: cannot execute: required file not found`.
Root cause: R283 test wrote temporary fake shell helper with *literal backslash-n bytes* in its shebang instead of actual newline. This is a TEST fixture construction error, not an actual VM operating system `id` binary failure and not successful Docker runtime verification. Fix committed on GitHub by replacing literal `\\n` in Python string source with interpreted `\n`; **fix has not yet been rerun on owner VM4714**, so must not claim 8/8 PASS. Original ordered shell terminated after R283 tests failed; R281 and Docker inspector tests in that shell were not reached.

Owner subsequently launched `--run-sudo` **separately** and did type the distinct explicit R283 VM4714 consent. The actual script passed local privileged Docker API access long enough to run its read-only `docker ps -a -q` preflight; it returned:
`R281_REFUSED: dedicated compute host has existing Docker containers; do not disturb them`.
This proves **at least one existing Docker container** (running OR exited) is present on real VM4714; it says NOTHING about container names, image, actual status, purpose, whether running original chain EL/CL, or presence of compute workers. Because the script stops BEFORE image build/run, **no new compute worker was started or CPU SHA workload measured**. This is correct fail-closed behavior and must NOT be bypassed until actual container inventory is known. Do not `docker rm`, `docker stop`, `docker prune`, `systemctl restart docker`, add Docker group membership or weaken socket permissions.

### Exact next read-only VM4714 owner command

Fetch latest exact pinned Git commit from ChatGPT; then on VM4714:
```bash
(
  set -euo pipefail
  SHA="<NEW_PINNED_FULL_GIT_COMMIT>"
  cd "$HOME/sse-v2-standby-source"
  git fetch --no-tags origin feature/r226-adaptive-v2-operator-runtime
  git switch --detach "$SHA"
  test "$(git rev-parse HEAD)" = "$SHA"
  echo "== RETEST FIXED R283 MOCKED UNIT SAFETY =="
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r283_vm4714_explicit_sudo_compute.py' -q
  echo "== ORIGINAL NO-EFFECT R281 SOURCE TESTS =="
  python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r281_vm4714_real_compute_worker.py' -q
  echo "== ACTUAL EXISTING DOCKER CONTAINERS: READ-ONLY =="
  sudo -n docker --host unix:///var/run/docker.sock \
    ps -a --no-trunc \
    --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
)
```

If known running original PoS clients appear, the host is NOT a pristine dedicated provider, and we must preserve them. If all only stopped leftover development containers appear, a carefully reviewed no-change coexistence approach could potentially start an independently named worker, but only after checking resource usage, port8877 collision, exact daemon and worker isolation. Alternatively choose an available EMPTY standby host: the project user has additional large standby VMs. Never infer physical fault independence from template labels.

No scripts will automatically remove, restart or rename preexisting Docker containers.

## Future engineering

- Wait for the actual owner container inventory before changing the existing-container prohibition or choosing another compute-only VM. Use exact read-only info rather than guesses about what is running.
- Use actual source `Dockerfile.sse-compute`, strict container resource/security restrictions, and actual OS-generated random 8192 SHA256 proof before claiming real compute work.
- New four-wallet TEST ETH grants and later monitor bonds are a separate spending scope; R282 prepared a verified budget but DOES NOT grant authority. The owner must explicitly authorize any wallet funding and any bond amounts.
- Resource measurement, independently hosted public HTTPS monitor probes, lease/escrow, on-chain evidence and payouts are still outstanding. Actual unit tests or local CPU run must not be mislabeled economic real SLA proof.
