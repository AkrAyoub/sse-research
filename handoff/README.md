# SSE handoff — start here

Read [../CLAUDE.md](../CLAUDE.md) first (also linked from AGENTS.md for Codex). This branch is a handoff layered onto R430, not a tested release. Since 2026-11-27 work here is SOURCE-ONLY (see GOVERNING_INSTRUCTION.md): nothing on this branch after R430 has been compiled or executed unless a record says so. Existing history and evidence preserved. No running VM state changed.

| File | Purpose |
|---|---|
| REQUIREMENTS.md | Consolidated owner requirements, new dashboard/cloud workflow, security and scientific invariants |
| STATE_AND_EVIDENCE.md | Latest deployed topology, exact source/runtime distinctions, experiments and known limitations |
| ROADMAP_AND_ACCEPTANCE.md | Dependency-ordered engineering tasks and acceptance tests |
| PROVENANCE.md | Historical evolution, exact revision references, complete base file index, missing sources |
| GOVERNING_INSTRUCTION.md | Owner source-only governing instruction (highest precedence) |
| planning/, audits/, logs/ | Master checklist, roadmap, deferred owner-run validation, audits and development logs |
| WORK_LOG.md | Durable checkpoint for autonomous coding and context resets |
| references/MILESTONE3_REPORT_EXTRACT.md | Supplied report text, original PDF authoritative |
| references/PROPOSAL_EXTRACT.md | Supplied proposal text, original PDF authoritative |

Existing docs/ and evidence/ retained. Start at WORK_LOG, not stale immediate instructions at top of earlier docs. Keep original branch/main intact. At completion create HAND_BACK.md with exact commits, tests, blockers and owner-run staged installation/validation plan.

## Launch prompt (superseded 2026-11-27 — source-only session)
The governing instruction is GOVERNING_INSTRUCTION.md: SOURCE-CODE DEVELOPMENT ONLY. Read CLAUDE.md, GOVERNING_INSTRUCTION.md, WORK_LOG.md and planning/MASTER_TASK_CHECKLIST.md. Continue actual source implementation autonomously on the handoff branch in dependency order. Do not compile, execute, test, install, deploy, start services or touch the live chain/VMs; write tests and scripts as source only and record every execution step in planning/DEFERRED_RUNTIME_VALIDATION.md. Commit locally, keep WORK_LOG current, resume from it after resets. Produce HAND_BACK.md with results, remaining tasks and exact owner-run validation instructions.

Previous launch prompt (historical, its "run tests" wording no longer applies): "Read CLAUDE.md and all linked handoff files. Continue actual implementation autonomously on the current branch ... Produce HAND_BACK.md with results, remaining tasks and exact owner-run validation instructions."
