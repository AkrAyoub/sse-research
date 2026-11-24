# R272 — Actual consumer funded at LATEST; native R267 monitor-1 waits for finality; VM4709 real resource preflight

## Owner live VM4707 observation (2026-11-24, source SHA 4eafadae5e27a6bc5ff6467c3a76996858dbdcb5)

**R271 targeted new tests:** 5/5 PASS.
**R271 owner actual LIVE chain:** `R271_REAL_NATIVE_CONSUMER_TX_AND_BEACON_FINALITY_READONLY=true`.

- Original native chain31340 original execution genesis verified, Beacon genesis verified.
- Actual consumer TX `0x9f3a13cb295b5ba2f642804a30c391b9cce266784a83dd293d0dd7fb7d1f9fdd`, value **10000000000000000 wei** = 0.01 native TEST ETH, **included block25564**, actual canonical successful receipt.
- Actual EOA consumer `0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f` **latest balance10000000000000000wei**, finalized balance still **0**.
- Actual EL head **25676**, finalized EL **25524**; **40 execution blocks short** of finalized consumer funding receipt.
- Beacon actual head slot **27288** (epoch852), finalized epoch **848**, lag 4 epochs, correct Beacon genesis; this alone does NOT prove consensus failure (finalized epoch has progressed since earlier epochs).
- Actual R271 did not send any transactions, read passwords or keys or mutate Docker/Beacon.
- Owner R267 two Monitor1 tests correctly returned pending; no monitor1 nonce2 or monitor2 nonce3 sent; do not resend consumer nonce1 or delete its one-shot marker.
- V2 market+ledger actual R260/R206 finalized deployment proof earlier PASS, no redeployment necessary.

## Separate REAL VM4709 host inventory from owner

- User: `ayoubakrvm4709`, 4 logical CPUs.
- Available RAM ~10GiB; available disk 92GiB; no swap.
- Existing nonroot owner `docker ps` **PERMISSION DENIED** at /var/run/docker.sock. This is NOT evidence Docker daemon/containers are stopped. The real Besu/Lighthouse containers must NOT be stopped, replaced, disabled or relocated just to free a daemon. Their current status still needs authorized read-only inspection.
- System Python `eth_account` NOT INSTALLED. This blocks existing `sse_pos_test_wallet.py --apply` under system Python, not native chain RPC or PoS peering.
- VM4709 historically ran genuine recovered Besu+Lighthouse original-chain31340 syncing/finality; status and physical provider capability at present not yet freshly verified.

## R272 new VM4709 host-only preflight code

`tools/sse_pos_r272_vm4709_provider_host_readonly_preflight.py` requires actual nonroot username `ayoubakrvm4709`, verifies CPU, Linux /proc MemAvailable, free home-filesystem bytes, Python venv availability, eth_account import availability, and the local OS Unix `/var/run/docker.sock` type, ownership, permissions and accessibility. It calls only fixed `docker --host unix:///var/run/docker.sock ps --format ...` to list real existing container NAMES when the CLI exists, without touching remote Docker contexts or requiring sudo. If it cannot inspect Docker, it reports the barrier rather than treating zero visible containers as absence.

This **does not create a wallet, install packages, start a Docker container, read secrets, change consensus clients, or send TEST ETH**. A host resource minimum being met is a candidate only, not a proven rentable CPU workload or independent paid SLA.

New 7 mocked/ephemeral socket tests are staged in
`tests/test_sse_pos_r272_vm4709_provider_host_readonly_preflight.py`. They are **NOT yet actually executed on VM4709**.

### VM4709 safe source handoff

Use exact HEAD SHA from chat; avoid changing the existing ~/sse-research or any path currently used by running PoS clients:

```bash
(
 set -euo pipefail
 SHA="<PINNED_40_CHARACTER_GIT_COMMIT_FROM_CHAT>"
 WORK="$HOME/sse-v2-provider-source"
 if [ -e "$WORK" ] && [ ! -d "$WORK/.git" ]; then
   echo "SOURCE_CHECKOUT_PATH_EXISTS_AND_IS_NOT_A_REPO_REFUSE=true"
   exit 2
 fi
 if [ ! -d "$WORK/.git" ]; then
   git clone -q --no-checkout https://github.com/AkrAyoub/sse-research.git "$WORK"
 fi
 cd "$WORK"
 git fetch -q --no-tags origin feature/r226-adaptive-v2-operator-runtime
 git switch -q --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests \
    -p 'test_sse_pos_r272_vm4709_provider_host_readonly_preflight.py' -q
 python3 -B tools/sse_pos_r272_vm4709_provider_host_readonly_preflight.py --inventory-only
)
```

If Docker access is still denied, an *optional separate owner-approved*
read-only check using preexisting sudo privileges, **never adding any
user to the root-equivalent docker group**, is:

```bash
sudo -n docker --host unix:///var/run/docker.sock \
  ps --format '{{.Names}} {{.Status}}'
```

If sudo needs a password, `-n` fails noninteractively
and does NOT alter service. Do not run `docker run`,
`docker restart`, `docker rm`, `usermod -aG docker`,
`chmod /var/run/docker.sock`, or expose socket over TCP.
Dedicated rootless worker daemon or restricted read-only
inspector can be planned after actual permissions/daemon
are proven without disturbing PoS containers.

Next, install *only owner-approved pinned application Python deps*
into an isolated per-host venv before creating an encrypted
`adaptive-v2-provider` EOA with the existing
`tools/sse_pos_test_wallet.py`. No key files may be
copied or committed, and a generated EOA does not yet
make a funded onchain provider.

## Scheduling

No loop or automated resubmit is authorized. Only once R271 reports
`SUCCESSFUL_CANONICAL_FINALIZED`, existing R267 can
send Monitor1 nonce2 after interactive owner approval;
Monitor2 nonce3 must wait for Monitor1's *actual* canonical
finalized receipt. The provider-host preflight is independent
of this finality dependency.
