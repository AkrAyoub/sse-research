# R169 — R168 owner-publication success, immediate anonymous readback refusal

## Actually observed VM4707 execution

On pinned R168 SHA `86adcddeaca7839fbd45570c232b6049f8e4cb8a`:

- Full Python suite: `Ran 1125 tests in 17.515s; OK (skipped=3)`.
- `--publish-live --node-id node-vm4707-observer` **succeeded**
  with public comment ID `7097016936`, `refreshedExistingComment=false`,
  source `https://github.com/AkrAyoub/sse-research/issues/42`,
  and ephemeral `expiresAt=1795427607`.
- **Immediately** running `--discover` returned:
  `R168_EXPERIMENTAL_GITHUB_RENDEZVOUS_REFUSED:
  no fresh real native identities published in public issue`.
  Therefore do NOT claim an external node has received a peer,
  joined native P2P, or synchronized an actual checkpoint.

## Independently inspected PUBLIC GitHub API

The source repository GitHub connector subsequently retrieved
`https://api.github.com/repos/AkrAyoub/sse-research/issues/42/comments?per_page=100`
and confirmed that the public comments collection now contains:

- exactly one R168 native announcement, comment `7097016936`,
  authored by `AkrAyoub`, created `2026-11-23T09:43:29Z`;
- correct R156 exact marker and parseable, strict source JSON;
- actual `node-vm4707-observer` Besu public enode, Lighthouse ENR,
  overlay IPv6 (not copied into repository or installer code);
- original chain31340 EL genesis hash
  `0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf`;
- original Beacon genesis validators root
  `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd`;
- short-lived original expiration `1795427607`
  (`2026-11-23T09:53:27Z`), with exactly the expected false
  signer-read, remote-handshake and pre-publication flags.

This proves anonymous **API availability after the initial command
had failed**. A transient public API cache / visibility delay is a
plausible explanation but is not conclusively distinguished from
VM-side retrieval or parser faults.

## R169 diagnostic source change

The public REST getter now includes explicit
`Cache-Control: no-cache` and `Pragma: no-cache` request
headers. They may improve public edge freshness but do not
guarantee immediate GitHub write visibility.

`tools/sse_pos_r168_github_rendezvous.py --diagnose-public`
performs ONE anonymous public GET and reports:

- how many comments were actually retrieved from public GitHub;
- how many had the exact R156 native peer marker;
- how many strict original-chain R156 records were fresh/valid;
- how many marked records were expired/invalid;
- `publicReadbackProven` only if a genuine fresh record is observed;
- all native handshake, independent discovery and new-node join
  flags remain **false**.

It never prints public native enodes/ENRs or signer data. The ordinary
`--discover` command must still return actual current hints or
refuse; no fallback hardcoded VM IP, new genesis, empty imaginary
directory or permanent stale ENR is acceptable.

Regressions were added for empty cached lists, fresh valid records,
stale/malformed records, and no invented handshake success.

## Expiration/future work

The owner has only **one actual** GitHub comment publication so far.
GitHub issue hints expire in 600 seconds. New original native
identity must be recollected and the SAME own comment updated
before expiry if another host is to use it. The R168 publisher
supports PATCHing the same comment but is not yet integrated into
a verified automatic recurring operator service. A successful
readback is still only **discovery**, not permissionless independent
native P2P nor active finality.

GitHub remains a single centralized temporary discovery service;
the final design requires independently operated discovery
paths and real native protocol proof from outside the VM provider.

## Next reviewable owner command

After checking out the new pinned R169 SHA and running full tests,
run these read-only commands (no additional GitHub comment mutation):

```bash
python3 -B tools/sse_pos_r168_github_rendezvous.py --diagnose-public
python3 -B tools/sse_pos_r168_github_rendezvous.py --discover
```

If the original comment expired, R168 `--publish-live` may refresh
it with **actual current** public native EL/CL identity, only after
its source tests pass. The exact root/hash/TTL and flags are
necessary; a GitHub issue comment ID is not a static network peer
address.
