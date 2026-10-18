# Progress log
Human and coding agents append one block per merged commit:

## 20XX-XX-XX — Commit NN — <sha> — <person>
- PR:
- Files/feature:
- Exact commands/tests run + PASS/FAIL:
- Security / model cost:
- Known blockers:
- Confirm next contributor pulled merged main: yes/no

## 2026-10-18 — Commit 01 — SHA: see PR (first commit on `feature/d1-dhyey-repo-foundation`) — Dhyey
- PR: not opened yet. `main` does not exist on the remote (empty repo); a base branch is needed first (awaiting human approval).
- Files/feature:
  - Root: MIT `LICENSE`, `.gitignore` (ignores `.env*` except `.env.example`, DBs, venvs), `.env.example` (mock mode, empty keys), `Makefile`, `docker-compose.yml`, root `pyproject.toml` (Ruff + pytest config), README quickstart + security warning.
  - `apps/api` (`prooflayer_api`): Pydantic settings (`SecretStr` keys; `PROOFLAYER_MOCK_MODE=false` without `NEBIUS_API_KEY` refuses to start), typed enums mirroring the contract (`RunStatus`, `RunMode`, `Verdict`, `TemplateId`, `CheckOutcome`, `ErrorCode`), request-ID middleware (safe pattern or fresh UUID), typed error envelope `{error:{code,message,request_id}}` with a generic 500 that never echoes exception text, CORS limited to configured origins.
  - Routes: `GET /api/v1/health`, `GET /api/v1/capabilities` (boolean flags only), plus unprefixed `GET /health` liveness for containers.
  - DB: SQLAlchemy 2 models for `task_templates`, `runs`, `events`, `artifacts`, `checks`, `certificates`; Alembic migration `0001` (enum CHECK constraints, unique `(run_id, seq)` on events). No CRUD or hash-chain logic yet (Commit 03).
  - `packages/contracts`: read-only loaders for `contracts/openapi.yaml` / `schemas.json`, used by contract tests.
  - `.github/workflows/ci.yml`: Python 3.12, ruff check, ruff format --check, pytest, `scripts/check_docs.py`; read-only permissions, no secrets.
  - `apps/api/Dockerfile`: non-root user; compose runs it read-only with `cap_drop: ALL`.
  - `scripts/check_docs.py`: no longer requires `AGENTS.md`/`CLAUDE.md` (kept local, not committed); now checks LICENSE, schemas and this log.
- Exact commands/tests run + PASS/FAIL (local, macOS, Python 3.12, `.venv`):
  - `ruff check .` → PASS ("All checks passed!")
  - `ruff format --check .` → PASS ("33 files already formatted")
  - `pytest -q` → PASS ("44 passed in 0.49s"). First runs failed and were fixed: Starlette 1.8 TestClient deprecates `httpx` (switched to `httpx2`); Alembic `path_separator` deprecation (added to `alembic.ini`); repo-hygiene test assumed `.env.example` already tracked.
  - `python scripts/check_docs.py` → PASS ("3 seed fixtures")
  - `alembic check` after `upgrade head` → PASS ("No new upgrade operations detected.")
  - Boot with empty environment (`env -i`, no keys) + `uvicorn`: `/api/v1/health` → 200 `{"status":"ok"}` with `x-request-id`; `/api/v1/capabilities` → all `false` except `mock_mode: true`; unknown route → typed 404.
  - `PROOFLAYER_MOCK_MODE=false` without key → startup `ValidationError` ("NEBIUS_API_KEY is required…") as intended.
  - Fresh clone of the branch into a temp dir + new venv: `make install` → OK; `make lint test check-docs` → PASS ("44 passed in 2.99s"); `make run` with empty environment → migration `0001` applied, health/capabilities 200; `git status` clean afterwards (SQLite DB ignored). Clone contained no `.env`, docx or agent-only files.
  - `docker compose config --quiet` → valid. **Docker image build NOT verified** (Docker daemon not running on dev host).
  - GitHub Actions: **not yet run** (needs push).
- Security / model cost: no Nebius or Tavily calls; $0 model spend. Capabilities never return keys, URLs or model IDs (tested with a fake key). `openshell_available`, `sandbox_enforced`, `independent_verifier_available` are hard `false` — nothing is claimed as enforced. Validation errors list field locations only (no input echo). Write endpoints, auth and rate limiting are not implemented yet.
- Contract notes for review: the plan says `/api/v1/config/capabilities`, but `contracts/openapi.yaml` (canonical) says `/capabilities` under server `/api/v1`; implemented the contract path. The contract leaves the capabilities schema open (`type: object`); proposing to pin it to the 7 boolean fields above.
- Known blockers: remote has no `main` branch yet; Docker build unverified; CI unverified until first push.
- Confirm next contributor pulled merged main: no (not merged yet).
- Next handoff (Ancy, Commit 02): after merge, `git switch main && git pull --ff-only origin main`, `make install && make test`, `make run`; build `apps/web` against `GET /api/v1/health` and `GET /api/v1/capabilities` using `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1`. CORS already allows `http://localhost:3000`. `/templates` and `/runs` are not implemented yet (Commit 03); use explicitly labeled sample fixtures for those.

## 2026-10-18 — Commit 02 — SHA: 75d22fd (branch `feature/d2-ancy-web-dashboard-foundation`) — Ancy
- PR: https://github.com/Dhyey0201/Prooflayer/pull/1, opened against `main`. `main` appeared on origin (pointing at Dhyey's Commit 01 SHA `c3a6e7f`) partway through this commit, after the branch note below was first drafted — resolves the blocker from Dhyey's Commit 01 entry.
- Files/feature:
  - `apps/web`: Next.js 16 (App Router, Turbopack) + TypeScript 5 (strict) + Tailwind CSS v4, scaffolded via `create-next-app` then customized — no backend contract changes.
  - Layout: `components/layout/{AppShell,Sidebar,MobileNav,NavLink}.tsx` — accessible sidebar nav (`<nav aria-label="Primary">`, `aria-current="page"`, visible `:focus-visible` ring, skip-to-content link), collapses to a horizontal nav below `md`.
  - Routes: `app/page.tsx` (dashboard: backend status, 3 scenario cards, recent-runs preview) and `app/runs/page.tsx` (full sample runs table) — two real destinations wired into the sidebar.
  - Typed API client: `lib/api/types.ts` mirrors `contracts/openapi.yaml` / `apps/api/prooflayer_api/{enums,routes/system}.py` exactly (health, capabilities, error envelope `{error:{code,message,request_id}}`). `lib/api/client.ts` reads only `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000/api/v1`); never references a Nebius/OpenShell/Tavily key. `lib/api/useSystemStatus.ts` is a client hook with explicit `loading | error | ready` states (no fabricated "ok" on failure) and a retry action.
  - `GET /templates` and `GET /runs` aren't implemented until Commit 03, so `lib/fixtures/{templates,runs}.ts` supply typed, explicitly-flagged (`isSample: true`) placeholder data; every consumer (`ScenarioCard`, `RunsTable`) renders a visible "Sample data — not a live backend result" badge. The "Launch run" button on each scenario card is disabled with an explanatory title, not wired to a fake action.
  - `components/StatusPill.tsx` (`RunStatusPill`, `VerdictPill`) color-codes `RunStatus`/`Verdict` without relying on color alone (text label always present).
  - Tests: `__tests__/apiClient.test.ts` (Vitest) — health/capabilities parsing, typed `ApiRequestError` from the backend's error envelope, and network-failure handling never resolves as success. `__tests__/navigation.test.tsx` — sidebar nav is an accessible, labeled landmark with correct `aria-current`, and is reachable by `Tab` order (keyboard smoke test) via `@testing-library/user-event`.
  - `apps/web/README.md` + root `README.md` "Quickstart (frontend)" section added; `apps/web/.env.example` documents `NEXT_PUBLIC_API_BASE_URL`.
  - `next.config.ts`: `turbopack.root` pinned to `apps/web` (a stray `~/package-lock.json` outside the repo was otherwise confusing Turbopack's root inference) and `agentRules: false` (repo convention keeps `AGENTS.md` local/uncommitted; Next 16 would otherwise regenerate one at the app root on every `dev`/`build`).
- Exact commands/tests run + PASS/FAIL (local, macOS, Node v26.0.0/npm 11.12.1, from `apps/web`):
  - `npm run lint` (`eslint .`) → PASS, no errors (one `react-hooks/set-state-in-effect` error was raised and fixed by moving the loading-state reset into the `refresh` callback instead of the effect body).
  - `npm run typecheck` (`next typegen && tsc --noEmit`) → PASS, no errors.
  - `npm test` (`vitest run`) → PASS — "Test Files 2 passed (2), Tests 6 passed (6)".
  - `npm run build` (`next build`) → PASS — "Compiled successfully", routes `/`, `/_not-found`, `/runs` all prerendered static; no warnings.
  - Backend/frontend integration smoke (backend run on a scratch port to avoid an unrelated process already bound to :8000 on the dev host; frontend then run on the real default `:3000` so the CORS check is representative of `http://localhost:3000`): `GET /api/v1/health` → `{"status":"ok"}`, `GET /api/v1/capabilities` → all `false` except `mock_mode: true`, both rendered correctly server-side (`curl` on `/` and `/runs` → 200, panel text and sample-data badges present in the HTML). Live in-browser client-fetch execution was **not** visually verified — no browser automation tool was available in this session; coverage instead comes from the Vitest fetch-mock tests exercising the exact same `lib/api/client.ts` code path, plus the direct `curl` checks above against the real backend at the exact URL embedded in the rendered HTML.
  - `grep` over `.next` build output for `NEBIUS_API_KEY`/`TAVILY_API_KEY` → no matches; only `NEXT_PUBLIC_API_BASE_URL` is referenced from client code.
  - Backend baseline re-verified untouched: `make lint test check-docs` → PASS ("44 passed"), no `apps/api`, `packages/contracts`, `contracts/`, or `tests/` files modified.
- Security / model cost: no Nebius/OpenShell/Tavily call from the frontend, $0 model spend. No secret or key is read by any `apps/web` source file (only `NEXT_PUBLIC_API_BASE_URL`). `npm audit` reports 5 high-severity advisories, all transitive dev-only lint tooling (`eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`, a stack-exhaustion DoS in a glob matcher used only by ESLint, never shipped to the browser bundle or server runtime); the only fix available downgrades `eslint-config-next` to `14.2.35`, which would mismatch Next 16 lint rules, so left as a known, low-risk, dev-only item for Dhyey/human review rather than silently downgraded.
- Known blockers: none new. Docker image build for `apps/web` not attempted (no Dockerfile requested for this commit; `apps/api`'s container is unaffected). In-browser client-side fetch not visually verified (see above).
- Confirm next contributor pulled merged main: no (awaiting Dhyey's review/merge of PR #1).
- Next handoff (Dhyey, Commit 03): after merge, `git fetch origin && git switch main && git pull --ff-only origin main`. Implement run create/read/list, fixture registry and the SQLite-backed `events` hash chain per the plan; once `/templates` and `/runs` are real, the frontend fixture adapters in `lib/fixtures/` are intentionally the only files that need to change to swap in live data — `RunsTable`/`ScenarioCard` already accept typed `Run`/`ScenarioTemplate` props.
