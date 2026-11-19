# R17 — actual SSE PoS deployment receipt provenance and next live SLA run

**Date**: 2026-11-19. Operator host: VM4705 (Ubuntu 24.04).
**Chain**: our own Ethereum-PoS 31339, valueless TEST ETH.
**Status**: first SSE contracts deployed; genuine consumer→provider→monitor
SLA flow is NEXT, not yet witnessed on this chain.

## Observed verified operator deployment log

The operator checked out EXACT source revision
\`cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef\` (R16).
All **33/33 targeted Python PoS tests** and **147/147 Foundry
Solidity EVM tests** passed. \`forge build --sizes\` compiled with
Solc0.8.24, all deployed code EIP170 compliant:
OpenMonitorCommittee22670 bytes (1906 free), SSESettlement22311B
(2265 free), OpenResourceBoard3739B (20837 free).
The first truly successful R16 script simulation reported 7
transactions, then the operator ran
\`forge script ... --broadcast --slow\` with an encrypted owner
faucet keystore. It reported **ONCHAIN EXECUTION COMPLETE & SUCCESSFUL**,
7 tx receipts at actual blocks953–959 and aggregate gasUsed10947092.

Address sources below are **reported actual deployed contracts** in
the operator trace, not simulated placeholders:

| Contract | Address |
|---|---|
| OpenMonitorCommittee | \`0x9965bAC16C5Df538df0373a906e42eA0E0C327d9\` |
| SSESettlement | \`0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F\` |
| OpenResourceBoard | \`0xF1147CA8aC9e28F845529A6Ae5837873806C7788\` |

Genesis execution block0:
\`0x2aab680cd1b5fe856566eb81eae181b8f15b0cdfb6bdd218180f793371df97f5\`.
Faucet EOA (PUBLIC):
\`0x1D987dBFEB682Ff4bD88EfAc293f132e233168e7\`.

| Step | Block | Transaction hash |
|---|---:|---|
| Deploy monitor committee | 953 | \`0xb3d144f1a627ccd7ee46b30fb814fea6ee720263d302d4dfe2fbc62efc010294\` |
| Enable delayed entropy | 954 | \`0x9489d36d0cdb8688f23cb859144e7643aab62e7d68e521785d5d343425c2308e\` |
| Deploy settlement | 955 | \`0x39d6879d3a099bd1923df7336d9c3cb5fa247ea4ee204ba57fcc93d533c497af\` |
| Deploy resource board | 956 | \`0x832b21b4d84581e6c8ca35e60117feb8354d20a0d5716b033fa598705dbba00d\` |
| Bind committee → settlement | 957 | \`0xcbb5bd988a7ec719624ba03eec9d166231980ac2bf2a6afb4fa57c7600c9ac78\` |
| Bind settlement → board | 958 | \`0x9f94a3b4ecef4dcaa27612e045342bd1dba81db4be69ce0571cac24129404ded\` |
| Bind board → settlement | 959 | \`0xfe316af856b79694c58b4a3fb1195da1eb979a7c2ea04f33e81063a99786a468\` |

Recorded sum gasUsed 10947092, total charged fee in printed
operator report \`0.000000000087576736\` UNVALUED TEST ETH. This
report is not a financial mainnet cost.

## Independent read-only on-chain verification — R17 code

A previous checker \`tools/sse_pos_contract_attest.py\` verifies
real code presence, correct mutual address bindings, positive monitor
bond, delayed entropy and both disabled global-election switches.
New R17 checker \`tools/sse_pos_deploy_receipts.py\` additionally
fetches all seven txs and receipts from the live Besu RPC and verifies:

1. exact chain31339 and pinned execution genesis;
2. actual Beacon finality exists (without conflating it with tx finality);
3. seven receipts status=1, blocks953–959, canonical block hashes;
4. faucet sender and nonce sequence 0–6 and zero transfers;
5. three contract creations at exact observed addresses;
6. correct method selectors and actual 20-byte binding arguments;
7. total on-chain gasUsed10947092, no missing or altered txs;
8. actual mutual contract bindings and security mode status;
9. \`eth_getBlockByNumber("finalized")\` height, **only** marking
   deployment tx finality true when that height covers block959.

The checker never decrypts any wallet or broadcasts transactions;
all evidential constants are public and were extracted from the
operator's successful deployment receipt transcript. If RPC cannot
serve a finalized execution block, this tool reports
\`deploymentTxFinalityProved=false\` rather than inventing finality.

Run from the EXACT approved new R17 GitHub checkout:

    cd ~/sse-pos
    source .venv-pos/bin/activate
    git fetch origin integration/r7-wp09q-wan-multivm-no-actions
    git switch --detach APPROVED_R17_SHA
    python -m unittest discover -s tests -p 'test_sse_pos_*.py' -v

    python tools/sse_pos_deploy_receipts.py \
      --rpc-url http://127.0.0.1:32770 \
      --beacon-url http://127.0.0.1:32774 \
      --require-tx-finality

If execution 'finalized' tag is not supported, retry with
\`--require-tx-finality\` removed: it will still verify canonical
receipts and independent Beacon finality, while explicitly marking
tx-finality unproven. DO NOT make permissionless P2P claims.

For independent binding inspection without known original tx hash
inputs use:

    python tools/sse_pos_contract_attest.py \
      --rpc-url http://127.0.0.1:32770 \
      --committee 0x9965bAC16C5Df538df0373a906e42eA0E0C327d9 \
      --settlement 0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F \
      --board 0xF1147CA8aC9e28F845529A6Ae5837873806C7788 \
      --source-commit cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef

Source commit is a *provenance claim from operator execution*,
NOT automatically proven by bytecode hash equivalence. If publishing,
archive verified Foundry build artifacts plus constructor immutable
references and code hashes separately.

## NEXT: real resource lease, independent role wallets and monitor votes

Current deployed contracts have **zero registered monitors and no
resource lease evidence yet**. Create **new encrypted EOA keys** for
consumer, provider and at least five bonded monitor identities. They
must be different from faucet and from one another. The 32 genesis
BLS validators are consensus participants, NOT these monitor EOAs.
Roles do not need SSE administrator permission. Never share passwords
or upload keystores/mnemonics to GitHub. On the private VM:

    for role in consumer provider monitor01 monitor02 monitor03 monitor04 monitor05; do
      python tools/sse_pos_test_wallet.py \
        --role "$role" --output-dir "$HOME/sse-pos-wallets" --apply \
        || break
    done

The script refuses duplicate keystores; do not delete any created
wallet to retry blindly. All seven new EOAs start at 0 test ETH and
must receive their OWN test-ETH from the funded faucet. This is a
lab faucet operation, NOT a real market purchase. A new GitHub-first
on-chain role runner should (a) verify chain31339/genesis;
(b) safely fund the new wallets through the encrypted faucet; (c)
register at least 5 monitors with the positive 1e15-wei bond;
(d) create request/bid/funded lease with distinct consumer/provider;
(e) wait for the actual +DELAYED_ENTROPY_BLOCKS future block and
apply permissionless selection; (f) obtain all four monitor
confirmations; (g) admit epoch, collect synthetic-but-labeled
HTTP/service evidence, submit EIP712-signed provider response and
monitor votes; (h) wait actual monitoring/evidence windows, seal and
settle/refund/withdraw with receipts and gas measurements. Do not
fast-forward a live PoS chain via Anvil RPC; use the real slot clock
and record actual delays. Avoid implying that synthetic ACK/votes
prove real cloud delivery.

SECURITY: First upstream launch leaked the 24-word bootstrap
validator mnemonic and several premine private EOAs into an
operator transcript. This current single-host chain is therefore
a **tainted isolated research smoke chain**. Keep inbound discovery
ports restricted, don't use any real ETH, don't open remote staking
until a NEW safe genesis and separately held validator keys exist.
No political mining analogy: chain now uses actual Ethereum PoS
proposer/attester slots, not PoW miners.
