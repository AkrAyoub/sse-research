# R92: Chain31340 post-reboot network recovery (VM4706 + VM4707)

## Why
The 2026-11-21 host reboots occurred before the ZeroTier 6plane IPv6 addresses
were assigned, so Docker Engine 29.1.3 failed explicit IPv6 port binds.
VM4707 subsequently had running containers with empty NetworkSettings.Networks
and Ports; VM4706 remained attached to an `internal=true` Docker bridge
without effective published ports. Merely stopping/starting containers did not
recover either problem.

## Architectural invariants
* Reuse the original chain31340 genesis, EL/BN data, images, containers and
  private Engine JWT. No Docker resources are created or removed.
* Original owner `sse31340-g2-internal` remains `Internal=true`; no gateway
  or permissive second Docker bridge is added. No port 8551 is forwarded.
* Exact loopback APIs 127.0.0.1:18545->172.18.0.2:8545 and
  127.0.0.1:15052->172.18.0.3:5052.
* Exact ZeroTier EL TCP/UDP 30404 and Lighthouse TCP 9000, UDP 9000/9001
  forwarded onto the existing original internal Docker bridge. Source peer
  address is hidden from containers by the relay; peer protocol remains native.
* Validator client, signing keys, R65 preserved containers are never started
  or touched by these scripts. The validator requires separate operator action.
* Neither approach establishes open public IP reachability independent of
  overlay participation.

## Initial recovery (VM4706 only)
1. Check the internal bridge APIs: GET http://172.18.0.3:5052/eth/v1/node/syncing
   and read-only chainId JSON-RPC at 172.18.0.2:8545 with a permitted Host
   header (e.g. `Host: 127.0.0.1`). Abort if internal access fails.
2. After reviewing PR and pinning checkout commit, run
   `bash scripts/r92_vm4706_install_owner_host_relay.sh --plan`.
   Then `sudo -v` followed by `python3 -B tools/sse_pos_r92_owner_internal_bridge_host_relay.py --check`.
   This checks exact host IP and all seven ports are available.
3. With explicit operator authorization, run
   `bash scripts/r92_vm4706_install_owner_host_relay.sh --apply`.
4. Check the unit and actual APIs/peers using curl locally, and compare
   independent finalized checkpoints with VM4707 before recovering validator.

The relay is a bounded, fixed-endpoint research-host workaround. It is not a
general-purpose public gateway, edge security appliance, NAT traversal service
or replacement for Docker's normal port publishing. Host firewalls and
underlying overlay routing remain important.

## Post-boot recovery on enrolled VMs
Run `bash scripts/r92_install_existing_node_recovery.sh --plan` first, then
`--apply` only on the VM named in the role guard. `--apply` installs and
enables an idempotent systemd guard for the *next boot*, without starting the
unit or changing running containers immediately. The guard checks the actual
ZeroTier IPv6, exact Docker internal/bridge mode, original configured host
port bindings, endpoint internal IPv4, original execution DNS alias, and
refuses unexpected extra networks. It never starts or touches validator clients.
If the overlay isn't assigned yet, systemd retries the guard after 15s.
An observer missing its Docker network is re-attached to the exact existing
bridge, preserving the fixed internal IP, and started or restarted. All exact
effective published ports must then be present.
The owner guard only starts/restores its existing EL and BN attachments and
does not treat internal-bridge missing Docker host ports as a failure: the
independent host relay supplies the controlled public/loopback bindings.

## Validation / failure behavior
* Do not run against unfamiliar VM, Docker network, extra attached networks,
  alternate genesis, or different internal IPs.
* Use `systemctl status sse31340-owner-port-relay.service`, `ss -lntup`,
  local read-only RPC, beacon /syncing, peer IDs, and finalized checkpoints.
* If a guarded step fails, inspect its state and logs. Never automatically
  retry a manual partial migration, create another validator, or rewrite
  Docker network internal flag.
* Existing owner container restart policy and restored container endpoint
  behavior should be verified in a real reboot exercise before claiming
  unattended service availability. Installing the guard is not proof of that.
* For a newly enrolled external VM, add its explicit role/network/identity
  configuration and tests; never reuse VM4706's or VM4707's addresses.

## Known limitation
The fixed UDP relay maintains per-source temporary upstream sockets (max 1024,
5 min idle). It forwards native Ethereum packets, but the transport can affect
source-address visibility and requires end-to-end real P2P/QUIC testing. Avoid
making a production uptime, permissionless onboarding or performance claim
without measuring it.
