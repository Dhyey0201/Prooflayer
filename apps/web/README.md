# ProofLayer — Web dashboard

Next.js (App Router) + TypeScript + Tailwind CSS v4 frontend. Talks to the
FastAPI backend (`apps/api`) only through the typed client in
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
| `npm run typecheck` | `next typegen && tsc --noEmit` |
| `npm test` | Vitest: API client contract tests, run-detail polling, event trace, keyboard-nav smoke test |

## What's here

- `app/` — dashboard (`/`), runs list (`/runs`) and run detail/trace timeline
  (`/runs/[id]`) routes, shared `AppShell` layout (accessible sidebar + mobile
  nav, skip link, focus-visible rings).
- `lib/api/` — typed client (`client.ts`) for every live endpoint
  (`health`, `capabilities`, `templates`, `runs` create/list/get,
  `runs/{id}/events`, `runs/{id}/cancel`), mirroring `contracts/openapi.yaml`
  exactly, plus hooks built on a shared `useAsyncResource` loading/error/ready
  state machine: `useSystemStatus`, `useTemplates`, `useRuns`, `useRunDetail`
  (polls the run + its events, stopping once the run reaches a terminal
  status), `useCreateRun` (one fresh `Idempotency-Key` per launch click).
- `components/dashboard/` — `ScenarioCard` (with an expandable policy
  preview: allowed/read-denied paths, required checks, policy version) and
  `LaunchRunButton`, `SystemStatusPanel`, `RunsTable`.
- `components/runs/` — `RunDetailView` (status/verdict pills, cancel action,
  a visible "fixture mode, no verdict yet" notice) and `EventTrace` (the
  event list + detail drawer: select an event to see its full safe payload
  and hash-chain fields).
- No fixture/sample data ships here — every page reads live backend state
  and shows an explicit loading or error state when it can't.

## Not yet implemented

The verification/claim-inspector UI and the evidence certificate explorer
follow in later commits per `docs/03_SEVEN_DAY_COMMIT_PLAN.md`. Launched
runs sit in `queued` state and never reach a verdict in this build — no
worker advances them yet (Commits 05/07/09).
