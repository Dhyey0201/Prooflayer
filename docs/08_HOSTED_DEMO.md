# 08 — Hosted demo (read-only replay)

The hosted demo serves **recorded** runs read-only. It does not run agents. The
agent sandbox cannot be enforced on hosted infrastructure without an OpenShell
host (`docs/07`), and the write endpoints are unauthenticated, so docs/03's
fallback applies: "publish hosted read-only verified recorded runs … label replay".

## What is in it
- `demo/prooflayer-demo.db`: a byte-for-byte snapshot of the reference
  database. It holds 8 runs:
  - **Live:** 3 Nemotron runs on Nebius, verified by the real Docker
    verifier, with their proof challenges (the same runs as
    `benchmarks/live/`).
  - **Scripted:** 5 runs, also checked by the real verifier, with scripted
    challenges. The false-success run is FAILED/CONTRADICTED; the secret-read
    attempt fails the forbidden-access check.
- `demo/evidence-ledger.jsonl`: the detached ledger entries for those runs.
- `benchmarks/results/benchmark-report.json`, served by `GET /benchmark`.

Every certificate re-verifies against the hosted API:

```bash
cd apps/api && ../../.venv/bin/python -m prooflayer_api.evidence.verify_cli \
  --api https://<api-host>/api/v1 --run <run-id> --ledger ../../demo/evidence-ledger.jsonl
```

## How it is locked down
- `PROOFLAYER_READ_ONLY=true`: every non-GET request gets the typed
  `403 read_only` before routing, and no worker starts. Capabilities report
  `read_only: true`, and the web app shows a "Replay" banner.
- `PROOFLAYER_ENV=production`, mock mode, `VERIFIER_DRIVER=disabled`. The
  image has no Nebius key: it never calls a model or Docker.
- The build context is an allow-list (`.dockerignore`), so `.env`, local
  databases and `node_modules` cannot enter the image.
- Non-root user (UID 10001). The image copies the snapshot to `/app/data` at
  start and never writes the originals.

## Preview locally
```bash
docker build -f demo/Dockerfile -t prooflayer-demo .
docker run --rm -p 127.0.0.1:8010:8000 \
  -e PROOFLAYER_CORS_ORIGINS='["http://localhost:3000"]' \
  --read-only --tmpfs /tmp --tmpfs /app/data:uid=10001,gid=10001 \
  --cap-drop ALL --security-opt no-new-privileges:true prooflayer-demo
cd apps/web && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api/v1 npm run dev
```

## Deploy (needs the owner's hosting accounts)
Any host that runs a Dockerfile works for the API, and any Next.js host works
for the web app. One free combination:

1. **API on Render** (Web Service, Docker):
   - Repository: this repo. Dockerfile path: `demo/Dockerfile`. Docker context: `.`
   - Health check path: `/health`. Render sets `PORT`, and the image listens on it.
   - Environment: `PROOFLAYER_CORS_ORIGINS=["https://<your-web-host>"]`. Add nothing else; the image sets the rest.
   - After deploy: `curl https://<api-host>/api/v1/capabilities` must show `"read_only":true`.
2. **Web on Vercel**:
   - Import the repo with Root Directory `apps/web` (framework: Next.js).
   - Environment: `NEXT_PUBLIC_API_BASE_URL=https://<api-host>/api/v1`. It is bundled into the browser; never put a credential there.
3. Put the web URL in `PROOFLAYER_CORS_ORIGINS` on Render, then redeploy.
4. Open the web URL in a fresh browser:
   - The Replay banner is visible.
   - The Runs page lists 8 runs, and `/benchmark` shows the measured numbers.
   - Launching a run shows the `read_only` error.

Free hosting tiers may sleep when idle. Open the API URL a minute before
judging or recording.

## Regenerating the snapshot
Only from a real local run: Docker verifier up, then
`PROOFLAYER_ALLOW_UNENFORCED_LIVE=true` with a key for live runs. Copy
`data/prooflayer.db` with SQLite's backup API (not `cp` while the API is
running), copy `data/evidence-ledger.jsonl`, then:
- re-run the secret scan with the key exported;
- confirm `verify_cli` passes for every run.

Never hand-edit the snapshot: any edit breaks its hash chains, and
`verify_cli` will (correctly) report it.
