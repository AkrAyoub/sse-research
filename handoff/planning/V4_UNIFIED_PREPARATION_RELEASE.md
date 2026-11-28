# Unified participant installation — preparation release

Run scripts/sse_install_participant.sh --install from clean pinned checkout.
Normal prompts: role selection, wallet selection/creation and secure passphrase.
Existing role policy and wallet are preserved. No gas prompts. No on-chain
writes, no unattended signing or exposure of a private console. Optional
RPC relay has bounded concurrency (16 workers) and exact existing TLS trust;
one known upstream remains a dependency. Bounded retries are reads only.

Fleet script scripts/sse_upgrade_lab_fleet.sh dispatches VM4709 relay,
VM4706/4708/4721 read-only inventory, and existing application roles. No
native reset, key import or re-deploy. Existing policy roles are authoritative.
Fresh native installer and validator enrollment remain gated, as do funding,
bond registration, automatic provider capacity provisioning, unattended
credentials, public dashboard publication and RPC failover. Passing
preparation is not evidence of active SLA service. Test on one new host
before rolling to remaining hosts. No runtime validation in coding session.
