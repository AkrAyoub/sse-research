# R173 — Recover first VM4709 runtime from preserved genuine source and selected role

## Actual operator observations

- VM4709 successfully retrieved actual VM4707 native Besu/Lighthouse public bootstrap identity anonymously, without hardcoded IP or GitHub login.
- First R170 installer selected the observer role and returned an opaque failure.
- Read-only VM4709 evidence now reveals **the original R170 public checkout and root-owned 0600 selected-role JSON are both already staged**. The public source phase did NOT fail.
- Docker CLI and daemon are installed and active; 3 old unrelated Docker containers are exited; NO new SSE Besu/Lighthouse container exists; ZeroTier service is inactive; disk has ~93 GB free.
- The original release checkout is at `/opt/sse/releases/df3df85190789cc14fe6920a248f6a7545a44197` and must NOT be replaced or modified. Last VM4707 confirmed R170 regression: 1131 OK, 3 skipped.
- Because R152 historically swallowed command-specific errors, **ZeroTier inactive is evidence but not proof that ZeroTier installation was the exact failing stage**.

## Recovery design

**Do not rerun R147**: its create-once guard must reject existing source/selection and silently forcing a reset could destroy original node data.

New `tools/sse_pos_r173_vm4709_recovery_gate.py` checks current host state without mutation or reading validator/wallet secrets:
- Existing PRIVATE root-owned selection is for the exact original pinned R170 SHA, role `observer`, matching chain31340 original-source flags and valid node ID.
- Exact original public genesis archive already staged under original release is byte-verified against immutable R59 SHA256 `1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7`.
- Docker READ-ONLY listings prove there is no preexisting SSE EL/CL resource; any SSE prefix refuses recovery.
- Read-only Docker daemon and ZeroTier statuses are recorded.
- Nothing gets restarted/deleted/overwritten; the old source install is preserved; any mismatch stops.
- This is specific to the actual VM4709 first observed R170 install state, not a general force-reset / validator rollout.

R152 now reports fixed redacted identifiers such as `R152_APT_UPDATE_EXIT_N`, `R152_ZEROTIER_GPG_VERIFY_EXIT_N`, `R152_ZEROTIER_VENDOR_INSTALL_EXIT_N`, `R152_ZEROTIER_DAEMON_EXIT_N`, `R152_ZEROTIER_JOIN_EXIT_N`, `R152_PINNED_CLIENT_IMAGE_PULL_EXIT_N`. No raw command stderr/credentials in exceptions. Mocked unit tests cover these stages.

## One guarded real recovery, after green pinned source tests

Only on VM4709. In a new anonymous public checkout of pinned R173 source:
1. Run `sudo python3 -B tools/sse_pos_r173_vm4709_recovery_gate.py`.
2. If the read-only gate confirms immutable R170 archive, selected observer role, and no preexisting SSE containers, **run the R173 R151 entrypoint directly**:
   `sudo python3 -B tools/sse_pos_r151_unattended_full_node.py --execute`.
3. R151 loads the existing R170 private selection and its exact verified archive under `/opt/sse/releases/`. The executable code is the freshly tested R173 checkout, not a mutation of the previous pinned release. It performs actual current native peer discovery BEFORE modifying packages, then resumes real R152 signed Docker/ZeroTier setup and R137 Besu+Lighthouse creation.
4. If any command fails, preserve the stage and inspect current Docker and systemd state; do not rerun R147, delete the installed release, or blindly rerun R151 again.

This is an intentional guarded **continuation of the existing selected role**, not a new permission to join or an alternative genesis. Do not claim live native peer handshakes or finality until actual client observations prove them.

## Remaining scientific/architecture gaps

GitHub Issue #42 is an interim, centralized, short-TTL optional rendezvous (not infrastructure independence). VM4707 records expire every 600 seconds and must be genuinely refreshed. The new VM does NOT require GitHub authentication, manual genesis, static IP or copied validator signing key. Real native EL+CL peer handshakes/finalized checkpoint comparison and actual dynamic independent discovery, validator stake custody/TEST ETH activation, and genuine SSE market workloads remain unverified.
