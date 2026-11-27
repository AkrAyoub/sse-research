# Governing owner instruction — source-code-only development session (2026-11-27)

Status: AUTHORITATIVE. Supplied by the owner (AyoubAkr) on 2026-11-27. It takes precedence over every
conflicting instruction in CLAUDE.md, AGENTS.md, README files, historical roadmaps, installation
instructions, test instructions and other repository documents, including after context resets.
This file is a faithful condensed transcription of the owner prompt (numbered sections kept); where
wording is shortened, no restriction has been weakened.

## 1. Mission
Audit, complete, improve, refactor, correct, secure and consolidate the entire SSE codebase during the
unattended session. Produce a coherent, scientifically sound, implementation-ready codebase that the owner
will later compile, install, deploy and test on the actual development VMs. Responsibility is
SOURCE-CODE DEVELOPMENT ONLY.

## 2. Absolute execution restrictions
The agent MUST NOT: execute application code; execute Python, JavaScript, TypeScript, Solidity or other
project code; compile contracts or other software; execute unit/integration/fuzz/invariant tests or test
suites; run Forge, Anvil, Cast, Hardhat or blockchain dev environments; use Docker or Docker Compose; use WSL;
create or use VMs, containers, emulators or remote execution environments; install software, dependencies,
packages, libraries, compilers or tools; run package managers; start servers, applications, agents, chain
clients or background services; run installation, deployment, migration, build or initialization scripts;
execute project scripts, including scripts the agent writes itself; access or modify existing VMs; connect
to or modify the existing blockchain; broadcast transactions, deploy contracts or create wallets; access
SSH, remote cloud environments, live signer APIs or private signing material; circumvent these restrictions
with alternative tools or environments. Do not trigger remote CI as a substitute.
ALLOWED: repository navigation, file reading/searching, source editing and Git version control (local,
dedicated handoff branch). Tests, fixtures, installers, deployment scripts, CI config and Dockerfiles may be
written as source but never executed. Anything requiring execution is documented for owner verification.

## 3. Self-testing is static and non-executing
Manually inspect syntax, imports, signatures, ABIs/events, state machines, serialization, math, financial
conservation, security invariants, authorization, boundaries, error handling, replay/duplicate risks,
frontend/backend and API compatibility, installer consistency. Trace workflows manually. Write
comprehensive tests (normal/abnormal/adversarial/boundary) but do not run them. Never claim pass/compile/
start/work unless supported by previously recorded actual evidence. Status classes:
Existing live-verified | Previously execution-tested | Newly implemented | Statically reviewed |
Automated tests written but not executed | Awaiting compilation | Awaiting runtime validation |
Awaiting deployment | Blocked | Not implemented. Static review != compilation or runtime testing.

## 4. Required reading
CLAUDE.md, AGENTS.md, handoff/README.md, REQUIREMENTS.md, STATE_AND_EVIDENCE.md, ROADMAP_AND_ACCEPTANCE.md,
PROVENANCE.md, WORK_LOG.md, handoff/references/, relevant historical architecture/evidence. Inspect actual
source. Baseline R430 + handoff commits. V3 deployed and experimentally exercised; V4 unfinished. Reconcile
contradictions using source, history and latest verified evidence. Source HEAD != deployed versions.

## 5. Initial comprehensive audit
Identify implemented / historically compiled+tested / verified on chain / candidate-only / partial /
disconnected / obsolete / duplicated / contradicting requirements / unimplemented / misdocumented /
weak (architecture, science, finance, security) / needing runtime verification. Map dependencies, intended
final architecture vs current. Do not spend the whole session auditing; convert to tasks and resolve.

## 6. Preserve SSE science
Settlement-Sufficient Evidence and exposure-aware continuation under uncertainty. Preserve admissible
histories, N/F/S interpretation, lower/upper entitlement bounds, guaranteed provider payments and consumer
refunds, explicit unresolved exposure, conservation, monotone refinement, exposure-aware admission, escrow,
evidence closure, bilateral residual allocation, conservative treatment of insufficient/conflicting evidence,
explicit assumptions. No arbitrary binary verdicts; authenticated observation != proof of physical delivery;
missing responses/network failures != proven violations.

## 7. Smart contracts
Complete/consolidate V3 review, V4 candidate market, adaptive and standby-compatible ledgers, global
sampling, ordered primary/standby selection, confirmation/promotion, capacity-backed eligibility,
collateral/capacity reservation, quorum, monitor/executor incentives, qualified negative evidence,
ack/response semantics, permissionless settlement, concurrent leases, safe cancellation/expiry/refunds,
evidence retention, monitor entry/exit/bond. Integrate standalone components; avoid more isolated helpers.
Preserve V3. Static review of size, gas, auth, reentrancy, arithmetic, replay, lifecycle, conservation.
Write Solidity regression/fuzz/invariant tests; do not compile or execute.

## 8. Permissionless chain
Genuine Ethereum-compatible native PoS with valueless TEST ETH; open join on objective rules. Preserve
native EL/CL, block production, staking, dynamic validator entry/exit, native rewards/penalties, slashing
protection, full-node verification, optional archive, optional RPC-connected apps, dynamic and concurrent
roles, replaceable discovery, multiple RPC options. No central membership, mandatory RPC, private LAN, fixed
IPs, mandatory login, artificial rewards, synthetic activity, fake decentralization claims. Distinguish
operators, machines, nodes, validator identities, wallets. Document NAT, bootstrap, weak subjectivity,
relay, stake concentration, Sybil and TEST ETH economic limits.

## 9. Marketplace via UI
Consumer: browse services, create requests with CPU/RAM/storage/execution needs, measurable SLAs, upload
code/files/data, review artifacts/commitments, choose monitor count and fault tolerance, check eligibility,
see quorum/assumptions, monitoring and standby costs, fixed epochs or provider-proposed, fees/total, compare
bids, award without minimum bid count, fund/authorize, track, retrieve outputs, inspect evidence/payments/
refunds/exposure. Provider: browse/filter/inspect requests, advertise actual resources, review authorized
workload info, bid with price/resources, propose epochs, accept, automatically execute awarded+accepted+
funded+admitted workloads, track reservations, concurrent workloads, signed ack/response, deliver outputs,
logs/SLA/earnings/history. Bidding alone never starts a paid workload. Real services, not placeholders; start
from existing compute workload. Secure artifacts, commitments, bounded uploads, isolation, access control,
limits, execution authorization. Docker files may be written, never run.

## 10. Monitor selection / standby / security
Consumer-configurable committee size and fault tolerance; feasibility; bonded+capacity eligibility;
exclude counterparties; show quorum; explain insufficiency; suggest alternatives without silent weakening;
compensation; reserve capacity+collateral; concurrent assignments; committed randomness; predetermined
standby order; promotion; quorum integrity; no duplicate identities; no inactive standby voting; no
membership change during admitted epochs; safe release after cancel/close. Analyze randomness/proposer
influence, selective confirmation, adversarial standbys, collusion, Sybil, operator independence. A bonded
wallet/unique address does not prove an independent operator. Write math analyses and tests (not executed).

## 11. Agents
Source-level: market and assignment discovery, monitor confirmation, standby activation, service execution,
consumer epoch progression, SLA monitoring, evidence submission, permissionless transitions, concurrent
leases/roles, durable cursors, idempotency, tx reconciliation, safe retry, restart recovery, resource
reservation/release, bounded local signing authorization, persistent logs/evidence. No unattended spending
without bounded owner authorization. Do not run agents.

## 12. Dashboard
Navigable responsive interactive UI for consumer, provider, monitor, validator, full/archive node and
multi-role participants (see owner list), backend-connected, no static mocks, no secrets, no unnecessary
login. Public dashboards read-only; privileged actions via owner-local controls or wallet authorization.

## 13. Explorer
Blocks/headers/hashes/parents, txs/inputs/receipts/events/gas/basefee/priority fee, state/tx/receipt
roots, slots/epochs/finality, validators, accounts/balances/code, known storage layouts, raw slots, real
proofs and proof-path visualizations, storage usage, historical availability, search/filter/pagination.
Distinguish local vs remote, full vs archive, historical blocks vs historical state, finalized vs not,
pruned/unavailable vs zero. Never invent trees/proofs/metrics/history.

## 14. Installer (source only)
Single-command onboarding: host checks, dependency install, verified release, client config, chain/genesis
verification, peer discovery, RPC discovery/failover, multi-role, full or light connectivity, optional
archive, secure wallet init, optional TEST ETH funding, validator activation, monitor bonding, provider/
consumer config, persistent services, dashboard, public HTTPS, terminal commands, restart recovery,
idempotency, upgrade/rollback. No manual IPs/addresses/VM names/ports/dev paths. Implement and statically
review; never run.

## 15. Security / quality audit
Authorization, public endpoints, secrets, keys, command execution, uploaded code, traversal, archive
extraction, exhaustion, SSRF, replay, duplicate payments/txs, reentrancy, accounting, consensus assumptions,
committee transitions, unbounded loops, gas, races, concurrency, API consistency, stale state, recovery,
exceptions, dependencies, config. Fix in source; mark unprovable properties as needing validation.

## 16. Mandatory documentation structure
handoff/audits/: INITIAL_CODEBASE_AUDIT, ARCHITECTURE_AUDIT, SMART_CONTRACT_AUDIT,
SCIENTIFIC_CORRECTNESS_AUDIT, SECURITY_AUDIT, NETWORK_AND_DECENTRALIZATION_AUDIT,
AGENT_AND_RUNTIME_SOURCE_AUDIT, DASHBOARD_AND_UI_AUDIT, INSTALLER_AUDIT,
DEPENDENCY_AND_COMPATIBILITY_AUDIT, FINAL_STATIC_AUDIT (.md).
handoff/planning/: MASTER_ROADMAP, MASTER_TASK_CHECKLIST, REQUIREMENTS_TRACEABILITY,
IMPLEMENTATION_DEPENDENCIES, BLOCKERS_AND_LIMITATIONS, DESIGN_DECISIONS, DEFERRED_RUNTIME_VALIDATION,
REMAINING_EXPERIMENTS (.md).
handoff/logs/: DEVELOPMENT_LOG, CHANGES_LOG, STATIC_REVIEW_LOG, BUGS_AND_FIXES_LOG,
TEST_IMPLEMENTATION_LOG, ARCHITECTURE_EVOLUTION_LOG, REFACTORING_LOG, CONTEXT_RESUME_LOG (.md).
One authoritative master checklist (MASTER_TASK_CHECKLIST.md). Per task: requirement, original status,
files/symbols, dependencies, solution, changes, decisions, alternatives, static review, tests written,
runtime validation needed, risks, status, commit. Keep history; do not invent logs/results.

## 17. Traceability
Each requirement -> source/instruction, component, files, status, test source, static status, runtime
verification needed, acceptance criteria. Sources: proposal, milestone reports, Milestone 4 (if available),
handoff docs, earlier decisions, latest owner requirements, discovered necessities. Distinguish academic vs
engineering vs agent recommendations; document unavailable materials.

## 18. Refactoring
Toward coherent architecture; preserve git history, branches, evidence, research materials, V3
compatibility, native chain infrastructure, owner security mechanisms. Inspect dependencies before removal
and record reasons. Remove dev-VM assumptions and abandoned login where safe. No history rewrite,
force-push, main merge or branch deletion.

## 19. Procedure (per cycle)
Inspect -> identify problem -> audit deps/science -> update roadmap/checklist -> implement -> write tests ->
static review -> find defects -> fix -> update docs/logs -> commit locally -> next task. Do not stop at plans.
Conservative reversible documented decisions. Blocked/awaiting-validation tasks are marked and skipped.

## 20. Context resets
Maintain handoff/WORK_LOG.md (branch, commit, state, files, audits, tasks, static checks, issues, tests
written-not-run, blockers, priorities, next steps, constraints, these restrictions). After a reset reread
this file, CLAUDE.md, WORK_LOG, master roadmap/checklist, relevant logs; resume first unfinished task.

## 21. Deferred runtime package
Staged runbook: dependencies, integrity, Python/Solidity compile, unit/fuzz/invariant/integration tests,
bytecode size, deployment verification, chain interaction, validators, onboarding, installer, dashboard/
marketplace, uploads, provider execution, monitoring/standby experiments, settlement, concurrency,
failure/recovery, security, independent infrastructure, reboot/logout persistence, final demo. Each with
commands, prerequisites, expected behavior, safety, failure handling, acceptance. Distinguish historically
verified commands from new ones. Fabricated live results prohibited.

## 22. Handback
handoff/HAND_BACK.md, final roadmap/checklist, initial+final audits, logs, traceability, architecture and
science docs, source, tests, deferred runbook, deployment/migration plan, onboarding runbook, risk register,
commit refs, remaining tasks. Separate live-verified / execution-tested / newly implemented / statically
reviewed / awaiting compilation / tests awaiting execution / awaiting deployment / unfinished. Honest.

## 23. Final
Develop, audit, reason, improve, implement, refactor, fix, integrate, document source. NOT authorized to
compile, execute, install, deploy or runtime-test anything, by any route.
