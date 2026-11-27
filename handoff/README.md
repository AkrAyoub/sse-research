# SSE handoff — start here

Read [../CLAUDE.md](../CLAUDE.md) first (also linked from AGENTS.md for Codex). This branch is a documentation handoff layered onto R430, not a tested release. Existing history and evidence preserved. No running VM state changed.

| File | Purpose |
|---|---|
| REQUIREMENTS.md | Consolidated owner requirements, new dashboard/cloud workflow, security and scientific invariants |
| STATE_AND_EVIDENCE.md | Latest deployed topology, exact source/runtime distinctions, experiments and known limitations |
| ROADMAP_AND_ACCEPTANCE.md | Dependency-ordered engineering tasks and acceptance tests |
| PROVENANCE.md | Historical evolution, exact revision references, complete base file index, missing sources |
| WORK_LOG.md | Durable checkpoint for autonomous coding and context resets |
| references/MILESTONE3_REPORT_EXTRACT.md | Supplied report text, original PDF authoritative |
| references/PROPOSAL_EXTRACT.md | Supplied proposal text, original PDF authoritative |

Existing docs/ and evidence/ retained. Start at WORK_LOG, not stale immediate instructions at top of earlier docs. Keep original branch/main intact. At completion create HAND_BACK.md with exact commits, tests, blockers and owner-run staged installation/validation plan.

## Launch prompt
Read CLAUDE.md and all linked handoff files. Continue actual implementation autonomously on the current branch, using the latest verified checkpoint. Work in dependency order and prioritize complete tested vertical slices. Follow all safety boundaries, never mutate live chain or VMs. Commit changes and tests, maintain WORK_LOG before context exhaustion, and resume from it after resets. If process/quota stops, leave a recoverable checkpoint and continue when restarted. Do not stop after writing a plan. Produce HAND_BACK.md with results, remaining tasks and exact owner-run validation instructions. 
