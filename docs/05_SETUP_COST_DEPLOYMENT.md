# 05 — Setup, infrastructure, costs and safe deployment
## Prerequisites
Git, Python 3.12+, Node 20+, Docker/Podman; optional OpenShell CLI and compatible Docker-backed gateway; Nebius Token Factory account/credits. Never assume promotional credits cover GPU compute or serverless. Start with local sandbox, SQLite, mocked models.

## Environment variables (server only)
`NEBIUS_API_KEY=...` (never commit)  
`NEBIUS_BASE_URL=https://api.tokenfactory.us-central1.nebius.com/v1/`  
`NEBIUS_MODEL_PRIMARY=nvidia/nemotron-3-super-120b-a12b` (confirm in live model catalog)  
`NEBIUS_MODEL_FAST=<select from your available catalog>`  
`TAVILY_API_KEY=...` optional  
`DATABASE_URL=sqlite:///./prooflayer.db`  
`SANDBOX_DRIVER=mock|openshell`  
`ENABLE_PUBLIC_EXECUTION=false`  
`RUN_LIVE_INTEGRATION=0`  
`MAX_AGENT_STEPS=8`  
`MAX_MODEL_CALLS_PER_RUN=12`  
`MAX_RUN_DURATION_SECONDS=120`  
`MAX_ACTIVE_RUNS=1`  
`MAX_OUTPUT_BYTES=1000000`  
`MAX_DAILY_INFERENCE_REQUESTS=100`.

## Live model smoke
Use OpenAI Python SDK with base URL above. Before first live request, call `/models` to confirm selected model ID and available access. Nebius site provides example model `nvidia/nemotron-3-super-120b-a12b`; capitalization / deployment may vary. Never expose API key to browser or agent sandbox. Use one short prompt, store model ID and latency only. Disable auto-spend/alerts if provider supports that control.

## OpenShell smoke
Follow exact current NVIDIA docs and use installed `openshell --help` as authority: https://docs.nvidia.com/openshell/latest/get-started/quickstart. CLI versions change; do not hardcode unsupported policy fields. Create sandbox with restrictive policy at creation, test denied synthetic secret path and optional restricted network destination, capture audit event. Filesystem/process restrictions may not be retroactively applied with policy update; reconstruct sandbox where needed.

## Cost budget
- Open-source software/local Docker/Postgres/SQLite/Next.js/FastAPI: $0 licensing (hardware and electricity excluded).
- Nebius Token Factory inference: usage-based; promotional credits may reduce out-of-pocket spend but not universally guaranteed.
- Nebius Serverless Jobs/GPU: potentially charged separately; *optional only* after confirming credits/billing.
- Tavily: free tier may change; enforce a query budget, fallback to local docs.
- Hosting: free-tier UI may be possible; secure public code execution is risky and likely costs compute. Prefer read-only hosted replay + controlled demo environment.
- Set alerts, quotas, maximum per-run tokens, per-day call limit, and disabled optional integrations.

## Proposed local startup (agent should implement)
`make setup` → install backend/web dependencies and create `.env` from example.  
`make dev-api` → backend at localhost:8000.  
`make dev-web` → web at localhost:3000.  
`make seed` → create 3 fixtures.  
`make test` → offline unit/integration.  
`make demo` → run golden path in mock mode, clearly marked.  
`make live-smoke` → explicit live Token Factory/OpenShell test, never part of default CI.

## Public demo deployment
**Safest:** deploy read-only replay frontend/API with anonymized stored real evidence, no guest-submitted source URLs or arbitrary code. Hosted run button shows controlled pre-executed recordings; indicate recorded evidence. To demonstrate real agent call, show video/controlled private dev host, or restricted known fixture with auth/rate-limit and dedicated sandbox host after independent threat review.

## Security checklist
No real secrets; no docker socket inside agent sandbox; no `--privileged`; no unrestricted host mounts; no arbitrary `subprocess` from HTTP; no shell interpolation; no public API keys; no agent write access to verifier/evidence storage; no unbounded logs; no automatically executing generated tests outside sandbox; no real third-party account changes. Ensure cache artifacts and exported bundle do not contain `.env` or credentials.
