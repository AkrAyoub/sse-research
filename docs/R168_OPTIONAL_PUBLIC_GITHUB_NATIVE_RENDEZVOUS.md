# R168 — Experimental REAL public rendezvous with expiring GitHub issue announcements

## Owner-observed baseline on VM4707

On November 23, 2026, at Git SHA
`9e008add7025800dad1fc34797877171bfe390d1`,
the real VM4707 owner observed:

```text
Ran 1111 tests in 17.456s
OK (skipped=3)
```

The live R156 Besu + Lighthouse public identity capture succeeded
for `node-vm4707-observer` and R157 produced a **valid single-peer
native discovery feed**:

```text
R167_REAL_NATIVE_PEER_DIRECTORY_VALID=true
R167_DIRECTORY_PUBLICLY_HOSTED=false
R167_EXTERNAL_NATIVE_P2P_VERIFIED=false
```

The original chain31340 genesis is already published via exact public
GitHub Release `chain31340-genesis-v1` with original SHA256
`1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
No new genesis, signing validator, or original node state changes are
necessary for this stage.

## Real implementation: public GitHub Issue #42 as OPTIONAL rendezvous

The GitHub issue exists:
`https://github.com/AkrAyoub/sse-research/issues/42`.

Anonymously readable GitHub public REST endpoint:
`https://api.github.com/repos/AkrAyoub/sse-research/issues/42/comments?per_page=100`.
It was inspected and returned `[]` before initial peer publication.
No real peer record was fabricated or prefilled.

`tools/sse_pos_r168_github_rendezvous.py`:

- `--publish-live --node-id node-vm4707-observer` captures actual Besu
  `net_enode`, Lighthouse ENR and observed ZeroTier 6plane IPv6 from
  REAL VM4707 local APIs using R156, checks exact original EL/CL genesis
  and ENR ports, then uses the operator's **existing separately
  authenticated** GitHub CLI session to post only the public R156
  record to Issue #42. It never reads any BLS/validator/P2P private
  keys, creates a wallet, or starts/stops containers.
- A subsequent call by the SAME publisher checks the public issue
  comments and uses GitHub's API to **PATCH its own existing comment**
  instead of flooding the issue with 720 comments per day.
  Repository write credentials are never placed in a shell command,
  log, issue comment, code file or artifact. The already authenticated
  GitHub CLI retains its own private credential store under the
  operating-system user account (VM4707 previously reported plaintext
  local storage, a real security tradeoff).
- `--discover` reads the PUBLIC issue REST API without GitHub login
  or authorization. It accepts only comments with the exact marker
  `SSE_CHAIN31340_R156_NATIVE_PEER_V1`, strict original chain31340
  R156 schema, fresh 600-second expiry, valid native IPv6 enode and
  Lighthouse ENR shape. Others are ignored; conflicting public node
  keys cause hard refusal. The resulting dynamic EL enode + Beacon
  ENR are actual hints from running nodes, **not hardcoded VM IPs**.
- This allows a future SECOND/THIRD VM to verify that it can
  anonymously discover a real dynamic native peer identity. No new
  participant is required to have a GitHub account to **join**.
  A participant wanting to **publish on this optional GitHub
  rendezvous** currently needs an account allowed to comment; this
  is a discovery publication limitation, not consensus membership.
- All results explicitly set
  `temporaryCentralizedRendezvous=true`,
  `independentDiscoveryInfrastructureVerified=false`,
  `actualNativePeersAuthenticated=false`,
  and `peerReachabilityVerified=false`.
  Only successful Besu/Lighthouse native P2P sync, identical original
  genesis, same finalized checkpoint and proof of external operator
  connectivity can change these truths.

**Do not conflate this with the FINAL network design.** GitHub is a
single corporate provider, may censor or throttle comments, has API
rate limits, and is unavailable without Internet reachability.
It is not a decentralized rendezvous, not a trustless DHT, and not
a service availability SLA. A directory source list containing two
GitHub endpoints is NOT two independently controlled discovery sources.
GitHub's issue comments API has a bounded page of 100 comments in
this current research reader; it is not a production-scale global
registry, and identity conflicts or untrusted spam can deny discovery.
An independent public HTTPS registrar/DHT/native discovery fallback
with independently operated mirrors and robust signature/rate
controls remains required for the final **permissionless** deliverable.

## After R168 code passes the real VM4707 test gate

The real first publication and anonymous readback on VM4707
are straightforward and require no additional GitHub login, because
the operator already completed the `gh auth login` step:

```bash
# Run ONLY on VM4707 after checking out/test-passing reviewed R168 SHA.
python3 -B tools/sse_pos_r168_github_rendezvous.py \
  --publish-live --node-id node-vm4707-observer

# Explicit, read-only public API retrieval, no GitHub login required.
python3 -B tools/sse_pos_r168_github_rendezvous.py --discover
```

No infrastructure has been publicly exposed by these source commits.
The marker/actual full ENR/enode contents are published ONLY when the
operator runs the explicit authenticated command. The live readback
must succeed before this temporary source can be used to bootstrap
another VM. R168 does NOT yet configure the R147 installer for
automatic Github-source discovery or schedule periodic 2-minute
refresh; both require their own verified integration and tests.
Without refresh the record expires in 10 minutes, intentionally.

## Follow-on after real publication

1. Have a separate VM perform anonymous R168 discovery and verify it
   sees the ACTUAL original-chain native EL/CL identity, without any
   fixed VM IP, manual enode, GitHub login, copied BLS key or
   read-only repo SSH key.
2. Add a safe periodic self-publication timer on each consenting
   existing node (within TTL), and integrate this replaceable
   PROVISIONAL source into the one-role-selector installer without
   claiming independent infrastructure.
3. Replace GitHub dependence with independent current-record
   publisher operators, ideally native Ethereum-compatible discovery
   with alternative public transport paths. Demonstrate real
   new-host EL+CL peer handshake and finalized checkpoint
   agreement from a different provider/ISP.
4. After genuine validator stakes/deposits, funded TEST ETH,
   real SSE provider/consumer/monitor resource workloads,
   measured SLAs and monitoring/committee decisions are implemented
   and tested, conduct the separately requested exhaustive
   paper-ready source refactoring. Never refactor away live
   experiment evidence beforehand.

**Code is research-phase R168 and has NOT yet passed the real owner VM
suite at the new SHA. Last verified green remains R167 (1111 OK,
3 skipped).**
