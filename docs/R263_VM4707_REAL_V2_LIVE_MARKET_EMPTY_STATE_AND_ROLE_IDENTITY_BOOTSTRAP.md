# R263 — Actual original chain31340 marketplace live, EMPTY; 7-block finality gap; begin role bootstrap

## Owner VM4707 actual R262 output on 2026-11-24

Exact source commit `57881c8bbe3ce1d8d56d806ab85c93120e8865ce`,
existing local Besu `http://127.0.0.1:28545`.
NEW targeted R262 tests **5/5 PASS** and genuine read-only
`R262_REAL_V2_LIVE_ROLE_READINESS_READONLY_NO_TX=true`.

- Correct chain31340/original genesis, successful canonical
  exact one-time deployment receipt in block **25339**.
- Real latest EL execution height **25476**,
  actual finalized height **25332**, only **7 blocks**
  short of creation inclusion. **R260/R206 not yet run
  after finality**; do not prematurely assert FINALIZED.
- Real Market `0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`,
  runtime SHA256
  `aed48968f9b5ef4e8f238efaed8c539af5c8799de181f290b38a21803386c261`,
  Ledger `0x6635849b77f037fab611736612d7d3493dc650ff`,
  runtime SHA256
  `3a14ac0cd120271c50ac31661b6080546477aa8218e9944e51dd89998b78622d`.
- Full live Solc runtime nonimmutable parity + three known
  compiled immutable values: **TRUE**.
- `activeMonitorCount=0`;
  `nextRequestId=1`, `nextLeaseId=1` (no actual
  resource requests/leases created yet);
  all outstanding service escrow, monitor funding,
  bonded monitor escrow, withdrawable balances = **0**;
  actual Market and Ledger native balances = **0**;
  both real onchain escrow-liability conservation checks PASS.
- No keys read, no transaction sent, no physical provider,
  monitor or SLA evidenced. These are facts, not planned results.

## First concrete V2 application milestone after finality

The current Solidity deployment requires at least **4** distinct
eligible active monitor EOAs for one Byzantine-fault-tolerant
committee under fault tolerance `f=1` (`3f+1`),
plus a distinct consumer EOA and provider EOA. Every
`registerMonitor()` transaction sends at least immutable
bond **1000000000000000 wei** into the actual onchain market.
The consumer request and provider bid are separate signed
transactions; funded service lease subsequently requires
the provider's real CPU/HTTPS resource and monitor runtime.

Do NOT assert 4 physically independent monitors based on 4
wallets under one VM/provider. The immediate test can establish
4 separate cryptographic accounts and real funds in a
LAB functional environment, then a WAN/multi-operator study
must independently verify real fault domains and resource
measurement. The user's separate requirement for permissionless
joinability is NOT met merely by local account files.

### Wallet creation reuse, no new insecure keys or funder

The EXISTING reviewed GitHub application wallet generator
`tools/sse_pos_test_wallet.py` safely generates random
encrypted UTC-V3 EOA keys in a user-owned private
0700 directory and 0600 files, prompts for a password
twice via hidden TTY, never outputs secrets, and
refuses overwriting an existing wallet. This can run
on any participating VM with its own private
`OUTPUT_DIR` and actual host-local venv. This is a
**wallet creation only** step, not a claim of independent
operators, a funded account, or an on-chain role.

Suggested six **distinct** test identities if the owner
wants the full functional protocol test before recruiting
outside operators:

- `adaptive-v2-consumer`
- `adaptive-v2-provider`
- `adaptive-v2-monitor-1`
- `adaptive-v2-monitor-2`
- `adaptive-v2-monitor-3`
- `adaptive-v2-monitor-4`

Place provider/monitor keys on actual hosts that will
operate those roles, with no private key copied between
machines. The VM4707 role directory has already been
verified private for its existing funded deployment EOA;
check any different VM's private directory before creation.
A proper real independent monitor experiment eventually
needs 4 independent hardware/operator fault domains, not
simply 4 cryptographic aliases.

**Owner already authorized and consumed exactly one market
CREATE and exactly one prior funding transaction**. Neither
authorizes any further TEST ETH transfers, bonds,
registrations or workload bids. After collecting public
role addresses, quote bounded real native funding from
an owner-controlled EOA, obtain fresh explicit individual
authorization, then submit per-role transactions using
the R242 one-transaction consent gate. Do not default
to the original VM4706 Genesis or BLS validator keys;
the EXISTING app deployer on VM4707 may have a spendable
remaining balance but any new use requires a separate
approval after live balance/nonce checks.

## Immediate finality acceptance (read-only, single invocation)

Once local EL finalized block is >=25339, use:

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
"$PY" -B tools/sse_pos_r260_v2_readonly_finalized_deployment_audit.py \
 --rpc http://127.0.0.1:28545
"$PY" -B tools/sse_pos_r206_adaptive_v2_deployment_audit.py \
 --manifest evidence/r261_vm4707_latest_state_v2_deployment_candidate.json \
 --rpc http://127.0.0.1:28545
```

R260+R206 must PASS before any real R242 role submission;
neither R257 --send nor R254 must ever be retried.
