# R10 — SSE publication-grade falsification and live-network experiment plan

**Design freeze: 2026-11-18.** Status: planned hypotheses; model/evidence
tools source-implemented but NOT YET verified on the new GitHub commit.
Already observed operator evidence at SHA
2bc993b2d05a08b831669a3b735a73a40959c78c: Windows
**910 Python tests (20 platform skips), 144/144 Foundry tests**, and
VM4704 **50/50 real Ubuntu security tests (zero skips)**. No new Besu
validator chain has produced blocks in the supplied operator records.

## Scientific contribution candidates (not established novelty claims)

**C1 — Observation-conditioned settlement**: In outsourced service
execution, distinct physical states N/F/S can have identical signed,
time-bounded monitor observations after partitions, dishonest ACKs or
provider-only transmissions. An evidence policy must report its
observation-equivalence assumptions and bound safe releases (L,U), not
promote a 3-of-4 vote to unconditional physical truth.

**C2 — Globally sampled bonded-monitor committee with bounded recovery**:
Full-roster authenticated Merkle snapshot and partial Fisher–Yates style
unique index selection across 16–160+ candidates, 40-index/8-proof
recovery and fee/bond conservation. Proof inclusion is verifiable,
but current entropy schemes still have withholding/selection/Sybil
limitations. Compare against bounded legacy roster on identical EVM
fixtures and actual posted transaction costs.

**C3 — An end-to-end reproducible SSE experiment**: Real deterministic
HTTP challenge/compute service, independent consumer/provider/4 monitors,
four separate consensus validators, read-only block consensus agreement,
published hashes of signed evidence and all fee/bond transfer receipts,
with controlled outage and network relocation arms. Tailscale is a
laboratory transport, not a prerequisite for open blockchain roles.
Physical independence is NOT proved by VMs sharing an administrator.

Novelty and priority require a properly cited closest-work study; do not
claim the first blockchain SLA monitor. Compare explicitly with:
- https://doi.org/10.1007/s10586-021-03416-y — blockchain real-time SLA
  cloud monitoring with empirical scalability
- https://onlinelibrary.wiley.com/doi/10.1002/cpe.5800 — distributed
  two-level blockchain management of dynamic SLAs and crowd oracles
- https://doi.org/10.1007/s10922-026-10041-w — contemporary SLA/SecSLA
  survey (2026)
- https://link.springer.com/article/10.1186/s13677-023-00409-7 —
  blockchain SLA monitoring for IoT

## Preregistered scientific questions and explicit falsification

**H1 — Physical ambiguity persists after valid votes.** In a
four-monitor committee, can the *same* authenticated report bundle be
compatible with world F and world S? Expected yes under a service
delivery predicate not attested by a provider-only response.
Falsification: show the signed on-chain report necessarily commits to
a trusted physically sufficient receipt, not merely a provider
transmission/signature. Use prior real Foundry CE01--CE04 examples.
Never conflate a stipulated scenario with actual observed SLA truth.

**H2 — Safer release/uncertainty tradeoff.** For a declared finite
possible-world universe, provider guaranteed release equals
L=min e(h); consumer guaranteed refund=V-max e(h); held=max-min.
A rule releasing more than these bounds must exhibit an excluded
world or explicitly assume stronger trusted evidence. Compare current
SSE quorum-style abstraction, ambiguity-hold, and an omniscient
upper-bound oracle over the same randomized physical hypotheses.
Reject a claim of universal safety if the universe fails to include
realistic network/Byzantine histories.

**H3 — Scalable election and recovery cost.** On identical Foundry
optimizer/EVM settings and seeded candidate identities, compare
old (legacy) and global-Merkle implementations at N=16,64,160,
plus 40-proof recovery batches of eight. Report all transactions,
per-call gas, exact runtime code size and EIP170 margin. Include the
countervailing cost of global on-chain registration and Merkle updates,
not only the inexpensive create-lease path. Historical numbers below
are **Foundry instrumented calls**, not chain throughput.

**H4 — QBFT four-host liveness/fault boundary.** Once actual independent
VMs are running from one verified genesis: 0 outages => sustained
finality, 1 validator outage => continued progress, 2 outages =>
consensus stalls or loses progress. Measure genuine block intervals,
rejoin latency and divergence from four independently pinned RPCs.
Do not assert observed behavior before real runs.

**H5 — Physical service evidence vs network causality.** Provider
execution may be correct but delivered after SLA deadline, or timely
provider broadcast may never reach consumer. Test service-local signed
request/response/consumer receipt, archive witness and WAN partition,
including contradictory or unavailable records. Do not claim
trustworthy timestamps merely because Ethereum includes transactions.

**H6 — Permissionlessness is a separate experiment.** QBFT block
production uses elected/whitelisted validators, not open PoS or PoW;
a downloadable validator-role request alone is not eligibility or
consensus voting authority. R10 must explicitly compare this controlled
baseline with a separate, genuinely open validator protocol if a
permissionless consensus claim is to be made. Until then publish
"open application entry over a permissioned QBFT evaluation chain",
not "permissionless consensus".

## Existing measured EVM results (operator log at 2bc993b)

WP09N instrumented creation gas:

| N | Legacy create lease | Global-Merkle create lease |
|---:|---:|---:|
| 16 | 975,537 | 472,727 |
| 160 | 2,579,410 | 473,039 |

WP09N registration gas: legacy 16/160 both 131,502;
global 16: 382,607 and 160: 399,727.
Global finalize 16: 544,488, 160: 569,031; these are distinct
operations and must not be presented as a per-lease total without
accounting for startup and maintenance costs.

WP09Q recovery: five actual Foundry proof-batch call gas measurements
680,497; 613,317; 612,008; 613,768; 638,445.
OpenMonitorCommittee code bytes 22,670; SSESettlement bytes 22,533;
EIP170 headroom 1,906 / 2,043 bytes.

The Foundry-world CE-01..04 demonstrators are **already exercised**,
but label world S/F as *stipulated outside-chain* ground truth.
The local Ethereum EVM cannot attest that a physical provider fulfilled
an SLA in the real cloud.

## Phase A — deterministic model and paper provenance (NOW executable)

After the *new* corrected GitHub SHA passes the manual Windows gate:

    mkdir -p .local/r10-model-20261118
    python tools/sse_r10_observation_campaign.py \
      --output-dir "$(pwd)/.local/r10-model-20261118" \
      --source-commit "$(git rev-parse HEAD)" \
      --seed 20261118 --replications 25

This enumerates 2 services × 3 true worlds × 5 outage strata
× 3 Byzantine-monitor strata × 25 replications = **2,250**
stipulated physical scenarios, and 6,750 policy allocation rows.
Defaults fee=25 wei, reservation=5 wei. Each scenario uses a
SHA256-derived independent deterministic random stream. Declared
response-visible probabilities for N/F/S are 0.20/0.72/0.88,
untrusted-ACK probabilities 0.08/0.35/0.30 and hypothetical
trusted-outcome-certificate probability 0.22. **These rates are
synthetic knobs, not measurements or calibrated probabilities.**

Outputs: immutable trials.csv, summary.json, summary.md,
manifest.json with SHA-256 file hashes and exact approved source SHA.
Five outage strata 0,1,2,3,4 are modeled; real QBFT outage strata
0/1/2 are a SEPARATE experiment. All row outcomes conserve escrow.
Wilson 95% intervals describe RNG variation *within the model*, not
confidence about an unmeasured Internet or Byzantine actor.

If we later obtain real partition/failure probabilities, preregister
a second sensitivity matrix, preserving the synthetic initial
assumptions rather than retrospectively tuning them for better results.

## Phase B — bring up first REAL Besu executable (VM4704)

Current chain31337 Anvil VM4695 remains untouched. On fresh VM4704,
after the new SHA passes Windows AND actual Ubuntu gates, use the new
scripts and a dedicated output directory:

    cd ~/sse-r9
    mkdir -m 700 -p "$HOME/sse-r9-canary-01"
    python tools/sse_r9_canary_lab.py \
      --source-commit "$(git rev-parse HEAD)" \
      --image-tag hyperledger/besu:26.11.1 \
      --run-id vm4704-r10-canary \
      --output-dir "$HOME/sse-r9-canary-01"

The first command is **dry-run only**. Explicit --apply causes
an image **version tag pull solely for an exploratory canary**,
records its immutable registry sha256 digest before running, creates a
unique disposable Compose project, checks a real block-zero RPC and
Besu client version on 127.0.0.1:18559, logs the results and stops
the canary. It never creates four actual validator keys or uses P2P,
and cannot claim real consensus. The operator must review Docker
privilege and registry provenance. The 26.11.1 tag is from the
2026-11-17 Besu hotfix, and is subject to availability on Docker Hub.
No guessed image digest is ever inserted. A subsequent actual validator
deployment **must use a separately approved, GitHub-reviewed fixed
image digest**, not a newly mutable tag.

    python tools/sse_r9_canary_lab.py \
      --source-commit "$(git rev-parse HEAD)" \
      --image-tag hyperledger/besu:26.11.1 \
      --run-id vm4704-r10-canary \
      --output-dir "$HOME/sse-r9-canary-01" --apply

**Safety advisories:** GHSA-p4h2-gvh4-pv6j (Shanghai-enabled QBFT
withdrawal unvalidated money mint; patched in 26.8.1),
https://github.com/besu-eth/besu/security/advisories/GHSA-p4h2-gvh4-pv6j
and Besu 26.11.1 JVM Base64 mitigation CVE-2026-114938,
https://github.com/besu-eth/besu/releases/tag/26.11.1 .
A minimally patched version is NOT a substitute for reviewing future
security advisories.

## Phase C — true four-validator / contract experiment

*Not yet run.* On four real Ubuntu machines, each with independently
created validator private key, distinct SSH/Tailscale identity,
signed-identity audit and independently saved logs:
- Create one full genesis with four **real** public validators, not
  the synthetic canary addresses; operator records exact JSON SHA256.
- Confirm the *actual same genesis block0 hash* on all four nodes.
- Verify identical version/digest and QBFT validator set, signed enodes,
  genuine P2P peer counts and common historical hashes.
- Run baseline blocks 5s/15M gas, then 12s/30M and 60M comparator
  with distinct genesi; separate chain environments for each genesis.
- Deploy the exact compiled SSE contracts on 31338 with pinned build
  metadata; require receipts and contract address crosschecks.
- Enroll five+ distinct app nodes (consumer, provider, four independent
  monitors), record their keys/roles without disclosing secrets,
  execute funded lease and settlement. Test 0/1/2 failed validators,
  0..3 partitioned monitors, and NAT/DHCP relocation.
- Collect at least 600 measured blocks per baseline arm and declare
  warmup 100 blocks if practical. Record real gas, tx counts,
  signed transcript evidence and EVM settlement outcomes; expose
  difference between valid contract claims and physical truth.
- Retain raw logs and sealed cryptographic hashes before disposable VM
  teardown. A mere SHA manifest is not a backup.

## Stop conditions / thesis integrity

Do NOT claim "published", "first", "fully permissionless", "real four
miners", "physical SLA proven", "cryptographic zero fraud", "secure
funds against one Byzantine validator" or "measured TPS" unless actual
evidence and a properly scoped theorem justify those terms.

Immediate hard evidence:
1. Windows FULL gate at new exact SHA;
2. Ubuntu VM4704 full security + R10 targeted tests;
3. first actual client block0 canary and immutable image digest;
4. four independent live validator RPCs producing consistent blocks;
5. one fully funded real multi-role SSE lease with archived signed
   provider/consumer/monitor evidence and on-chain receipts;
6. repeatable comparative research figures and limitations.

Operators must preserve the Anvil chain31337 and original unresolved
historical obligations. Never destroy VM4695, copy wallet keys, or
auto-update live consensus from a moving branch.

## 2026-11-18 — VM4704 first live Besu canary FAILURE, rooted and preserved

This is a real **execution failure** on a new Ubuntu host, not a fake
test or a consensus measurement. The operator executed R10
`sse_r9_canary_lab.py --apply` on VM4704 and obtained:

```text
SSE_R9_CANARY_REFUSED: canary never produced a valid genesis RPC: canary RPC not ready
```

The preserved `~/sse-r9-canary-01/docker.log` proves Docker launched
Besu 26.11.1 far enough to parse CLI options and configure loopback
RPC at port18559, but it crashed during Java native-library initialization:

```text
NativeLibraryLoader | /tmp/libnetty_transport_native_epoll...so exists
but cannot be executed; check volume for "noexec" flag
java.lang.NoClassDefFoundError: Could not initialize class com.sun.jna.Native
Caused by: java.lang.UnsatisfiedLinkError:
  /tmp/jna....tmp: failed to map segment from shared object
```

Root cause: the disposable Compose service mounted `/tmp` as a Docker
tmpfs without explicit `exec`. Container tmpfs is often `noexec` by
default. The JNA and Netty native libraries are dynamically extracted
into `/tmp` and require an executable mapping, even when other UNIX
permissions are correct. This fault occurred **before** Besu exposed
a functional JSON-RPC server. The original container was cleaned
successfully: `docker ps -a --filter name=sse-canary-vm4704-r10-canary`
returned no containers.

**Reviewed source correction:**

- Only the **isolated, short-lived, P2P-disabled** canary Compose
  changes its tmpfs declaration to
  `/tmp:rw,exec,nosuid,nodev,size=512m,mode=1777`.
  Keep `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`,
  nonroot UID, no wallet/validator secret, and local loopback RPC.
  This exec permission is an **explicit security exception**:
  validate a separate restricted native-extraction directory before
  applying any similar change to long-running production validators.
- Canary operator script checks `sudo -n docker info` *before* creating
  evidence, reports current phases and starts Compose with
  `--pull never` after resolving and recording the registry digest.
- R10 Wilson 0/10 and 10/10 floating-point interval tests and the
  incorrect preflight 26.10.1 expectation are corrected in source.
- New tests assert executable canary tmpfs, nonroot read-only container,
  correct client-image minimum, no silent repull and no wallet access.
- **All changes require full manual Windows gate and Ubuntu targeted
  source tests before claiming a corrected deployment.**

Preserve `~/sse-r9-canary-01/` as the FIRST FAILED real-client case.
After accepting the new Git SHA, use an entirely NEW directory, e.g.:

```bash
cd ~/sse-r9
source .venv-r9/bin/activate
mkdir -m 700 "$HOME/sse-r9-canary-02"
sudo -v
python tools/sse_r9_canary_lab.py \
  --source-commit "$(git rev-parse HEAD)" \
  --image-tag hyperledger/besu:26.11.1 \
  --run-id vm4704-r10-canary2 \
  --output-dir "$HOME/sse-r9-canary-02"
# After reviewing the plan, repeat the exact command with --apply.
```

Successful canary means: evidence includes observed Besu `chainId`
31338, real block-zero hash, client version, immutable image digest
and `canaryStoppedAfterProbe: true`. It **does not** mean four
validators, honest SLA monitors or production application nodes exist.
Never infer protocol safety from a successful boot0 canary.

Vendor references:
- https://docs.docker.com/engine/storage/tmpfs/
- https://www.elastic.co/docs/deploy-manage/deploy/self-managed/executable-jna-tmpdir

