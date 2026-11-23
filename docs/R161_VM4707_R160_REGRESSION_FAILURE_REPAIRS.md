# R161 — Repair of actual VM4707 R160 regression failures

**Observed on VM4707 at pinned Git SHA**
`6828aaf0c516799fb76c01ba213ed6c445882f40`:

```text
Ran 1093 tests in 17.566s
FAILED (failures=1, errors=4, skipped=3)
```

This is **not a green test result**. The earlier verified baseline remains
R153: 1047 tests, OK, 3 skipped.

## Five errors diagnosed and fixed in GitHub

| Failing regression | Root cause | Corrective change |
|---|---|---|
| R151 `test_preexisting_archive_never_overwritten` | A deliberately invalid preexisting archive raised `r136.Refused` through `prepare_original_archive` instead of the R151 fail-closed interface's `Refused`. | Explicitly normalize R136 archive-verification refusal to an R151 refusal without modifying or replacing any preexisting bytes. Test operates on isolated temporary path. |
| R152 `test_exact_signer_verifies_and_returns_only_signed_plaintext` | The newly written fixture used literal backslash-n sequences (`\\n`) instead of newline-separated GPG `pub:`/`fpr:` records. | Correct Python fixture strings to contain real newlines at execution; retain strict primary key fingerprint check and GPG decrypt verification. |
| R152 `test_legitimate_primary_key_with_subkey_is_accepted` | Same malformed fixture: no actual `pub:` and `sub:` lines reached the parser. | Correct newline-separated primary/subkey fixture; retain single pinned primary signer and valid subkey support. |
| R157 `test_public_file_rotates_atomically_when_peer_ttl_changes` | Directory writer appended literal backslash-n characters **after** JSON, creating `JSONDecodeError: Extra data`. | Output a real newline byte (`\n`) after the JSON document; retain atomic replacement and symlink protection. |
| R142 `test_conflicting_same_node_hint_not_silently_trusted` | The first-to-second-peer fix reduced the minimum valid peer count from two to one. When one identity equivocated across directories, the other identity still satisfied the new threshold. | Track ANY conflicting published node ID and reject the entire discovery result, even when another usable identity remains. Retain one genuine nonconflicting peer as sufficient to bootstrap node two; retain two distinct HTTPS feeds for this implementation's resilience gate. |

These patches are in the existing public GitHub development PR. They
alter no running Besu/Lighthouse/ZeroTier services, no wallet or
validator identity, no on-chain deployment and no genesis.

## Validation and safety

The exact R161 code has **not yet been VM4707 verified** until the
operator runs the pinned test command and supplies its terminal result.
No new VM joins the network by passing these source regressions.

The next runtime milestone is still public immutable original
genesis bytes and honest independent native discovery sources,
then real VM4709 EL/CL native peering and finality. Deep paper-ready
refactoring remains deferred until the real experiments finish.
