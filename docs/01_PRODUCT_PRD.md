# 01 — Product requirements (PRD)
## Problem and audience
Autonomous AI coding agents are useful but their completion messages do not prove tasks are correct or policies were obeyed. Target users are engineering teams, AI platform teams and security reviewers approving AI-created changes. Adjacent products include agent observability, policy enforcement, and AI review; our deliberate niche is **claim-to-evidence outcome verification**.

## Product proposition
User chooses an approved bounded coding task and guardrails. An external coding agent (or our small Nemotron-driven demo agent) operates in a monitored sandbox. ProofLayer records tool observations, runs an *independent* verifier, challenges claims with additional tests, and emits signed-off evidence statuses. The system accepts UNKNOWN as a valid answer.

## Explicit scope
### P0 (must ship)
- Landing/dashboard with three fixtures and run history.
- New run wizard: task title, fixture repository snapshot, allowlisted editable paths, required checks, duration and token budget.
- Agent runtime adapter: can launch our bounded demo agent, optional external agent adapter later.
- OpenShell integration adapter with deny-by-default tested policy; direct enforcement events read from real OpenShell telemetry.
- Run execution: queued / provisioning / running / verifying / completed / failed / inconclusive / canceled.
- Deterministic verifier: diff allowlist; command/test execution in separate verifier sandbox; exit codes and stdout/stderr capture; conditions on expected artifacts.
- Agent claim collector; mapping of `claim_id -> requirement_id -> verification evidence`.
- Nemotron planner generating *candidate* requirements and safe test suggestions; rules require validator approval and trusted execution.
- Stream or poll live events to trace screen.
- Certificate export as versioned JSON, SHA256 chain, verification flags and report.
- Three repeatable fixture runs with non-fabricated evidence.
### P1 (if time)
- Proof Challenge button: strict schema candidate test generation then safe test runner.
- Tavily optional retrieval with citations from trusted docs and fixed domains; trace retrieved source provenance.
- Compare baseline vs ProofLayer detection on benchmark.
- Separate Nemotron Nano/Super routing with token/cost accounting.
### P2 / explicitly not planned
- Universal agent interception; formal correctness proofs; broad production cloud permissions; arbitrary external repositories; multi-tenant billing; Cosmos / GROOT / hardware; unrestricted tool execution; automatic changes to production repos; blockchain.

## Pages / UX
1. `/` hero and quick-start demo.
2. `/runs` runs table with statuses and filters.
3. `/runs/new` fixture selector, policy preview, expected required checks, launch.
4. `/runs/[id]` three-pane: task/claims, live timeline, results. Responsive stack on mobile.
5. `/runs/[id]/challenge` proposed tests, validation gate, execute, diff outcomes.
6. `/runs/[id]/certificate` claim verdicts, evidence refs, artifact download.
7. `/benchmarks` aggregate precision/recall, false block rate, overhead, scenario manifest.
8. `/settings` model config status, environment/credit status (never expose secret values).

## Core personas and stories
- Engineer: 'When my coding agent says a patch is done, I want the complete regression suite independently rerun so I can trust the merge decision.'
- Security engineer: 'When a forbidden read is attempted, I need evidence from the enforcement point rather than a model-generated assertion.'
- Technical judge: 'I want one-click replay of three cases with actual test outputs and clear system boundaries.'

## Data retention/privacy
Fixture repositories contain only synthetic content. No real credentials. Redact tool logs before persistence. Export certificates contain hashes and safe metadata, not secret text. Default TTL 24h for temporary workspaces; purge run artifacts by configurable policy. Access to logs and certificates should be authenticated before any public multi-user deployment.

## Success / exit criteria
- All 3 scenarios execute reproducibly locally and expose actual observations.
- Nonzero independent test result becomes FAILED regardless of agent report.
- Blocked restricted read becomes VIOLATION_ATTEMPT and NEVER 'secret exfiltrated'.
- Success case passes required checks, no unapproved diff, complete evidence set.
- Hash chain validator finds modified/deleted/reordered events; must document limits if attacker also controls storage.
- Demo hosted in safe read-only/replay mode if secure live execution cannot be safely public.
- Page readable and responsive; basic keyboard accessibility; no browser secrets.

## Quality bars
P95 UI latency for cached timeline <=2s locally (target), cold sandbox execution can take longer; max ~120s per run in demo; budget capped in config. Targets are aspirational; publish measured values.
