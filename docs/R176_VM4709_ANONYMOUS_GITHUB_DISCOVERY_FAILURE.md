# R176 — Actual VM4709 public discovery unavailable after R175 signed ZeroTier APT preflight

## Real evidence

- On VM4709, R175 narrowly targeted source tests passed: 18 R152,
  3 R173, 15 R151, and 18 R168 (54 total).
- The official ZeroTier Noble HTTPS `InRelease` metadata was
  actually retrievable and starts with expected clearsigned
  message. **This proves transport and expected format, not APT
  package signature verification**, which APT must still perform.
- The pre-existing observer selection for the original R170
  source, exact R59 original genesis SHA256, and absence of SSE
  Docker clients were verified by a read-only R173 gate.
- The immediately following **anonymous public GitHub peer lookup**
  returned `R168_EXPERIMENTAL_GITHUB_RENDEZVOUS_REFUSED:
  anonymous public rendezvous unavailable`, BEFORE R151 runtime
  or ZeroTier signed APT installation. Do not call this an APT failure
  or claim live chain syncing.
- VM4707 had actually refreshed the genuine R156 public identity
  comment, but a successful publication does not imply that GitHub's
  anonymous API permits unlimited third-host reads.

## R176 code

GitHub documents a primary unauthenticated REST API rate limit of
60 requests per hour per source IP, and exhausted primary rate
limits respond with HTTP 403 or 429 and header
`X-RateLimit-Remaining: 0`:
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

R168 currently performs a GET of the public issue comment collection
and a second GET of the dynamically discovered actual comment ID
to avoid observed stale list responses. Requests carry fresh cache
nonce. The new implementation classifies the **actual** anonymous
GitHub read failure without exposing response body or credentials:

- `GITHUB_ANONYMOUS_API_RATE_LIMIT_EXHAUSTED` for 403/429 with
  rate remaining exactly zero.
- `GITHUB_ANONYMOUS_API_THROTTLED_OR_FORBIDDEN` for other 403/429.
- `GITHUB_PUBLIC_API_HTTP_N` for another exact response status.
- `GITHUB_PUBLIC_API_DNS_TLS_OR_EGRESS_FAILED` for transport errors.

The tests inject synthetic HTTP failures solely to check failure
handling; they do NOT simulate blockchain peers, proof of a specific
VM4709 HTTP response, or native P2P. Existing expiry, genesis and
native identity validation stays unchanged.

## Next real read-only check

On VM4709, use the public `GET /rate_limit` endpoint (GitHub says
this endpoint does not count against the primary REST API rate
limit, though it may count toward secondary throttling). Inspect
only `resources.core.remaining`, `resources.core.limit` and
the reset timestamp. It does not need a GitHub account or token.

If quota is exhausted, do not bypass limits or repeatedly hammer
the API. Stop and establish a genuinely independent discovery
service; this temporary GitHub issue is a single availability
dependency, not a real permissionless native discovery protocol.
If quota is available, run the pinned R176 diagnostic `--discover`
once and report its now-specific error. Do not retry the privileged
R151 installer until public discovery succeeds.

Current real proof: VM4709 has NO SSE EL/CL clients, handshakes or
finalized checkpoint. Existing observer selection, genesis and
source checkout MUST be preserved. Final project requires independent
dynamic peer routing and real native consensus verification.
