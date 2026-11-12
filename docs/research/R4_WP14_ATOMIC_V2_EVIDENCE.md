# WP-14 — Storing signed HTTP observations with their exact V2 chain reference

## Why I changed the archive instead of just adding another field

WP-13 can verify the V2 lease, pending epoch, provider, selected monitors and each monitor's active ticket at one blockchain block. WP-08B can fetch a signed HTTP response and store a monitor's signed observation. But they ran separately: a saved response had **no durable statement of the exact on-chain state used to authorize it**.

That matters during a dispute. Suppose monitor M3 observed a response while it was selected, then failed a later assignment and was replaced. If someone reopened the report against the *current* committee, it would appear unauthorized. The opposite error is also possible: a forged current roster could be supplied to justify an older report.

I decided to keep the WP-08B archive unchanged and create a separate V2 archive. Its entry must bind the actual signed bytes to a particular historical block reference, and checking it later must reconstruct authorization at **that same block**, not at `latest`.

## How the write works

1. Read a V2 lease/epoch/committee snapshot using the WP-13 pinned-block reader. Independently configured runtime-code hashes are mandatory.
2. Check that the chosen monitor is among the selected, confirmed, bonded seats before making an HTTP request.
3. Make one bounded numeric-loopback POST to the provider. Verify the provider's legacy off-chain EIP-712 `ProviderResponse`, then create the monitor's distinct EIP-712 `SSEEvidenceObservation` over the exact received bytes.
4. Before writing, **read the same historical block again**. Require the archived block hash to agree with the canonical height and be at or below the RPC's chosen `finalized`, `safe` or `latest` tag. Every contract call uses EIP-1898 `{blockHash,requireCanonical:true}`. Do not accept a forged Python snapshot object as authority.
5. Reverify both signatures, the exact payload hash, all lease/SLA/request/endpoint bindings and committee membership.
6. Serialize the chain reference and signed observation as canonical ASCII JSON. The reference commitment is `keccak256("SSE_V2_AUTHORITY_REFERENCE_V1\\0" || referenceBytes)`. The entry ID domain-separates the evidence ID, signer and chain-reference commitment.
7. Run one SQLite `BEGIN IMMEDIATE` transaction storing **provider bytes + monitor envelope + reference bytes + commitment + signer + nonce**. Either everything commits or no row is inserted.
8. Enforce `UNIQUE(chain,controller,lease,epoch,monitor,nonce)`. Exactly matching retries return the existing entry; reusing a nonce with a changed report or block reference raises an error, even after restarting the program.

These decisions fix provenance and replay *within this local archive*. They do not put raw evidence on-chain or establish a physical delivery fact.

## How a read works later

An independent caller provides its trusted V2 configuration and the original entry ID. The loader reads the archived reference, insists on canonical JSON and the same finality-tag assumption, then reruns the V2 authorization reader at the **archived block number and hash**.

It checks the canonical block at that height against the RPC, requires that the permitted chain head is not behind the archived block, recomputes the full authority bytes and commitment, rechecks the signed HTTP response and monitor signature, and matches every archived metadata field to the reconstructed scope.

This makes historical verification possible even if a *later* committee changes or the epoch closes. It does **not** turn the archived block into an independently proven consensus fact. The RPC and availability of historic block-state queries remain dependencies. A pruned RPC, unsupported EIP-1898 implementation or a reorganization causes a fail-closed error.

The file is still deletable by the host who owns it. For genuinely distributed evidence availability we must publish an append-only digest externally or replicate authenticated copies across independent parties.

## What the archive can prove—and what it cannot

An intact entry supports a conditional statement of the form:

> Under the nominated RPC's canonical block view and the independently trusted deployed-code fingerprints, this selected V2 monitor signed these exact received provider bytes for this exact pending epoch.

It **cannot** prove:
- the consumer received the response, much less received it before the SLA deadline;
- the provider's response reached any remote host other than the reporting monitor;
- the RPC's finalized tag or account/storage state without an independent proof;
- the monitor's local timestamp is a trustworthy physical clock;
- the archive host did not delete other records or withhold access;
- real VRF fairness, independent monitor organizations or a sound N/F/S world-exclusion certificate.

The V2 controller still requires consumer and provider's exact bilateral EIP-712 allocation signatures. **No archive entry and no monitor signature can move escrow by itself.**

One namespace detail stays explicit: the provider HTTP signature is still the legacy *off-chain* `SSESettlement/1 ProviderResponse` format, with V2 controller address in its verifying-contract field. V2 uses a different `SSELeaseControllerV2/2 EpochAllocation` domain for on-chain funds. A fully native provider-response V2 wire version remains open.

## Verification I ran

The branch adds `tools/sse_v2_provenance_archive_v1.py`, extends the WP-13 reader to permit a separately verified historical anchor, and adds **36 Python tests** in `tests/test_sse_v2_provenance_archive_v1.py`.

The tests include a **real localhost HTTP server using EIP-712 provider signatures**, a monitor-signed observation, SQLite reopen/restart, identical replay, changed-report and changed-block nonce conflict, concurrent writers, forced transaction rollback, mutated provider bytes, monitor signature, reference JSON, reference commitment, metadata and signer; additionally wrong monitor authorization, wrong runtime code, block reorganization, archived block ahead of finalized height, unsupported root directories, and rechecks at the originally selected block even after a newer finalized head exists.

Initial hosted CI run: https://github.com/AkrAyoub/sse-research/actions/runs/43196133501
- Python Ubuntu: **410/410** (374 inherited + 36 new), no failures or skips
- Python Windows: **410/410**, no failures or skips
- Foundry: **124/124** existing tests, no failures or skips

The Ethereum RPC for these new archive tests is **synthetic**. The HTTP exchange, signatures, SQLite transactions and evidence tampering are real within the local test environment. This does not establish live Anvil archive compatibility or external Ethereum finality.

## What I would do after review

1. Review/merge the existing V2 dependency chain (#9→#10/#11→#12→#13). Retarget/retest WP-14 after upstream merges; do not merge branch duplicates blindly. PR #8's V1 authorization remains independent.
2. Use a **live local Anvil chain** with a funded V2 lease and confirmed committee to exercise EIP-1898 `eth_getCode` and `eth_call` compatibility and produce an actual archive entry from an RPC block.
3. Publish an external append-only reference digest and test multi-process/multi-host archival availability, including adversarial delete, stale RPC and network partitions.
4. Create a distinct V2-native EIP-712 ProviderResponse wire schema and key-management policy rather than reusing the legacy message forever.
5. Research what physically trustworthy consumer receipt or bounded-delivery certificate would soundly exclude N/F/S worlds before attempting any autonomous monetary allocation.

**Acceptance level:** tested conditional V2 signature provenance, local atomic retention and restart-safe nonce constraints—not physical-delivery qualification or production Ethereum state verification.
