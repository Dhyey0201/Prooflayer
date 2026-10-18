# 03 — 7-day alternating commit plan (14 commits, Dhyey first)
**Sprint dates:** Mon Oct 19 through Sun Oct 25, 2026. Two serial handoffs each day: Dhyey → Ancy. Each starts from the other person's latest merged work. Across calendar days sequence continues Ancy → Dhyey. **No parallel writes on the same branch.**

## Ground rules / handoff protocol
Maintain one `main` and sequential short-lived branches. For each slot: (1) `git fetch origin && git switch main && git pull --ff-only origin main`; (2) `git switch -c feature/dN-owner-topic`; (3) implement and test; (4) commit; (5) push and open PR; (6) partner reviews & merges to `main`; (7) notify next owner with SHA, tests, blockers. If solo speed matters, the pair may allow fast-forward direct push on a private repo but PR audit is preferred. **Never push while another PR is outstanding** and never `git push --force`. Resolve conflicts during handoff.

### Day 1 — Monday Oct 19: foundation and contracts
**Commit 01 — Dhyey, `chore(repo): initialize secure monorepo and backend scaffolding`**
- Files: root README, LICENSE (MIT), `.gitignore`, `.env.example`, `Makefile`, `apps/api`, `packages/contracts`, `tests`, GitHub Actions skeleton, Compose for local SQLite & apps.
- Implement: FastAPI `/health`, `/api/v1/config/capabilities` (booleans only), request IDs, Pydantic settings and typed errors. Define core enums and database migrations.
- Tests: API health; no key leaked; secrets excluded from git; `ruff` and pytest.
- Exit: fresh clone runs API without Nebius key; CI skeleton green. Review/merge before Ancy begins.
**Commit 02 — Ancy, `feat(web): build dashboard shell and typed API client`**
- Files: `apps/web`, design tokens, navigation, hero, scenario selector, runs table mock via typed fixture adapter, a11y scaffold.
- Implement: Next.js TypeScript Tailwind, TanStack Query (optional), loading/error states, empty state; typed API client grounded in contract.
- Tests: frontend lint/typecheck/build; keyboard navigation smoke; no keys in browser bundle.
- Exit: UI navigable and connected to `/health`; fake demo values explicitly labeled sample placeholders.

### Day 2 — Tuesday Oct 20: persisted runs / active playground
**Commit 03 — Dhyey, `feat(api): persist run lifecycle and event evidence`**
- Implement run create/read/list, fixture registry, SQLAlchemy SQLite, state machine, structured `events` with per-run sha256 chain, runs fixture seeder. Enforce idempotency and request validation.
- Tests: create run; invalid scenario 422; forbidden transition rejected; event hash chain verification; concurrency sequence test.
- Exit: frontend can start/read a fixture-backed run; `/runs/{id}/events` returns ordered events.
**Commit 04 — Ancy, `feat(web): build run playground and trace timeline`**
- Implement task setup, policy preview, launch, status pills, live polling, event detail drawer, route `/runs/[id]`.
- Tests: mocked run lifecycle, error/timeout states, no false green state on missing data.
- Exit: user can create/observe a persisted run from browser (backend fixture mode clearly shown).

### Day 3 — Wednesday Oct 21: Nebius + independent verifier
**Commit 05 — Dhyey, `feat(ai): integrate Nebius Nemotron adapter and bounded agent planner`**
- Implement OpenAI-compatible SDK adapter: model discovery, strict prompt schema, token budget, retriable errors, timeouts, mocked deterministic provider for CI. Bounded step planner using only allowlisted operations and trusted fixture tools.
- Tests: mocked successful and malformed response, budget exhausted, timeout, fallback/inconclusive.
- Exit: authenticated local smoke run calls real Nemotron if key present; never requires paid calls in CI.
**Commit 06 — Ancy, `feat(web): add claim inspector and verification UI contract`**
- Implement requirements panel, claim list, evidence status, unknown outcomes, run detail tabs; use live API when available.
- Tests: all three verdict render states, missing event safety, color + accessible labels.
- Exit: users can distinguish agent claims from measured evidence without confusion.

### Day 4 — Thursday Oct 22: sandbox enforcement + proof checks
**Commit 07 — Dhyey, `feat(sandbox): integrate OpenShell policy driver and event capture`**
- Implement adapter local OpenShell with version-checked commands/SDK, create scoped sandbox, apply deny-by-default tested policy at creation, observe policy-deny telemetry, enforce cleanup. Keep `MockSandboxDriver` for CI.
- Tests: integration smoke gated env, policy deny fixture, runtime unavailable => INCONCLUSIVE/ERROR not 'secure'.
- Exit: show actual deny of synthetic `.env.production` read under OpenShell; never store secret content.
**Commit 08 — Ancy, `feat(evidence): implement independent verification UI and certificate explorer`**
- Implement verification results pages and backend certificate rendering/storage integration with Dhyey's verifier contract; if backend verifier incomplete, add frontend/UI tests and agreed contract scaffolding only.
- Tests: result table renders pass/fail/inconclusive, hash check surfaced, JSON export.
- Exit: clear report screen, no hardcoded outcomes.

### Day 5 — Friday Oct 23: independent verification engine + first E2E
**Commit 09 — Dhyey, `feat(verifier): execute pinned checks in isolated verification runtime`**
- Implement independent trusted verifier driver, fixed allowlist check templates, clean workspace snapshot, process timeout and resource caps; fixture login expiry regression.
- Tests: false success claim fails, authorized patch passes, altered restricted path fails, missing artifact inconclusive. End-to-end API test.
- Exit: failure from real command exit codes; no LLM as outcome authority.
**Commit 10 — Ancy, `feat(web): integrate three end-to-end demos and charts`**
- Implement one-click scenario gallery, live trace animation from actual events, before/after claim mismatch visualization, mobile/responsive polish.
- Tests: e2e browser smoke with seeded backend; no autoplay fake logs.
- Exit: judges can click replay for 3 scenarios and see actual state.

### Day 6 — Saturday Oct 24: proof challenges and evidence integrity
**Commit 11 — Dhyey, `feat(challenges): build Nemotron challenge proposer and sandbox validation`**
- Implement constrained test proposal schema, AST validation and repo context limits, verifier-only execution, hard time/resource caps. Certificate manifest and detached hash verification CLI.
- Tests: benign generated test; banned network/import denied; malicious prompt injection text treated as data; modified event chain detected.
- Exit: Challenge button triggers real execution; unknown/unsupported outcomes not promoted to verified.
**Commit 12 — Ancy, `feat(web): implement challenge workflow and downloadable proof certificates`**
- Implement review/execute challenge UI, evidence links, hashes, comparative original vs challenge outcomes; downloadable JSON.
- Tests: page interactions, progress/timeout/error paths, keyboard/accessibility checks.
- Exit: polished main judges' 3-min flow end-to-end.

### Day 7 — Sunday Oct 25: benchmark and freeze
**Commit 13 — Dhyey, `test(bench): add deterministic benchmark harness and harden security`**
- Implement 12-20 seeded test cases including true pass, false success, denied file, attempted network exfil, corrupt log, invalid model JSON, timeout. CLI measures confusion matrix, overhead and model usage; harden runtime.
- Tests: CI all green, 3 consecutive demo runs, artifact integrity, environment secret scan.
- Exit: reproducible benchmark JSON and limitations doc; stop adding core features.
**Commit 14 — Ancy, `docs(demo): finalize accessible UI demo and submission assets`**
- Implement UX polish, benchmark UI wired to real metrics, diagrams, README quick start, Devpost copy draft, concise 3-min video storyboard, screenshots from running app.
- Tests: clean-clone setup, front+back tests, deployed read-only demo smoke.
- Exit: stable release tag `v0.1.0-demo`, signoff from both; new changes only critical fixes.

## Human role matrix
- Dhyey owns API/security/sandbox/model/backend verifier, benchmark runner, infra.
- Ancy owns UX/pages/front contracts, interactive evidence visualizations, demo recording/storytelling, documentation; contributes backend adapters only through agreed tasks.
- Both review every PR, share functional demo testing, confirm security limits and co-author hackathon feedback.

## Commit timing and checkoffs
Do not impose artificial clock times. Handoff occurs only after prior PR merged. If a task spills, reduce scope instead of parallel editing. Each commit must include `docs/PROGRESS_LOG.md` with SHA, exact tests, blockers and next handoff.

## Contingency
If OpenShell cannot run on development host by Day 4: prioritize a real container verifier with explicit warning 'not OpenShell enforced' for development, maintain an OpenShell smoke test on a compatible host, and do not claim blocked event evidence unless collected. If Token Factory credits unavailable: mocked API for development only; hackathon submission requires **at least one live NVIDIA open model on Nebius**. If hosting sandbox risky: publish hosted read-only verified recorded runs plus live model/verification demo on controlled host; label replay.
