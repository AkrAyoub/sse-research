# R64 — existing owner native P2P migration READ-ONLY state inventory

**Status 2026-11-21:** GitHub source only, NOT executed on VM. The last actual operator's nonsecret VM4706 inventory shows ZeroTier One 1.16.2 **installed**, `systemctl is-active zerotier-one` **active**, genuine official apt GPG key fingerprint `74A5E9C458E1A431F1DA57A71657198823E52A61`, official signed repository present, and `zerotier-cli listnetworks` `ff2328775f000000` **OK PUBLIC**, host 6plane `fca0:2328:776e:4750:395b::1/40`, transport TUNNELED. Original VM4707 host already present in same public ad-hoc overlay. **R63 installer is complete in OS/membership terms; DO NOT REINSTALL.** Its earlier reported R63Refused was an installer return/error-path limitation; after-the-fact status cannot tell exact final failure step. No original client settings, Docker network, signing key or genesis changed by these observations; actual latest original client restart/health will be measured by R64. No native Besu/Lighthouse P2P observed.

## What is implemented

`tools/sse_pos_r64_owner_native_public_p2p_migration_audit.py` runs only in original VM4706 checkout. It **refuses ALL mutation** and combines:
1. Exact reviewed SHA, original EL+BN+VC original genesis/JWT-metadata and Docker running/internal-only checks already enforced by R63.
2. Independently re-reads current actual `ff2328775f000000` `OK PUBLIC` and valid 6plane IPv6 for original owner, with 1.16.2 CLI. No private provider-LAN bootstrap allowed.
3. Verifies each **original** Besu EL, Beacon and validator client is running with only the original isolated bridge attached. Verifies immutable image-ID syntax and records only allowlisted network flag values; Docker mount inventory reports counts, recognized target mount points and whether bind-mounted, but NEVER host filesystem mount source paths, full client argv/env or private validator/JWT contents.
4. Runs R62 already-proven **local host Python in the ORIGINAL running EL/BN network namespaces**, rechecking genuine local chain31340 execution `eth_chainId`, `eth_blockNumber`, peer count and Lighthouse Beacon actual genesis/head/finalized epoch/root. Refuses if original EL/CL genesis identity differs. Reports original native EL `--p2p-enabled=false` and missing external native peers **without claiming Ethereum native sync**.
5. Determines exact state/mount relationships necessary to design a controlled source-reviewed future R65 EL/CL P2P migration with same signed original chain, one VC, no new genesis, protected Engine8551 and no provider-private-LAN P2P.

`tests/test_sse_pos_r64_owner_native_public_p2p_migration_audit.py` defines **10 source/mock tests**, NOT YET VM-tested.

## Run on VM4706 ONLY — no new installation and no SCP

```bash
(
 set -e
 cd "$HOME/sse-research"
 export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes"
 git fetch --no-tags origin feature/r19-fresh-external-node-preflight
 SHA="ada6cf9bc84a1fd6944e6c7a40b1feff2901ef7c"
 git switch --detach "$SHA"
 test "$(git rev-parse HEAD)" = "$SHA"
 python3 -B -m unittest discover -s tests -p 'test_sse_pos_r64_owner_native_public_p2p_migration_audit.py' -v
 echo "R64_SOURCE_TESTS_PASSED=true"
 sudo -v
 python3 -B tools/sse_pos_r64_owner_native_public_p2p_migration_audit.py --audit --expected-commit "$SHA"
)
```

**No `--apply` exists.** Do not stop/restart original containers until state and mounts are understood and a consistent recoverable backup and reviewed rollback are ready. No SSH/SCP is needed between VMs.

## Next migration engineering decision

Existing original G2 client containers are on `sse31340-g2-internal`, which is IPv4-only and internal, and EL `--p2p-enabled=false`. Docker cannot retrofit existing container `--publish` mappings. R65 must preserve ORIGINAL EL DB, BN DB, VC identities and slashing protection while enabling actual native IPv6 P2P listening/ENR on owner host's verified 6plane address. Protect Engine API JWT on an isolated trusted local bridge, no external port 8551, and preserve Docker DNS connectivity between original VC and BN. A maintenance window/owner authorization/backup may be required to recreate original EL and Beacon process containers, but **not original blockchain database or signer identity**. Binding external P2P only to overlay IPv6 is mandatory. Linux Docker overlay host ports must be tested from outside provider network. Independent third-party original-source bootstrap and signed CL+EL discovery are required; ZeroTier's roots/relay dependencies remain an infrastructure limitation.

The next live native peering trial must include an outside provider laptop, not a provider-private LAN, and compare exact original genesis/finalized roots. Never claim overlay IPv6 alone proves no private-LAN underlay.

Original evidence: journal Entry 096 for original true execution block3029 and Beacon epoch97; Entry 098 for interrupted R63; Entry 099 for actual ZeroTier completion. Current official docs: https://docs.docker.com/engine/network/port-publishing/ ; https://docs.besu-eth.org/public-networks/reference/options ; https://lighthouse-book.sigmaprime.io/advanced_networking.html .
