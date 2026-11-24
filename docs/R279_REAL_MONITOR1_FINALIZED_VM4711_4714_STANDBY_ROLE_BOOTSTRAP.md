# R279 — real native Monitor1 nonce2 funded/finalized; four actual small VM standby hosts independently inventoried; opt-in owner-local app wallets

## Fresh owner-evidenced chain31340 Monitor1 transfer FINALIZED

Owner actually ran new R276 eight tests **8/8 PASS** at previous
exact pinned Git SHA `fc50985a7bf067ff83485c931069211bc572863f`
on VM4707. Actual original native chain31340 read-only
forensic for previously consumed R267 Monitor1 marker returned:

- `transactionStatus=MATCHING_TX_SUCCESSFUL_CANONICAL_FINALIZED`
- Exact one-time Monitor1 funding TX
  `0xaf024159fe0b34d255689ab6ab5137c55aa247e7044f9792d56e6297ad447ebc`
- From VM4707 app-only deployer
  `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`,
  nonce **2**,
  to VM4707 actual encrypted EOA
  `0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147`,
  **5000000000000000 wei = 0.005 TEST ETH**.
- Actual canonical inclusion block **25739**; execution
  head **25956**, finalized height **25812**,
  `blocksUntilReceiptFinality=0`; monitor1
  real native latest AND finalized balances both
  5000000000000000wei.
- Sender latest and pending nonces both **3**.
  `monitor2PredecessorFinalizedEligible=true`.
- All exact gas/chain/provenance checks PASS.
- **No monitor1 retry is needed or allowed.**
  The original 'already consumed' earlier log was
  correctly avoiding a duplicate transfer and there
  was an ACTUAL already completed successful transfer.

### Last approved VM4707 funding stage: Monitor2 nonce3

The owner had explicitly authorized three exact native
funding transfers: consumer0.01, monitor1 0.005,
monitor2 0.005 TEST ETH, each gas max21000 at
1000wei/gas. The first two are now confirmed
finalized. The last originally approved stage remains
monitor2 `0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8`
nonce3, **5000000000000000 wei**. Run the already
tested R267 source at **previous exact checkout**
`fc50985a7bf067ff83485c931069211bc572863f`
only if there is NO consumed monitor2 attempt marker;
R267 refuses by default otherwise. Owner must still type
exact per-tx terminal approval, hidden VM4707 app deployer
wallet password; R267 writes nonretriable 0600 marker
BEFORE any RPC broadcast. A previously unreported
monitor2 broadcast is not ruled out by these results.
**Do not issue any additional funding or monitor bond
transaction without new separate approval.**

New R278 extends existing R276 public-only marker
forensic to `--role monitor-2` (once a nonce3 attempt
has been consumed). Strict comparison, real canonical
receipt/finality and recipient's balance; still NO
signing or broadcast. Five new mocked tests authored.
**R278 not yet executed on VM4707**.

## Actual NEW owner inventory: four small standby VM hosts

All actually observed by owner 2026-11-24, not simulated:

| VM | 2 vCPU | RAM total | RAM available | Disk available | OS | Docker and Python |
| --- | --- | --- | --- | --- | --- | --- |
| VM4711 | yes | 3.8GiB | 3.3GiB | 35 GB | Ubuntu 24.04 | Both CLIs exist |
| VM4712 | yes | 3.8GiB | 3.3GiB | 35 GB | Ubuntu 24.04 | Both CLIs exist |
| VM4713 | yes | 3.8GiB | 3.3GiB | 35 GB | Ubuntu 24.04 | Both CLIs exist |
| VM4714 | yes | 3.8GiB | 3.3GiB | 35 GB | Ubuntu 24.04 | Both CLIs exist |

Per-user: `ayoubakrvm4711` .. `ayoubakrvm4714`.
VM4711 has provider-private eth0 10.50.56.14,
VM4712 10.50.56.19, VM4713 10.50.56.21,
VM4714 10.50.56.22.
These **provider-private IPs are NOT public P2P or
remote monitor HTTPS reachability**. Two sets of
VMs share TEMPLATE hostname labels; do not use
template hostname as distinct machine identity
proof. Current distinct terminal logins and OS
resource observations establish actual separate VM
sessions, not independent physical faults, ownership,
provider cloud availability zones or public access.
Neither Docker running state nor current VM monitor
registration has been established on these hosts.

For the lab, propose locally-created encrypted
app-only monitor EOAs on VM4711, VM4712, VM4713,
and a provider EOA on VM4714. They are **not
permanent protocol-assigned roles**, just
independent test app identities. They still need
funding/bonds and any real HTTPS/WAN probe.
Original VM4709 previously created a provider
app-only encrypted EOA, but this dedicated small
VM avoids competing with the real PoS daemon
on VM4709. VM4707 funded monitor1 can be fourth
host-distinct monitoring candidate, but shared
administration/cloud still does not prove
independent adversarial fault domains.

## New simple R279 owner-local wallet bootstrap

GitHub `scripts/r279_standby_vm_app_identity.sh`
wraps the EXISTING audited
`tools/sse_pos_test_wallet.py` and
`requirements.txt`. It never creates a wallet
by default. Requires exact review-pinned Git HEAD,
clean tracked source, known nonroot owner OS username
among 4711–4714, no existing role wallet,
no symlinked app private path. `--preview`
reads only public filesystem/source metadata.
Explicit `--create` needs a real interactive
TTY and exact typed per-owner role consent phrase;
only then it creates an owner-private 0700
app EOA directory, private venv and installs
the existing pinned Python dependencies in
owner-local venv. Calls existing generator, which
asks for 16+ character secret twice (hidden),
creates one encrypted 0600 file, never overwrites.
No TEST ETH created, blockchain transactions,
native PoS node installs, Docker calls, BLS
validator custody access or public HTTP binding.

Fixed owner-to-role mapping FOR THIS TEST:
- `ayoubakrvm4711` -> `adaptive-v2-monitor-vm4711`
- `ayoubakrvm4712` -> `adaptive-v2-monitor-vm4712`
- `ayoubakrvm4713` -> `adaptive-v2-monitor-vm4713`
- `ayoubakrvm4714` -> `adaptive-v2-provider-vm4714`

7 source fake-identity/no-effects tests are
authored in `tests/test_sse_pos_r279_standby_vm_app_identity.py`.
**New R279 tests and owner wallet creation not yet VM-run.**

Owner per-host command once exact reviewed current
SHA is pinned in ChatGPT:

```bash
(
 set -euo pipefail
 SHA="<CURRENT_EXACT_FULL_GIT_SHA>"
 DIR="$HOME/sse-v2-standby-source"
 if [ -e "$DIR" ] && [ ! -d "$DIR/.git" ]; then
   echo "NON_GIT_PATH_REFUSED=true"; exit 2
 fi
 if [ ! -d "$DIR/.git" ]; then
   git clone -q --no-checkout https://github.com/AkrAyoub/sse-research.git "$DIR"
 fi
 cd "$DIR"
 git fetch --no-tags origin feature/r226-adaptive-v2-operator-runtime
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests \
   -p test_sse_pos_r279_standby_vm_app_identity.py -q
 bash scripts/r279_standby_vm_app_identity.sh "$SHA" --preview
)
```

After preview and tests PASS, owner may separately
run `bash scripts/r279_standby_vm_app_identity.sh
"<PIN>" --create` interactively on each host.
Do not paste any password, mnemonic, keystore
file JSON or signing key into chat or GitHub.
Only paste the public EOA address printed on
successful creation. Any new actual native
TEST ETH funding or EVM monitor bond/use requires
**separate new explicit authorization and exact
chain31340 nonce/spend/gas quote**; the original
three-stage VM4707 EOA funding approval does NOT
include these new standby identities.

### Next objective gates

1. Finalize previously approved Monitor2 nonce3
   (if not already attempted), validate via R278
   after its original one-use marker is consumed.
2. Actual R279 source tests and owner-local new
   app EOA creation on each distinct standby VM.
3. Choose 4 host-distinct monitor EOAs, get bounded
   TEST ETH funding consent, real `registerMonitor()`
   bonding from each host with no identical copied
   private EOA keys; at least four for `f=1`.
4. Deploy actual lease-committed pinned CPU worker
   on dedicated VM4714 with measured CPU/memory,
   strict isolated container config and HTTPS,
   without exposing native chain RPC or rootful
   daemon to public network.
5. Real independent HTTPS monitor probes and
   signed evidence from distinct machines,
   original-chain finalized onchain request/bids,
   seats/epochs, payout/refund/inconclusive.
