# R189 — actual R188 existing client recovery succeeds but Lighthouse SSZ bind mount unreadable

Real VM4709 output on 2026-11-23:

- R188 four targeted tests PASS and actual read-only `--plan` PASS.
- Owner intentionally authorized R188 `--execute --authorize RECOVER-VM4709-PRESERVING-OLD-CLIENTS`.
- Actual reports:
  - `R188_FRESH_BEACON_DATA_STAGED_OLD_DB_PRESERVED=true`
  - `R188_OLD_BN_CONTAINER_RENAMED_PRESERVED=true`
  - `R188_OLD_EL_CONTAINER_RENAMED_PRESERVED=true`
  - `R188_NEW_EL_CONTAINER_SUBMITTED=true`
  - `R188_NEW_BN_CONTAINER_SUBMITTED=true`
- The original old exact containers are STOPPED, renamed `-r188-preserved`, not deleted. The original populated Lighthouse chain/freezer/blob DB remains in its original data directory; copied local P2P identity, verified genesis and Engine JWT preserved.
- New exact EL and CL container names were up less than a second when checked; EL health starting, EL startup logs initially empty.
- REAL new Lighthouse log `Unable to open /checkpoint/checkpoint-state.ssz: Os { code: 13, kind: PermissionDenied, message: "Permission denied" }`. This is NOT a proof that the checkpoint state is bad. The existing genuine VM4709 R187 downloaded public checkpoint directory was created as 0700, public files 0600 owned by the nonroot VM user; inside the hardened `--cap-drop ALL` Docker container, UID 0 lacks CAP_DAC_OVERRIDE to read user-owned bind-mounted files. This safety-preserving policy is why it cannot read them.

## R189 implementation and direct one-time on-host repair

- Updated R187 **future-node** anonymous downloader to stage ONLY publicly published SSZ state, block and manifest with read/traverse permissions directory 0755, files 0644. No parent changes, no access grants for JWT, wallets, data roots or private P2P identity.
- Updated R188 recovery preflight to refuse if those exact public checkpoint files or directory lack other-read/other-execute bits before launching the container. R188 already fully executed on VM4709; never rerun `--execute`.
- Added focused R187 mode regression (unit tests are code-only; actual deployment evidence remains separate).
- Current VM4709 repair: check exact real SHA256, verify none of the 3 paths is a symlink; `chmod 0755 /home/ayoubakrvm4709/sse-chain31340-checkpoint-e565`; `chmod 0644` only three public checkpoint files; restart only the new Lighthouse container once, inspect EL and CL real logs and health. The existing database, original prior containers, testnet/genesis, Engine JWT, host firewall, SSH, wallet, validator must remain untouched.
- No success claims until Lighthouse validates the actual original owner e565 SSZ pair, EL+CL are stable, native peers >0, syncing=false and matching finalized root across VM4707 and VM4709. The top-level original VM4707 beacon finalized and published checkpoint succeeded previously; independent external infrastructure and full SSE marketplace remain out of scope of this specific fix.

No extra GitHub checkpoint release is necessary; existing e565 release SHA256 and original genesis identity were already verified. This addresses a real client permission error, not peer transport.
