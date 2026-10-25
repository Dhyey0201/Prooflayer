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
| `npm test` | Vitest: API client contract tests, run-detail polling, event trace, claim inspector, certificate explorer, tabs keyboard nav |

## What's here

- `app/` — dashboard (`/`), runs list (`/runs`) and run detail (`/runs/[id]`)
  routes, shared `AppShell` layout (accessible sidebar + mobile nav, skip
  link, focus-visible rings).
- `lib/api/` — typed client (`client.ts`) for every live endpoint
  (`health`, `capabilities`, `templates`, `runs` create/list/get,
  `runs/{id}/events`, `runs/{id}/cancel`, `runs/{id}/certificate`), mirroring
  `contracts/openapi.yaml` exactly, plus hooks built on a shared
  `useAsyncResource` loading/error/ready state machine: `useSystemStatus`,
  `useTemplates`, `useRuns`, `useRunDetail` (polls the run + its events,
  stopping once the run reaches a terminal status), `useCreateRun` (one
  fresh `Idempotency-Key` per launch click), `useCertificate` (treats a 404
  as an explicit "not ready" state, not an error).
- `components/dashboard/` — `ScenarioCard` (with an expandable policy
  preview: allowed/read-denied paths, required checks, policy version) and
  `LaunchRunButton`, `SystemStatusPanel`, `RunsTable`.
- `components/runs/` — `RunDetailView` (status/verdict pills, cancel action)
  with three tabs (`Tabs.tsx`, accessible: click or arrow keys):
  - **Event trace** (`EventTrace`) — the event list + detail drawer: select
    an event to see its full safe payload and hash-chain fields.
  - **Claim inspector** (`ClaimInspector`) — the template's requirements
    (reuses `PolicyPreview`), the agent's claim labeled explicitly untrusted
    (with its hash and length, never promoted to evidence), and an evidence
    status row per required check. Every check reads INCONCLUSIVE until the
    independent verifier exists (Commit 09) — real measured signals (e.g. the
    count of observed `policy.denied` attempts) are shown alongside it, never
    used to upgrade the outcome.
  - **Certificate** (`CertificateExplorer`) — calls the real
    `GET /runs/{id}/certificate`; since no run has one yet, every run shows
    "No certificate yet" (the contract's documented 404 case) rather than a
    fabricated result. Once Commit 09 ships a certificate, this renders its
    verdict, claims/checks (outcome pills), evidence manifest hash and a
    "Download JSON" export with no frontend changes needed.
- No fixture/sample data ships here — every page reads live backend state
  and shows an explicit loading, "not ready", or error state when it can't.
