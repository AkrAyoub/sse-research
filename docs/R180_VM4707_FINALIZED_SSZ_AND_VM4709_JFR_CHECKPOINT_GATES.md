# R180 — real R179 verification, Docker JVM JFR test caveat and trusted checkpoint preflight

## Actual VM evidence 2026-11-23

Original owner VM4707 ran R179 pure 2 tests OK, and its REAL localhost Lighthouse REST validated original genesis validators root `0xda5c089a2f9261d547bdeb8f129bdb5d174cb925c486670b129b17d1e2fcbedd` and finalized epoch `560`, slot `17920`, root `0x166faa9e332bbe4ff749d486e88de74bec3339efcc38dfb3659cb149f89954dd`. Separate read-only calls for `/eth/v2/debug/beacon/states/finalized` and `/eth/v2/beacon/blocks/finalized` with `Accept: application/octet-stream` each returned HTTP 200, Content-Type `application/octet-stream` and first 32 bytes. These prove owner checkpoint bytes are available on localhost. They are NOT proof a third-party VM can access this private Beacon API. Do not expose it publicly without authentication and scoped access.

Actual new VM4709 tried a **disposable** image `hyperledger/besu@sha256:4fd2ba40f0d65917bcb3abd9af60673946f66dee2ecb1b87f7cdfa6a30fe458d` version check with `--entrypoint /opt/besu/bin/besu --read-only --cap-drop ALL --security-opt no-new-privileges --network none`. JVM exited before printing version:
`Error occurred during initialization of VM`
`Failure when starting JFR on_create_vm_3`.
This particular disposable command OMITTED the actual R137 `--tmpfs /tmp:rw,nosuid,exec,size=256m` writable scratch filesystem. JFR startup can require writable scratch. The outcome is **inconclusive** as to binary compatibility with the real container's options. Do not patch to weaken security; repeat only the disposable --version test with matching writable /tmp and CPU/memory/pid constraints before changing existing containers. If still failing, capture sanitized failure and investigate Java environment or image expectations.

Lighthouse documentation (https://lighthouse-book.sigmaprime.io/advanced_checkpoint_sync.html) states that checkpoint sync requires no existing Beacon database; the VM4709 Lighthouse had initialized `/data` and written a genesis-derived state. Do not add `--checkpoint-sync-url` to a populated database and falsely assume checkpoint sync. Do not purge or delete without inspecting file inventory and obtaining owner authorization. Preserve exact native genesis and Engine JWT, existing Docker resources, port bindings, observer role.

## Safe next verification

VM4709:
1. Repeat ONLY disposable pinned Besu `--version` with `--tmpfs /tmp:rw,nosuid,exec,size=256m`, `--read-only --cap-drop ALL --security-opt no-new-privileges --network none`. Does not run the existing client or modify its volumes.
2. Read-only list of existing observer `/root/.local/share/sse-r137-node-8be265272c35f3d8c3a0/beacon` top-level filenames, modes and total byte counts without printing file contents, JWT, or sensitive private paths. Check whether Lighthouse populated chain database.
3. Avoid restarting/replacing either existing container until we determine a safe reversible plan for the data and pinned image identity. No `--ignore-ws-check` or an exposed public Beacon API.

VM4707: owner validated SSZ responses, not a publicly available checkpoint service. For remote sync use a deliberately authenticated, read-only, tightly scoped transport with exact genesis/finalized roots and no Engine API/validator secrets, then ensure VM4709 Lighthouse uses fresh checkpoint state without destroying existing data.

R179 code introduced direct Besu binary launch for **future** R137 installs, conditioned on disposable compatibility; it does not recover existing VM4709 clients yet.
