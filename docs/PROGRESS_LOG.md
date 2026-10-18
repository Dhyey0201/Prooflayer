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
