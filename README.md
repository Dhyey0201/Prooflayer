# ProofLayer — AI Agent Outcome Verification Studio
**Hackathon:** Nebius × NVIDIA Global AI Hackathon 2026  
**Team:** Dhyey (backend / security / infra lead) and Ancy (frontend / experience / evaluation lead); both contribute across the stack.  
**Track:** Coding and Agentic Engineering.  
**Submission deadline:** October 30, 2026, 10:00 AM MST (Arizona); submit earlier.  
**Implementation sprint:** October 19–25, 2026 (seven days); October 26–29 for polish, deployment, benchmarking and recording.

## Mission
An AI coding agent may claim a task succeeded even though tests fail, a forbidden action was attempted, or compatibility was never checked. ProofLayer collects enforcement evidence and *independently* evaluates explicit postconditions. Its report distinguishes VERIFIED, FAILED, and INCONCLUSIVE claims. It is **not** formal proof of software correctness and does not guarantee containment when actions bypass instrumented controls.

## The product in one sentence
A developer launches a bounded AI coding task, watches its actions in a real sandbox, challenges its completion claim with independently executed tests, and obtains an integrity-linked evidence certificate.

## Golden path demo
1. Open a hosted dashboard, choose the **False Success** fixture, review allowed paths and required checks.
2. Agent modifies sample Python application and says its selected tests passed.
3. Independent verifier runs the *full pinned suite*, finds an expired-token regression and reports FAILED.
4. Nemotron proposes a targeted additional test; a deterministic verifier validates and executes it (never arbitrary LLM shell text directly).
5. Evidence view shows command hashes, exit status, artifact hashes, claim mapping and a certificate JSON export.
6. Also demonstrate a policy-denied attempt to read `.env.production` via OpenShell, and a positive verification case.

## Non-negotiable acceptance
- Every status has a server-side evidence source, never a fabricated UI value.
- One real end-to-end execution path with Nemotron on Nebius Token Factory.
- At least three pre-seeded cases (pass, false success, access denied), replayable locally.
- Failed action and failed task are distinct; attempted policy violation != successful secret read.
- Sandbox verifier is separated from the untrusted agent workspace; no agent access to verifier credentials or audit store.
- README, open-source license at repository root, public repo, live demo URL, <=3min YouTube video, and tool feedback ready.

## Quickstart (backend, mock mode, no cloud keys)
> **Security warning.** This is a hackathon prototype. Mock mode uses deterministic
> test doubles: **no sandbox is enforced and no Nebius call is made**, and
> `/api/v1/capabilities` reports `sandbox_enforced: false`. Never put real credentials
> in fixtures, never commit `.env`, and do not expose the API publicly before write
> operations are authenticated.

Requires Python 3.12+ and `make`.

```bash
git clone https://github.com/Dhyey0201/Prooflayer.git && cd Prooflayer
make install                  # .venv + pinned deps from apps/api/requirements-dev.txt
make lint test check-docs     # ruff check, ruff format --check, pytest -q, handoff check
make seed                     # optional: one queued fixture run per template
make run                      # alembic upgrade head, then API on http://127.0.0.1:8000
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/api/v1/health         # {"status":"ok"}
curl -s http://127.0.0.1:8000/api/v1/capabilities   # boolean flags only
curl -s http://127.0.0.1:8000/api/v1/templates      # trusted fixture registry
curl -s -X POST http://127.0.0.1:8000/api/v1/runs \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-run-0001' \
  -d '{"template_id":"false-success-auth","mode":"fixture"}'
curl -s http://127.0.0.1:8000/api/v1/runs/<id>/events   # hash-chained evidence events
```

A new run is persisted in `queued` state with a hash-chained event log. **No agent,
sandbox or verifier executes it yet** (Commits 05/07/09), so no run reaches a
verdict; `mode: "live"` returns 422 until a live runtime exists.

Optional configuration: `cp .env.example .env` (git-ignored). Setting
`PROOFLAYER_MOCK_MODE=false` requires `NEBIUS_API_KEY`; the API refuses to start otherwise.
Keys are server-side only and are never returned by any endpoint.

Docker alternative: `docker compose up --build` (API on `127.0.0.1:8000`, or set
`API_PORT=8001`; non-root, read-only filesystem, SQLite in a named volume).

## Quickstart (frontend)

Requires Node.js 20+. Run the backend first (above) so the dashboard's
"Backend status" panel has something to call.

```bash
cd apps/web
npm install
npm run dev      # http://localhost:3000; expects the API on :8000 by default
```

`NEXT_PUBLIC_API_BASE_URL` (see `apps/web/.env.example`) is the only
configuration the browser reads; it never sees a Nebius, OpenShell or Tavily
key. The scenario cards, runs list and run detail/trace timeline (`/runs`,
`/runs/[id]`) are wired to the live `GET /templates`, `GET/POST /runs`,
`GET /runs/{id}` and `GET /runs/{id}/events` endpoints — no fixture/sample
data ships in the frontend as of Commit 04. Launching a run creates it in the
backend's `queued` state; no worker advances it yet (that lands in Commits
05/07/09), so it will not reach a verdict in this build — the UI says so
rather than animating fake progress. See `apps/web/README.md` for scripts
(`lint`, `typecheck`, `build`, `test`).

## Repository layout
| Path | Purpose |
|---|---|
| `apps/api` | FastAPI service (`prooflayer_api`), Alembic migrations, Dockerfile |
| `apps/web` | Next.js (App Router) + TypeScript + Tailwind dashboard |
| `packages/contracts` | Python loaders for the canonical contracts |
| `contracts/` | `openapi.yaml`, `schemas.json` (source of truth) |
| `tests/` | pytest suite (API, config, contracts, migrations, repo hygiene) |
| `docs/` | PRD, architecture, plan, evaluation, deployment, demo, progress log |

## Read these files in order
1. `docs/01_PRODUCT_PRD.md` — goals, UX, stories and success criteria.
2. `docs/02_ARCHITECTURE_SECURITY.md` — data flow and trust model.
3. `docs/03_SEVEN_DAY_COMMIT_PLAN.md` — exact ownership and alternating integration protocol.
4. `docs/04_TEST_EVALUATION.md` — benchmark and acceptance.
5. `docs/05_SETUP_COST_DEPLOYMENT.md` — setup, cost limits, deployment.
6. `docs/06_DEMO_SUBMISSION.md` — judged demo, copy and final checklist.
7. `contracts/openapi.yaml`, `contracts/schemas.json` — contract-first interfaces.
8. `docs/PROGRESS_LOG.md` — per-commit evidence and handoff notes.

## Principle: one trunk, one active writer
The initial seven-day plan alternates commits: Dhyey pushes, Ancy pulls and extends, Ancy pushes, Dhyey pulls and extends. For simplicity, use a protected `main` with a single active feature branch at a time and review PRs. **Never both modify the same local unpushed branch simultaneously.** No force-push, no committing credentials.

## Official references
- https://nebius.com/services/token-factory/nemotron
- https://api.tokenfactory.nebius.com/docs
- https://docs.nvidia.com/openshell/latest/get-started/quickstart
- https://docs.nvidia.com/openshell/latest/home
- https://github.com/NVIDIA/OpenShell
