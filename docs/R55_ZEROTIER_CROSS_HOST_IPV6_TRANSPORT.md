# R55 — Real public controllerless ZeroTier IPv6 TCP+UDP roundtrip validation

**Current status:** GitHub source only. No VM4706 original chain/validator/EL/CL changes, no new signer or genesis. VM4707 actual ZeroTier 1.16.2 status was TUNNELED, network ff2328775f000000 status OK PUBLIC, network ztrb6cq527 IPv6 fca0:2328:77b8:6578:a55::1/40, PLANET peers via RELAY. It joined WITHOUT per-node authorization. This is an actual overlay membership, not an actual native EL/CL P2P/consensus connection.

According to official ZeroTier https://docs.zerotier.com/cli/ , TUNNELED means UDP/9993 to global roots not working and a fallback TCP relay is active. This is worse for tail latency and performance; no guarantee it's fit for actual finality duty or monitoring SLAs. Overlay availability also depends on provider's relay infrastructure.

According to official https://docs.zerotier.com/protocol/ , a controllerless ad-hoc network ffSSSSEEEE000000 restricts BOTH UDP packet destination ports (including responses) and TCP SYN destination ports to S..E. R54 selected 9000..30303 for real Lighthouse+Besu P2P, excluding TCP22/Engine API8551. **Critical:** UDP client must bind a source port WITHIN 9000..30303 so reply destination port is also permitted; ordinary ephemeral UDP source ports might be >30303 and fail even if connectivity works! We explicitly bind UDP client to 29002. Client TCP establishes to 29000, UDP to 29001. All three are within allowed destination range, and server binds ONLY its assigned 6plane IPv6 address, not global ::.

## GitHub source and safety

- tools/sse_pos_r55_zerotier_ipv6_transport.py pure Python stdlib, tests/test_sse_pos_r55_zerotier_ipv6_transport.py with 12 tests.
- --plan: read-only joins status; requires actual membership OK PUBLIC and a fca0::/16 6plane address, reports no remote packet evidence.
- --server: accepts harmless exact TCP/UDP echo probes, ONLY VM4707's own assigned 6plane IPv6, TCP29000, UDP29001, max10m; no root privilege needed except read-only sudo ZeroTier status.
- --check REMOTE_6PLANE_IPV6: on an independent second network participant, after it joined SAME controllerless ad-hoc ID, require BOTH actual IPv6 TCP+UDP packet roundtrips to that remote VM4707; client binds source UDP29002. Cross-host proof is real sockets, not simulated or synthetic; network operator independence cannot be inferred from tool.
- Never copies validator keys, restarts Docker, exposes RPC/Engine, touches genesis, edits OS network configuration, calls join/leave, or alters original signer.
- Source committed to original PRIVATE GitHub only; to run on VM4707, use a read-only authenticated Git checkout or transfer this ONE public unprivileged script over the verified existing VM4706->VM4707 LAN via SSH/SCP (after SSH host fingerprint verification), NO GitHub SSH private key copied. On a separate Linux laptop/non-provider host, install ZeroTier from official package and join EXACT ID, copy only this script; automation of installer will replace these manual testing actions after transport works. Do NOT use original VM4706 as sole external Internet proof: same infrastructure is not independent.

## VM4707 one-time trial

1. Run Python R54 --plan after copying source; VM4707's actual joined network is OK PUBLIC, IPv6 fca0:2328:77b8:6578:a55::1.
2. Run Python R55 --plan; expected status from real VM exactly as above.
3. Start Python R55 --server and keep terminal open at most 10m.
4. From a genuinely separate machine outside provider infrastructure, join ff2328775f000000 (anyone can join without network authorization) and run SAME R55 script --check fca0:2328:77b8:6578:a55::1 . Check both TCP and UDP fields; RTT measured via actual sockets. The tool rejects self-test and public IPv4, so it cannot be passed via loopback or on the same machine. An operator using only VM4706 could measure real two-VM transport but could NOT claim independent public Internet join.
5. Do not treat this as Ethereum peer proof. Next integrate the original public R47 genesis bundle + pinned Besu26.11.1 and Lighthouse8.3.3 with IPv6 ENRs and node discovery and verify true native EL/CL handshakes. VM4706 original EL currently P2P disabled/internal Docker network, so careful single-validator maintenance/migration is required to connect actual two nodes; preserve DB/validator slashing.

No persistent external network operational SLA or permissionless network claimed at this stage.
