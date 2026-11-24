# R260 — Real V2 contract creation signed + submitted ON original native chain31340; finality and on-chain code NOT YET proven

## Actual owner VM4707 report, 2026-11-24

At exact pinned Git SHA `08f383680db5647192643a5d9fa2df5170c8877a`,
VM4707 `R257` gave **14/14** targeted deployment guard
tests PASS. It then passed the actual live PREVIEW against
original Besu RPC `http://127.0.0.1:28545`: R255
first app-wallet funding finalized, 1 native worthless TEST ETH
present at finalized, app nonce0, original genesis verified,
compiled constructor full initcode SHA256 matched exact
owner-approved value, estimated gas **6,670,081**,
proposed limit **8,342,601**, fixed gas price **1000 wei/gas**,
and predicted CREATE market address
`0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`.

The owner explicitly typed the approved single-deployment TTY
phrase `DEPLOY-ONE-V2-CHAIN31340-BOND-0.001-TEST-ETH`,
unlocked their **separately encrypted VM4707 app-only EOA**
with a hidden password, and successfully ran the R257
exact one-transaction signer/broadcaster. Public output:

- `R257_ONE_TIME_DEPLOYMENT_ATTEMPT_CONSUMED=true`:
  private create-once marker consumed; **NEVER rerun R257 --send**.
- Actual signed locally computed public transaction hash:
  `0xe9187bd24d72d2dec11fc6a2758802ddf6fa46a2941edd306329173fe132d6b6`.
- Actual Besu acknowledged this hash via one
  `eth_sendRawTransaction` request:
  `R257_ONE_SIGNED_DEPLOYMENT_SUBMITTED_NOT_YET_FINALIZED=true`.
- Signed source: app EOA
  `0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
  (NOT original Genesis execution owner).
- Signed nonce **0**, `to=null` EVM contract CREATE, value **0 wei**,
  constructor `minimumBondWei=1000000000000000`,
  signed gas limit **8342601**, gasPrice **1000 wei/gas**,
  absolute max gas fee **8342601000 wei**.
- Entire approved constructor initcode SHA256:
  `22d5b3310ec9a9efc66015762ea3d78d152f0a52eb9d67a257f18e3470c171ec`.
- Project-specific immutable application semantics remain
  unproved until on-chain successful finalized receipt/code:
  the contract constructor internally creates a separate
  immutable-linked vote ledger.

**What is NOT yet known**: whether Besu included a successful
creation receipt, market and ledger addresses really have EVM
code, code hashes, constructor immutable bindings, finality,
actual gas used, or actual remaining deployer balance.
The market address remains **predicted** until proven by receipt.
NEVER resend to find out; only READ-ONLY RPC allowed next.

## New R260 finalized deployment verifier (SOURCE ONLY; not VM-tested yet)

`tools/sse_pos_r260_v2_readonly_finalized_deployment_audit.py`
only reads original VM4707 localhost RPC; accesses NO
wallet/private key; signs/sends NOTHING and never touches
Lighthouse, Docker or nodes.

R260 checks all of the following before returning success:
1. Both real compiled Foundry V2 artifacts match audited
   native ABI source and the exact approved constructor
   bytecode SHA256, not merely contract name or ABI.
2. Original execution chain ID31340 and original Genesis hash,
   the actual first native R254 funding transaction's original
   sender/recipient/value/nonce/status and canonical finality
   **at its historical inclusion block**. Do not require the
   deployer to still hold the initial 1 ETH after spending gas.
3. EXACT contract CREATE transaction hash, sender, nonce0,
   null recipient, 0 tx value, fixed signed legacy gasLimit
   8342601, gasPrice1000, original chainId, exact approved
   byte-for-byte constructor calldata.
4. Actual `eth_getTransactionReceipt` successful status1,
   expected market CREATE contract address,
   gas used <=8342601, actual gasPrice <=1000, valid
   execution canonical block hash.
5. Live `eth_getBlockByNumber("finalized")` height covers
   creation block. If not, print actionable PENDING state
   and **DO NOT RESEND**.
6. At FINALIZED height, actual market `votes()` returns
   a separate ledger address, ledger `settlement()` is
   market address, and market `minimumBond()` equals
   the exact immutable owner-approved bond1e15 wei.
7. At FINALIZED height, BOTH actual EVM runtime codes
   are checked byte-for-byte against compiler-generated
   `deployedBytecode.object` **outside Solc-declared
   constructor-set `immutableReferences` slots**.
   Explicit known immutable words for market vote-ledger
   address and min bond, and ledger settlement address,
   must be present inside the compiler-declared slots.
   This avoids falsely equating the zero-placeholder
   compiled runtime to constructor-patched on-chain code.
   The remaining Solc-reported immutable words may include
   OpenZeppelin EIP712 cached domain fields; therefore
   only the nonimmutable byte-for-byte equivalence and
   known getter-linked immutable values are independently
   established, not every EIP712 cache constant individually.
8. Generate public R206 manifest with exact runtime
   SHA256 observed on the real finalized block. Run
   existing R206 to independently re-verify the
   transaction, canonical finality, SHA256 of both
   actual on-chain runtimes, and mutual immutable getters.
9. Only after ALL live checks return 0, optionally
   **create** a small owner-only file containing the
   public R206 manifest. The write is create-only; no
   existing evidence file overwritten.

R260 return markers:
- Success `R260_REAL_NATIVE_V2_MARKET_AND_LEDGER_FINALIZED_AND_R206_VERIFIED=true`;
- Still pending, return code3,
  `R260_NOT_FINAL_YET_DO_NOT_RESEND`, including
  receipt inclusion/finalized heights when known;
- Mismatch/refusal return code2,
  `R260_DEPLOYMENT_AUDIT_REFUSED`. Do NOT bypass.

Eleven new focused synthetic/mock regressions exist in
`tests/test_sse_pos_r260_v2_readonly_finalized_deployment_audit.py`.
**Neither focused tests nor R260 real RPC verification
have been observed run on VM4707 yet.** This verifier
deliberately does not reuse R255's original requirement
that the app deployer have >=1 ETH at the *current finalized*
height; that would incorrectly fail as soon as the
actual contract deployment has spent network gas.

## Owner next exact command

Fetch exact pinned R260 Git HEAD given in chat on VM4707.
Run `python3 -B -m unittest discover -s tests -p
'test_sse_pos_r260_v2_readonly_finalized_deployment_audit.py' -q`;
then execute real read-only checker:

```bash
python3 -B tools/sse_pos_r260_v2_readonly_finalized_deployment_audit.py \
 --rpc http://127.0.0.1:28545 \
 --manifest-out /tmp/sse-r260-v2-finalized-deployment-manifest.json
```

In case of pending, re-run ONLY this read-only R260
checker after consensus finalization; **never R257 --send**.
On full success and generated public manifest, run:

```bash
python3 -B tools/sse_pos_r206_adaptive_v2_deployment_audit.py \
  --manifest /tmp/sse-r260-v2-finalized-deployment-manifest.json \
  --rpc http://127.0.0.1:28545
```

Then use the public manifest on VM4706 to independently
reverify against `http://127.0.0.1:18545` with R206;
copy only manifest PUBLIC JSON, no keystores or passwords.

Deployment alone does NOT prove independent physical SLAs,
permissionless public Internet joins, independent validator
operators or unbiased VRF; all remain active actual research
implementation gates.
