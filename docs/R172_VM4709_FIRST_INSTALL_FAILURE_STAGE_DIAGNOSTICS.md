# R172 — Actual VM4709 installer failure and safe diagnostic

Observed first VM4709 installation attempt on pinned R170 SHA df3df85190789cc14fe6920a248f6a7545a44197:
- Anonymous public GitHub R168 peer discovery PASS: 1 current R156 genuine EL/CL peer record.
- One real local role menu; observer (2) selected.
- Installer exit: R147_PUBLIC_INSTALL_REFUSED: host prerequisite or GitHub command failed.
- Because the R170 code suppressed command details, NO exact failing command can legitimately be identified from this log. Container state was not shown; neither node launch nor absence of side effects can be assumed.
- Existing VM4707 later refreshed the real GitHub peer record, with original chain and signing services untouched.

R172 fixes:
- scripts/sse_install.py command execution now reports a bounded fixed stage identifier and failure exit class for APT_UPDATE, APT_INSTALL, PUBLIC_GIT_CLONE, PINNED_COMMIT_PRESENT, PINNED_COMMIT_CHECKOUT, PINNED_COMMIT_HASH, UNIFIED_ROLE_PLAN, REAL_EL_CL_HOST_AND_CONTAINER_INSTALL. Timed out and unavailable are differentiated. Never print potentially sensitive command stderr, argument values or stdout.
- New --inspect-failed-host performs READ-ONLY existence checks for /var/lib/sse/selection.json and /opt/sse/releases and counts release entries only. No root permissions, pinned SHA, Docker mutation or private file reads needed. safeToBlindlyRetry always false.
- Unit tests mock every stage and failed timeout and assert no secret disclosure, plus empty/partially staged host inventory.
- No changes to original genesis, wallet, validator, ZeroTier admission rules or existing running VM clients.

Owner next performs read-only inventory on VM4709, using reviewed R172 public source checkout:

    python3 -B scripts/sse_install.py --inspect-failed-host
    sudo test -e /var/lib/sse/selection.json && echo SELECTION_PRESENT || echo SELECTION_ABSENT
    sudo test -d /opt/sse/releases && echo RELEASE_DIR_PRESENT || echo RELEASE_DIR_ABSENT
    command -v docker >/dev/null && sudo docker ps -a --format '{{.Names}} {{.Status}}' || true
    command -v zerotier-cli >/dev/null && sudo zerotier-cli status || true

Do not blindly rerun privileged installer on a partly installed node, overwrite existing chain files or remove Docker resources. After host state is known, exact failing R172 stage can be diagnosed on an appropriately safe retrial.

Last verified VM4707 green: R170 1131 tests OK (3 skipped). R172 itself still requires VM testing. The public peer record has a 600-second TTL and must be genuinely refreshed before an authorized join, while GitHub discovery is still centralized and temporary. Genuine native EL/CL peering, finalized-root convergence, independently operated discovery, and validator/marketplace roles are still unverified.
