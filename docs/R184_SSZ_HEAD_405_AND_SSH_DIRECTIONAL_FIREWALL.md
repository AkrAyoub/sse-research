# R184 — Lighthouse SSZ HEAD 405 and VM4709→VM4707 SSH timeout

Date: 2026-11-23. Source: actual operator read-only commands.

## Actual results

VM4707 has the existing SSH daemon active, with TCP listeners
`0.0.0.0:22` and `[::]:22` as observed by `ss -lnt`.
The owner Beacon API on `127.0.0.1:25052` answered **HTTP
405 Method Not Allowed** to `HEAD` (`curl -I`) at:
- `/eth/v2/debug/beacon/states/finalized`
- `/eth/v2/beacon/blocks/finalized`

This does **not** contradict the prior observed actual `GET`
responses to both same endpoints: HTTP 200, Content-Type
`application/octet-stream`, 32 bytes successfully read. The
405 indicates HEAD not supported. Do not change the Beacon
client, disable security or claim the checkpoint is unavailable
on the basis of HEAD.

VM4709 actual ZeroTier-to-VM4707 overlay IPv6
`fca0:2328:77b8:6578:a55::1` TCP port22 timed out
(`TimeoutError`) while native client TCP30404 and TCP9000
were separately observed reachable. This proves SSH is not
reachable IN THAT DIRECTION, but not why: check host firewall,
cloud security policies, or reverse direction; don't assert a
specific cause without measurements. Never recommend disabling
firewalls or exposing SSH/Beacon APIs publicly to fix an
unrelated port timeout.

## Next bounded no-mutation probe

On VM4709, read-only `ss -lnt '( sport = :22 )'`, check
`systemctl is-active ssh` and current ZeroTier address. It
does not install or start SSH.

On VM4707, attempt a TCP socket connection to VM4709's
**previously actually observed dynamic ZeroTier IPv6**
`fca0:2328:77e5:740c:ce60::1` TCP port22 with timeout
5s, record only reachable or timeout, no authentication.
If reachable, assess mutually authenticated SSH keys
and host-key trust before transporting any finalized SSZ.
DO NOT output private credentials or create an SSH user
automatically. Prefer no changes to VM4707 inbound firewall.

For actual owner state+block SSZ size, use HTTP GET and
read only Content-Length response header, then close
without transferring the full body (a body may be streamed
until closed; not a HEAD request). The two endpoint aliases
`finalized` can advance between requests, so pin the
same finalized block root from a trusted checkpoint
before exporting a pair. Verify both using pinned
Lighthouse or a known-good SSZ root before acceptance.

If both SSH directions fail, use a secure authenticated
transfer approach suitable for existing overlay conditions.
Do not resort to unverified unsigned GitHub comments,
expose privileged REST endpoints, start publicly accessible
state snapshots, or bypass the CL weak-subjectivity check.

VM4709 actual two clients remain in restart loops.
No native EL/CL handshake/finality demonstrated yet.
Original genesis, JWT, populated Beacon DB and local P2P
identity must be preserved. R147/R151/R137 create-once
installers must not be repeated on existing VM4709.
