# Verified state and gaps — 2026-11-19

**Public network acceptance: NOT MET.**
The architectural target is defined in [ARCHITECTURE.md](ARCHITECTURE.md).
Do NOT confuse private single-host smoke data with a permissionless,
Internet-public deployment. Research claims require actual observations.

| Observation | Evidence and exact scope |
|---|---|
| Private PoS smoke VM | VM4705, 4vCPU/11GiB, Besu EL+Lighthouse CL/VC, all operated on ONE host |
| Consensus | Execution blocks increased to at least 1157; Beacon finalized checkpoint previously observed |
| Deployed source | SSE Solidity R16 commit `cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef` |
| Committee | `0x9965bAC16C5Df538df0373a906e42eA0E0C327d9` |
| Settlement | `0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F` |
| Board | `0xF1147CA8aC9e28F845529A6Ae5837873806C7788` |
| Deployment receipts | Seven canonical successful tx in blocks 953–959, 10,947,092 total gas; **finalized by execution block 1088**, verified by VM4705 R18 tool |
| Python tests | **51/51** targeted `test_sse_pos_*.py` passed at Git SHA `f846e770744fb18f3364801781d9075498eacc6b` |
| Foundry tests | **147/147** EVM Solidity tests passed at R16, source/contract changes not made since |
| Faucet | 1M genesis-allocated TEST ETH; no real ETH |
| User wallets | Faucet, consumer, provider and monitor01–05: eight encrypted local keystores on VM4705 |
| Local role funding | Attempt failed BEFORE broadcast in R18 due to EIP-55 checksum; R18b fix passed 51/51 Python tests, not yet retried live |
| Monitor bonds | **ZERO active registered candidates** in latest user-observed read-only plan |
| SSE real workload | **No real cross-host consumer/provider/monitor SLA execution witnessed** |
| Public PoS P2P | **No independent remote P2P peer or dynamically readdressing seed witnessed** |
| Public validator joining | **No new BLS deposit/activation from an independent host witnessed** |
| Genesis key security | First upstream PoS launch printed genesis consensus mnemonic and premine private keys. **Compromised for any Internet-public use.** |

**Important distinction:** The successful ledger is genuine PoS and
the three SSE contracts genuinely exist there. But 32 genesis
validator BLS identities under one operator, and seven application
EOAs under one VM, do not represent independent operators. A quorum
of four SSE monitors on one VM is also not physical independence.

**New public system:** None of the entries above establishes the
fresh multi-operator public chain31340, public reachable P2P, or
permissionless external validator entry. It has to be launched with
independently created **non-exposed** genesis keys. No legacy
QBFT/Tailscale gate is acceptable as a substitute.

## Repository hygiene

The former `main` at `7e86edb9aff6a2e45eac940cf7ced3b2c88f2bea`
was 264 commits behind the R18b working integration branch and
incorrectly presented Anvil as the current runtime. The cleanup
work is reviewed on `refactor/permissionless-public-pos-mainline`
with a PR to `main`. Before merge, run Python/Foundry tests on a
clean checkout and review retained executable dependencies.
The snapshot branch
`archive/legacy-pre-public-pos-2026-11-19`
preserves the full previous integration tree for historic grading,
research reproducibility and potential migration.

CI/test status and current architecture MUST be refreshed from the
exact new GitHub commit: no static audit document or passing mock
unit test can prove live public Internet behavior.
