# SSE agent instructions

Read and follow [CLAUDE.md](CLAUDE.md) and, first of all, [handoff/GOVERNING_INSTRUCTION.md](handoff/GOVERNING_INSTRUCTION.md).
The same constraints apply to Codex and every other coding agent.

**Current session mode: SOURCE-CODE ONLY.** Do not execute, compile, test, install, deploy, start services, use Docker/WSL/VMs/CI,
or touch the live chain, VMs, wallets or keys. Write tests and scripts as source only; record every command that would need
execution in handoff/planning/DEFERRED_RUNTIME_VALIDATION.md for the owner to run later. Never report a test or build as passing
unless historical evidence already records it.

Continue from handoff/WORK_LOG.md and handoff/planning/MASTER_TASK_CHECKLIST.md; update WORK_LOG before a context reset and after
each meaningful task. Do not deploy or mutate the live network. Preserve the original branch, main and the scientific V3 baseline.
