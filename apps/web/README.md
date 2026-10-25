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
| `npm test` | Vitest: API client contract tests, run-detail polling, event trace, claim inspector, certificate explorer, challenge workflow, tabs keyboard nav |

## What's here

- `app/` — dashboard (`/`), runs list (`/runs`) and run detail (`/runs/[id]`)
  routes, shared `AppShell` layout (accessible sidebar + mobile nav, skip
  link, focus-visible rings).
- `lib/api/` — typed client (`client.ts`) for every live endpoint
  (`health`, `capabilities`, `templates`, `runs` create/list/get,
  `runs/{id}/events`, `runs/{id}/cancel`, `runs/{id}/certificate`,
  `runs/{id}/challenge(s)`), mirroring `contracts/openapi.yaml` exactly,
  plus hooks: `useSystemStatus`/`useTemplates`/`useRuns` on a shared
  `useAsyncResource` loading/error/ready state machine; `useRunDetail`
  (polls the run + its events, stopping once terminal); `useCreateRun` (one
  fresh `Idempotency-Key` per launch click); `useCertificate` (polls only
  while the run has no verdict yet; a 404 is an explicit "not ready" state,
  not an error — also surfaces the `X-Certificate-SHA256` response header);
  `useChallenges` (polls only while a challenge is queued/running).
- `components/dashboard/` — `ScenarioCard` (with an expandable policy
  preview: allowed/read-denied paths, required checks, policy version) and
  `LaunchRunButton`, `SystemStatusPanel`, `RunsTable`.
- `components/runs/` — `RunDetailView` (status/verdict pills, cancel action,
  a real in-progress notice) with four tabs (`Tabs.tsx`, accessible: click
  or arrow keys, horizontally scrollable on narrow screens):
  - **Event trace** (`EventTrace`) — the event list + detail drawer: select
    an event to see its full safe payload and hash-chain fields. A row that
    just arrived via polling gets a one-shot highlight (`.event-arrived` in
    `globals.css`, respects `prefers-reduced-motion`) — never a looping or
    fake animation, and the initial batch on mount is never flagged.
  - **Claim inspector** (`ClaimInspector`) — the template's requirements
    (reuses `PolicyPreview`), a **before/after claim-vs-evidence comparison**
    (`ClaimVsEvidence`: what the agent said vs. what the verifier measured,
    with the real `SUPPORTED`/`CONTRADICTED`/`UNVERIFIED` status — never
    re-derived client-side), and an evidence-status row per required check
    using the certificate's real per-check outcome once one exists, or an
    explicit PENDING state (not a fabricated INCONCLUSIVE) before it does.
  - **Certificate** (`CertificateExplorer`) — renders the real certificate
    once the independent verifier has graded the run: verdict, claims
    (status pill), checks (outcome pill + reason + measurements), the
    manifest's verifier identity (driver/isolation/network/image) and
    artifact digests, both hashes (the manifest digest in the body and the
    `X-Certificate-SHA256` of the exact response bytes), and a "Download
    JSON" export. Shows "No certificate yet" on the documented 404 rather
    than a fabricated result.
  - **Challenges** (`ChallengeWorkflow`) — requests one proof challenge
    (disabled with an explanatory message until the run is certified or
    while one is already active), polls `GET /runs/{id}/challenges`, and
    renders each one: the untrusted proposed test source as code (never
    HTML), whether static validation rejected it (never executed), the
    measured outcome once run, and a comparison against the original
    certificate's check for the same requirement (agree/disagree).
- No fixture/sample data ships here — every page reads live backend state
  and shows an explicit loading, "not ready", "pending", or error state
  when it can't.
