# R5/R7 — Funded marketplace winner delivers a signed compute result

**Status:** experimental implementation and opt-in integration test **committed**, but **not yet executed by the operator**. Previous branch `a818fda` passed 603 Python tests (599 passed, 4 skipped). Solidity baseline previously passed 127 Foundry tests. Neither result proves this newest code works until rerun.

## Exact research objective

A selected provider should fulfill a consumer's paid request **directly** over the private service network, rather than making the global SSE network dashboard act as a bidder, consumer, provider or signing proxy.

The test `tests/test_sse_direct_delivery_anvil.py` uses fresh real `OpenResourceBoard`, `SSESettlement` and `OpenMonitorCommittee` deployments on a temporary loopback-only Anvil chain. It verifies:

1. Consumer (wallet 0) publishes a request committing immutable `sse-resource-profile-v2` and `sse-service-sla-policy-v1` manifests, maximum price 45 wei and bidding close.
2. Two **different** provider wallets compete: provider A bids 31 wei, provider B bids 25 wei.
3. Consumer chooses bid **index 1** and funds 25 wei (zero reservation under experimental delivery-only SLA). Settlement stores provider B, request ID, endpoint, profile and policy hashes.
4. Five independent **EOA signatures** bond as monitor candidates; four selected monitor wallet identities confirm, using **lab-only source-controlled entropy**. Separate EOA accounts are NOT evidence of separate VMs or independent operators.
5. Consumer admits epoch 0. Both peers use read-only `inspect_chain(..., pin_block_hash=True)`, including EIP-712 domain, to validate active funded lease identity and hash commitments.
6. Losing provider A fails the provider-authentication check; the winning provider B accepts the signed EIP-712 work order, computes the deterministic SHA-256 result, returns signed result bytes + Solidity-compatible V1 challenge signature, and receives a consumer-signed receipt over actual loopback HTTP.
7. The winning provider's **durable local SQLite replay journal** stores work order, response, and receipt, and rejects duplicate signed nonces. The consumer can relay provider B's V1 `ProviderResponse` signature to the actual `SSESettlement.submitProviderResponse` function; receipt inspection must show `responseAuthenticated = true`, zero monitor votes, and no claims of verified CPU provisioning or trusted clock.
8. Both the smart contract and the signature code must reject an unauthorized provider role. The direct exchange does **not** settle escrow or claim a physical SLA-certified success.

The temporary public Anvil mnemonic is development-only; never deploy its keys to any Ubuntu VM, Sepolia, or real-value network. No externally exposed services and no Docker were used in this particular test.

### Crash-safe journal limitation

`tools/sse_direct_journal.py` creates a local owner-only SQLite journal, requiring a precreated private directory and file mode 0600. Its durable statuses are `RESERVED`, `RESPONDED`, `RECEIVED`. A signed request gets reserved **before** execution; a crash between reservation and response blocks replay and needs explicit reconciliation. This favors avoiding duplicate executions over automatic re-delivery.

In `services/provider-agent/direct_work_service.py`, a real `--serve` now requires `--journal-file /path/inside/an/owner-only/directory.sqlite`; off-chain unit tests may still use the in-memory mode for isolated test fixtures. The archive is not globally immutable, independently replicated, or an EIP-712 monitoring certificate. Each host's wallet and journal remain separate. The consumer still needs durable pre-send/post-receipt recording, a dedicated follow-on task.

### Run validation from repository root

```bash
git status --short
git fetch origin research/r5-r7-real-lease-direct-exchange-no-ci
git switch --detach origin/research/r5-r7-real-lease-direct-exchange-no-ci
git rev-parse --short HEAD
python -m unittest discover -s tests -p 'test_sse_direct_journal.py' -v
python -m unittest discover -s tests -p 'test_sse_sla_direct_delivery.py' -v
python -m unittest discover -s tests -q
forge build
SSE_RUN_ANVIL_INTEGRATION=1 python -m unittest discover -s tests -p 'test_sse_direct_delivery_anvil.py' -v
```

The standard Python suite should discover **611 tests** (603 prior + 7 journal + 1 new optional real-Anvil), with five expected skips until opt-in. The new real-Anvil test requires the installed `anvil`, `forge build` output, `eth-account` and `eth-abi` dependencies; it uses a disposable localhost chain and does not interact with any remote VM.

**If the new real-Anvil test fails**, send the full traceback; do not interpret its test design as a passed result. The correct acceptance test is an EVM-funded consumer-selected provider exchange, not just an on-chain request and an unrelated HTTP echo.

### Still open before Ubuntu fleet readiness

- Reproduce test on **independent Ubuntu VMs** using automatic Tailscale installation, broker provisioning, restrictive ACLs, and Tailscale Serve private HTTPS.
- Replace lab-only entropy with verifiable or otherwise defensibly unbiased production committee selection; prove independent monitor operation and adversarial network-partition behavior.
- Run actual agreed workloads inside pinned, isolated Docker containers with enforceable CPU and RAM limits; evaluate what can and cannot be independently verified.
- Persist **consumer-side signed evidence**, handle request retries after crashes, and replicate evidence off host before grading availability.
- Wire authorized role-local UI actions for bidding, award selection, execution, provider response, monitor submissions, and safe runtime controls; the independent network dashboard remains nonparticipant observer.
- Develop qualified real service-specific probes and adjudication policy. A signed result, receipt or three matching timeouts does not in itself establish physical delivery, trustworthy time, or a legitimate SLA failure.
- Test full independent network economics and produce reproducible evaluation/report/publication artifacts.
