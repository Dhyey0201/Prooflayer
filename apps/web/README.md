# ProofLayer — Web dashboard

Next.js (App Router) + TypeScript + Tailwind CSS v4 frontend (Commit 02). Talks
to the FastAPI backend (`apps/api`) only through the typed client in
`lib/api/client.ts` — never calls Nebius, OpenShell or Tavily directly, and
never holds a cloud credential.

## Setup

```bash
cd apps/web
npm install
cp .env.example .env.local   # optional; defaults to http://127.0.0.1:8000/api/v1
npm run dev                  # http://localhost:3000, expects the API on :8000
```

With the backend running (`make run` from the repo root), the dashboard's
"Backend status" panel calls `GET /api/v1/health` and `GET /api/v1/capabilities`
and renders a loading, error, or live state — never a fabricated "ok".

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Local dev server |
| `npm run build` | Production build (also used as the typecheck/build gate) |
| `npm run lint` | ESLint (`eslint-config-next`) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest: API client contract tests + keyboard-nav smoke test |

## What's here (Commit 02)

- `app/` — dashboard (`/`) and runs (`/runs`) routes, shared `AppShell` layout
  (accessible sidebar + mobile nav, skip link, focus-visible rings).
- `lib/api/` — typed client + hook for `/health` and `/capabilities`, mirroring
  `contracts/openapi.yaml`.
- `lib/fixtures/` — **sample-only** scenario and run data standing in for
  `/templates` and `/runs`, which land in Commit 03. Every component that
  renders fixture data shows a visible "Sample data" badge; nothing here is
  presented as a live backend result.
- `components/` — `ScenarioCard`, `RunsTable`, `StatusPill`, layout shell.

## Not yet implemented

Run creation, the live run list, event timelines, and the verification/
certificate UI follow in later commits per
`docs/03_SEVEN_DAY_COMMIT_PLAN.md`. The "Launch run" button on each scenario
card is intentionally disabled until then.
