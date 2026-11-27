# Integrated owner authentication — release design

Owner administration must not require a browser wallet extension or external identity provider.
Public marketplace remains unauthenticated. Existing EIP712 protocol evidence and optional external wallet control remain supported.
Default integrated owner credential is enrolled locally during installation. Password verification must use a salted memory-hard KDF. Prefer WebAuthn passkeys on a stable HTTPS origin once available; rotating Quick Tunnel hostnames do not preserve relying-party identity. Never promise passkey continuity across unrelated origins.

Security boundary:
- Integrated login grants node administration, not unlimited transaction signing.
- Public HTTPS terminates at a third-party tunnel in the current deployment. Never transmit application keystore passwords, mnemonic, raw keys or validator keys through this tunnel.
- Initial release may support authenticated bounded provider interruption without financial signing. Remote financial operations require a separate explicit local signer policy with bounded amount, action scope, expiration, journal, revocation and recovery. Do not silently unlock wallet at installation or reboot.
- Sessions must be random, short-lived, revocable, hashed in memory, secure HttpOnly SameSite cookies; exact configured HTTPS origin and per-session CSRF token for mutation. Do not trust arbitrary forwarded host/proto headers.
- Enrollment and recovery are owner-local only; never provide public registration/reset endpoints. Rate limit login, bound concurrent sessions and request sizes, avoid credential logging, audit actual control outcomes.
- Node controls are an explicit allowlist, not a generic shell or process endpoint. Reuse R400/R401 bounded recovery mechanism, preserve native validator and wallet state.
- Existing public listener remains unchanged until regression and live security checks succeed.
- Unified installer must include enrollment, secure state permissions, role discovery, service readiness, revocation and recovery documentation. No browser extension requirement.
