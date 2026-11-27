# R287 — Real four-VM network evidence and authenticated temporary SSH compute probe

## Actual owner-VM results as of 2026-11-24

All four VM4711–VM4714 hosts ran the R286 focused suite, 9/9 tests each, 36/36 collectively. All four hosts really connected to VM4714 private address 10.50.56.22 TCP port 22. Owner-observed durations were 2ms on VM4711, 1ms on VM4712, 1ms on VM4713, and 0ms locally on VM4714. All four probes to raw worker port8877 on the provider private interface returned TCP_REFUSED. This is the desired isolation because the unsigned Docker worker binds to 127.0.0.1:8877.

VM4714 also rechecked exact live Docker container ID 59b9086543110acd2ef44da7fddeb100ab0341204de3dac595093803985f535b and image sha256:848cde736008713d2f72e8de20cc669326abc678e41f644d3d63480ce77bd20d. Its second independent 8192-round SHA256 challenge matched the actual response digest sha256:676dbe62ec36cd3f42a14ee6b65e3753be3a5ae71df244161b1a886732728abe, one local HTTP elapsed 0.015428 seconds (15.428ms). First owner trial duration was 2.379ms. These are two independent real observations, not sustained latency statistics, trusted hardware proof, a signed provider response or a paid onchain SLA. Real evidence file: evidence/r287_real_four_vm_private_tcp_and_second_docker_cpu_probe.json.

## R287 source — STRICT out-of-band SSH host key pinning

New source tools/sse_pos_r287_three_vm_authenticated_temporary_compute_ssh_probe.py uses only the exact four previously observed OS VM owners. It deliberately avoids opening remote plaintext worker port8877 or creating persistent tunnels.

1. VM4714 --provider-hostkey reads ONLY its PUBLIC standard /etc/ssh/ssh_host_ed25519_key.pub, computes and prints the server ED25519 SHA256 fingerprint. It never reads the host SSH private key, the EOA keystore or a validator key. The owner must copy this public fingerprint FROM THE ACTUAL VM4714 CONSOLE to each monitor's terminal out of band; do not trust a fingerprint learned solely from an unauthenticated monitor-side ssh-keyscan.

2. VM4711, VM4712 or VM4713 --preflight --expected-host-fingerprint SHA256:... performs an explicitly bounded SSH public key scan of 10.50.56.22 port22, compares ED25519 public key SHA256 against that owner-console PIN, and fails closed on mismatch, unknown key or failed scan. It uses a temporary owner-private mode0600 known_hosts file, never silently adds an unknown host permanently and does not disable strict checking. It then runs a noninteractive, hostkey-verified SSH publickey-authenticated remote true. The SSH command ignores user config and proxy settings, refuses passwords, keyboard interactive, agent forwarding, X11 forwarding, and insecure trust-on-first-use. An optional existing owner-private 0400/0600 identity-file can be explicitly supplied for SSH child use, without Python reading the key. If real direct user public-key login is unavailable, the result says so and no worker tunnel is opened. TCP22 handshake observed in R286 was not evidence of account authentication.

3. On an individual monitor with successful --preflight, --probe rechecks the same fingerprint and SSH login, starts exactly one temporary local SSH port-forward 127.0.0.1:EPHEMERAL -> VM4714 localhost127.0.0.1:8877. It then requests actual worker healthz and one fresh OS-random 8192-round SHA256 compute result across this encrypted transport. The monitor independently reproduces the resultDigest, observes real SSH-roundtrip seconds and reports it as UNSIGNED pre-lease evidence only. In a finally block the spawned SSH process is terminated and ephemeral known_hosts is deleted. No permanent tunnel, Docker or native RPC writes, new EOA/SSH keys, authorized_keys, firewall or wallet changes.

New 14 mocked tests were authored at tests/test_sse_pos_r287_three_vm_authenticated_temporary_compute_ssh_probe.py. Neither the tests nor the actual provider public fingerprint, monitor SSH account authentication or real cross-VM compute over SSH have been executed by the owner yet. Github source is not a deployed network connection.

## Next operator order

First on VM4714 update to the exact pinned HEAD supplied in chat, run the new 14 focused tests and run the tool --provider-hostkey. This is a public-key read only.

Then on each monitor VM4711–VM4713 update the same SHA, run the 14 tests, and run --preflight with the same actual provider-consoled SHA256 public fingerprint. No password or private signing key should be pasted into GitHub or chat. If the result says SSH noninteractive publickey login not verified, no tunnel may be started. The next step is separately owner-authorized dedicated SSH key provisioning and public authorized_keys entry only, not disabling strict host keys or opening the worker.

Only on clients where real preflight authentication succeeds should the owner invoke --probe with identical host fingerprint. The result is REAL remote CPU over ephemeral authenticated SSH but still not EIP712 signed monitor SLA evidence.

## Chain, funding and public Internet constraints

Original chain31340 consumer nonce1, Monitor1 nonce2 and Monitor2 nonce3 native funding transactions are all proven FINALIZED. New four VM4711–4714 encrypted EOAs are still UNFUNDED. Read-only R282 verified clean nonce4..7 0.005 TEST ETH per account, combined maximum debit 0.020000000084 TEST ETH including gas, but NO owner authorization or tx has been received for these new grants. Native EL/CL validator, original Docker PoS nodes and private keys remain untouched.

A private SSH tunnel does not prove arbitrary participant admission from the public Internet, a public TLS endpoint, independent physical fault domains, bonded monitors or paid finalized V2 lease. The real V2 R232 monitor still requires elected and confirmed onchain monitor identity, final paid lease, committed HTTPS origin and signed EIP712 provider response before SLA success or votes. Do not make that claim from pre-lease CPU probes.
