# R265 — Three actual VM4707 encrypted consumer/monitor wallets created, propose native TEST ETH funding

## Genuine VM4707 owner output (2026-11-24)

Owner ran existing `tools/sse_pos_test_wallet.py --apply`
three times in an existing private owner-only application
wallet directory. Each distinct role produced **walletCreated:true**,
`encryptedWithPassphrase:true`, `privateKeyPrinted:false`,
`passphraseStored:false`, `ethereumTransactionsSent:false`,
`testFundsCreated:false`, no validator key or mainnet.
Password was typed privately twice per wallet.

**PUBLIC application EOA identities and their actual host:**

1. VM4707 `adaptive-v2-consumer`:
   `0xD74A2aBC5a906BaFe39471CEe222c48BDD62DE3f`
2. VM4707 `adaptive-v2-monitor-1`:
   `0xd63b2Ba14E8aD16Cf5f494259dAE05AD59fE0147`
3. VM4707 `adaptive-v2-monitor-2`:
   `0xf8D4c882A7439507e2fc237DCBDf4A1c228F0FF8`

Source public evidence:
`evidence/r264_vm4707_created_application_role_public_addresses.json`.
The keys are **encrypted owner-local files** in
`~/.local/share/sse-v2-app-only`, not stored in GitHub;
none was used to sign or fund any native transaction yet.
Three wallets on ONE VM are **not physically independent
monitor operators**. A fully independent four-monitor
multi-operator experiment still requires different fault
domains; new provider and two additional monitor EOA
identities MUST be created by actual owners on chosen
other participating hosts.

Existing real V2 contract:
`0x6C01dBd7aA336a96d8Ab09Ea631E209612224080`;
existing fully known live ledger:
`0x6635849b77f037fab611736612d7d3493dc650ff`.
Actual VM4707 R262 five unit tests PASS plus live
market EVM read-only success: activeMonitorCount **0**,
nextRequestId **1**, nextLeaseId **1**, zero escrow
and zero actual contract balances. Actual finalized
EL block **25332**, deployed success block **25339**,
**7 blocks** remaining. Do not claim finality before R260
and R206 both PASS. Deployment R257 and original Genesis
R254 transfer authorization were consumed; no rerun.

## New read-only actual native owner funding quote — R265

`tools/sse_pos_r265_vm4707_three_role_wallet_funding_quote.py`
is a **new proposed RESEARCH BOOTSTRAP budget**, not
a transaction or spending approval. It always uses only
public new EOA addresses in the exact owner output,
app-only already funded VM4707 EOA
`0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0`
as POSSIBLE future source; original Genesis owner EOA
and Lighthouse BLS keys are NEVER used.

Suggested small transfers (worthless native research TEST
ETH, not meaningful economically):

| Recipient | Proposed value | Why |
| --- | ---: | --- |
| consumer VM4707 | 0.01 TEST ETH | sufficient proposed lab escrow/gas cushion |
| monitor 1 VM4707 | 0.005 TEST ETH | > actual 0.001 TEST ETH min registration bond |
| monitor 2 VM4707 | 0.005 TEST ETH | > actual 0.001 TEST ETH min registration bond |
| **TOTAL** | **0.02 TEST ETH** | unapproved researcher scenario |

Every simple native EOA transfer is quoted with fixed
**21,000 gas** * **<=1000 wei/gas**;
gas fee <= **21,000,000 wei each** and <=
**63,000,000 wei total** for 3 proposed transfers,
so maximum cumulative source debit for these proposed
three transfers = **20,000,000,063,000,000 wei**
(0.020000000063 TEST ETH). The amounts are a
choice for owner review, **not** chain-derived SLA economics.

R265 gates the quote on original chain31340 Genesis,
actual successful canonical market CREATE receipt,
existing VM4707 app-only funder pending nonce **1**,
funder balance enough for all proposed transfer value
plus upper gas, live node gas/base fee <=1000 wei,
each destination exactly one of the actual new public
wallets, each has NO CODE, ZERO current native balance,
ZERO pending EOA nonce, actual `eth_estimateGas=21000`.
Any mismatch refuses without signing, and any later
nonce2+ activity requires fresh review.
No keystore is loaded, unlocked, signed or uploaded;
NO `eth_sendRawTransaction` or other send code exists.
This is not evidence of wallet signing-key custody or
hardware operator independence. R265's eight new
mock tests are authored but **not yet actually run
on VM4707**.

## Immediate owner commands (exact latest pinned SHA in chat)

Run full R260+R206 verification ONCE when finality allows;
it may still return pending, which is safe. Run R265 quote
even if R260 remains pending (without authorizing a send):

```bash
PY=/tmp/tmp.Ridv9nIavf/testvenv/bin/python
"$PY" -B -m unittest discover -s tests \
  -p 'test_sse_pos_r265_vm4707_three_role_wallet_funding_quote.py' -q
"$PY" -B tools/sse_pos_r265_vm4707_three_role_wallet_funding_quote.py \
  --rpc http://127.0.0.1:28545
```

Next after owner review: implement an EXACT quoted
one-use owner-local native transfer sender with separate
explicit approval for each value/recipient/nonce, safe
keystore unlock, one-shot broadcast marker and finality
read-only audit. **NO approval of any additional funding,
bond, resource bid or registration has been given.**
Actual VM4707 app-only EOA may have balance left after
deployment but that fact does NOT imply approval to
spend any of it.

After role funding is individually authorized,
use R206-finalized-gated R242 to register actual
bonded monitors; keep the 0.001 TEST ETH policy
as research test policy, NOT Sybil protection.
