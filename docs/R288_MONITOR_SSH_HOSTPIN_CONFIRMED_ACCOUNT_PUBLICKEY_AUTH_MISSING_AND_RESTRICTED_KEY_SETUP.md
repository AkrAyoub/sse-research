# R288 — VM4711–13 host fingerprint verified, SSH publickey login unavailable; bounded operator-only monitor SSH credentials

## Actual R287 user evidence

On November 24, 2026, the owner ran R287 14 unit tests on each of VM4711, VM4712, VM4713, VM4714: **56/56 passed**. Trusted provider-console VM4714 public ED25519 SSH host fingerprint:

    SHA256:jWl81QyIY7+m7Y51lzA2g0wM6F0lIuvdE3bv2SeAFoY

An initial non-fingerprint value 29111805200603600369 was correctly rejected by R287. Subsequent three-monitor R287 --preflight with the true provider-console host fingerprint verified each server host key BUT all three returned **sshNoninteractivePublicKeyLoginVerified=false**. This proves the host keys matched; it does NOT prove whether the login rejection was caused by absent user SSH key, missing server authorized_keys, forced server policy, source IP, or other permission. NO tunnel or real remote CPU challenge was launched. The VM4714 Docker CPU worker itself previously completed two local independent 8192-round challenges and remains localhost-bound pending a fresh recheck.

Evidence: evidence/r288_real_vm4711_13_hostkey_pinned_ssh_pubkey_auth_missing.json

## New R288 GitHub source-only credentials workflow

Source tools/sse_pos_r288_monitor_to_vm4714_ssh_publickey_bootstrap.py and 18 mocked tests tests/test_sse_pos_r288_monitor_to_vm4714_ssh_publickey_bootstrap.py authored, **not yet run on actual owner VMs**.

The tool permits five explicit modes, with exact OS nonroot usernames VM4711–14 only:

- --client-preview: public local metadata only, no changes.
- --client-create: on each VM4711, VM4712, VM4713, only with explicit unique TTY authorization generate ONE new ED25519 SSH private/public pair in the owner-private ~/.local/share/sse-v2-app-only/ssh directory. It is intentionally *passphrase-free* for unattended BatchMode temporary tunnel experiments; that is an experimental security tradeoff, not a production long-lived unattended credential. Private key remains owner-controlled mode0600 on its own monitor VM. Never show/copy/upload/paste private SSH, EOA, validator or wallet key. It does not read or replace any Ethereum EOA app identity.
- --client-public: read the local PUBLIC SSH .pub file and print its exact public key string and fingerprint. Safe to copy PUBLIC output into chat for the owner-reviewed follow-up.
- --provider-preview: VM4714 reads only owner .ssh directory and authorized_keys metadata, without printing or changing any existing authorized key.
- --provider-authorize --source-vm vm4711|vm4712|vm4713 --public-key 'ssh-ed25519 AAA...': VM4714 owner individually types one exact TTY authorization per PUBLIC monitor key, which is appended with fsync and a file lock to ~/.ssh/authorized_keys. Existing contents are preserved verbatim; reject symlinks, conflicting entries, permissive file modes, missing newline and wrong owner.

Each authorized key has the following bounded options (with monitor-specific private source IP and distinct public key):

    from="<VM private IP>",restrict,port-forwarding,permitopen="127.0.0.1:8877",command="/usr/bin/true" ssh-ed25519 <public key> sse-r288-<vm>

Source IPs exactly VM4711 10.50.56.14, VM4712 10.50.56.19, VM4713 10.50.56.21. OpenSSH restrict denies agent/X11/PTY/remote-user-rc and default forwarding, port-forwarding explicitly enables only the destination permitopen="127.0.0.1:8877", command=/usr/bin/true prevents arbitrary remote shell via these new keys. AuthorizedKeysFile and AllowTcpForwarding effective sshd configuration could still make login unavailable; do not loosen those settings automatically.

Official sshd authorized_keys reference: https://man7.org/linux/man-pages/man8/sshd.8.html .

Existing portal SSH account access and any existing authorized_keys content are preserved, not replaced. This procedure does not sudo, restart sshd, modify firewall, alter Docker/image/worker or touch the original native chain31340 clients. No funds or onchain EOA calls are made.

## Exact next owner action

1. Each monitor VM4711–4713 separately fetches newest pinned reviewed Git HEAD, executes 18 R288 focused tests, runs --client-preview and --client-create only if approved by the individual terminal owner. Capture its own PUBLIC ssh-ed25519 key line from the printed JSON. Do not reuse or share one private key among monitors.
2. VM4714 can run --provider-preview read-only; after comparing the three distinct monitor PUBLIC keys, separately run --provider-authorize for each key with exact owner TTY approval. This can be done from public key strings supplied via the owner's follow-up log.
3. R287 recheck per monitor with provider-console ED25519 SHA256 fingerprint and explicit --identity-file pointing to that monitor's owner-only generated SSH private path. The SSH subprocess reads the private file; Python does not read or print its bytes. R287 preflight first. Only if true, start R287 --probe for ONE disposable 127.0.0.1 ephemeral local forward to VM4714 127.0.0.1:8877; actual independent remote CPU digest and encrypted end-to-end timing then followed by automatic tunnel teardown.
4. Failed authentication after key setup means inspect effective sshd policy and source IP with READ-ONLY audit, rather than disabling host pinning, sudoing to copy secrets, adding owners to Docker group or exposing plaintext port8877.

## Honest research status

All three previously authorized native VM4707 consumer/monitor funding transfers are finalized. Four NEW separate VM4711–14 encrypted Ethereum EOAs are created but remain UNFUNDED. The owner-proven four-recipient R282 read-only plan is 0.005 TEST ETH each with max combined 0.020000000084 TEST ETH including gas, but owner has NOT separately approved transfers nonces4–7. R288 does not add spending authority. Public permissionless EL/CL outside-ISP ingress, public TLS signed provider endpoint, independently bonded elected monitors and real paid finalized onchain V2 lease/evidence/settlement remain to be implemented and tested.
