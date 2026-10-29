# Devpost submission draft

Draft copy for the Devpost entry, following the outline in
`docs/06_DEMO_SUBMISSION.md`. Treat every bracketed `[...]` as a placeholder
that needs a real value (demo URL, video link, credits) before submission —
nothing else here is a placeholder; it describes what's actually built as of
this draft. Re-check against `docs/PROGRESS_LOG.md` before submitting, since
the last two implementation days (benchmark harness, hardening) may still be
in flight.

## Inspiration

An AI coding agent's own "done" message isn't proof. We've all seen an agent
report a task complete while a test silently failed, a forbidden file was
touched, or a claim was just optimistic. ProofLayer exists to stop taking an
agent's word for it: a bounded run, a sandbox that's separate from the
checker, and a verdict that comes only from measurement.

## What it does

A developer opens a dashboard, picks one of three seeded scenarios (a clean
fix, a false-success claim, and a denied secret-read attempt), and launches
it. A worker runs a Nemotron-driven agent in a policy-scoped sandbox (OpenShell
where the host kernel supports it; otherwise a mock that says so) while every
step — actions, tool results, policy denials — is written to an append-only,
hash-chained event log. When the agent finishes, an **independent verifier**
— a separate container with no access to the agent's sandbox or credentials
— reruns the pinned test suite against a rebuilt, pinned workspace and grades
each requirement from the measurement alone. The agent's own claim ("tests
passed") is recorded as untrusted input and compared against that
measurement (`SUPPORTED`/`CONTRADICTED`/`UNVERIFIED`) — it never sets the
verdict. The result is an evidence certificate: a verdict, the per-check
measurements, and a manifest binding it all to the event chain, downloadable
as JSON. From there, a user can request a **proof challenge** — the model
proposes one additional pytest test, it's statically validated, and only the
verifier (never the agent) executes it against the recorded workspace.

## How we built it

- **Backend**: FastAPI + SQLAlchemy/SQLite, a bounded agent loop talking to
  NVIDIA Nemotron over the Nebius Token Factory (OpenAI-compatible API,
  typed action schema, no raw shell access for the model), an OpenShell
  sandbox driver (with a deterministic mock for CI) for the agent side, and
  a from-scratch independent verifier running pinned pytest suites inside
  network-less Docker containers with dropped capabilities and a non-root
  user — a different isolation boundary and a different trust domain from
  the agent's own sandbox.
- **Evidence**: every state change is an event in a per-run SHA-256 hash
  chain; certificates carry a manifest digest also written to a detached
  ledger file, checkable offline with a small CLI.
- **Frontend**: Next.js App Router + TypeScript + Tailwind, a typed REST
  client against the OpenAPI contract, polling (never fake/looping
  animation) for live run state, and a run-detail view with four tabs —
  event trace, claim-vs-evidence inspector, certificate explorer, and the
  challenge workflow.
- **Process**: a strict contract-first, alternating-commit workflow between
  two contributors (`docs/03_SEVEN_DAY_COMMIT_PLAN.md`) with a per-commit
  progress log recording exact commands and test output — no commit claims
  a result it didn't actually run.

## Challenges we ran into

- Keeping the untrusted agent and the trusted verifier genuinely separate —
  different containers, different credentials, the agent workspace rebuilt
  from a pinned baseline before the verifier ever sees it — rather than
  just trusting the agent's own test run.
- Deciding what "the agent attempted a forbidden read" should mean when the
  agent sandbox itself is a deterministic mock (no real OpenShell on every
  dev machine): the certificate says explicitly when enforcement wasn't
  real, rather than claiming a denial it can't back up. We installed OpenShell
  0.1.5 and reached its gateway, but Docker Desktop's Linux kernel has no
  Landlock, so OpenShell (correctly) refused every sandbox; real enforcement
  needs a Linux host with Landlock.
- Nemotron 3 Super's reasoning tokens count against the completion limit, and
  it sometimes JSON-escapes code twice; both first showed up as rejected live
  challenges (never executed) and were fixed with tests.
- Running model-proposed code at all without it becoming a code-execution
  hole: AST-level static validation (import allowlist, no `eval`/`exec`,
  no dunder access) is explicitly documented as advisory, not the security
  boundary — the verifier's container isolation is.
- Resisting the temptation to show a number before it was actually
  measured — several UI states (the certificate, the benchmark page)
  intentionally say "not ready" instead of rendering a plausible-looking
  placeholder.

## Accomplishments we're proud of

- A real, end-to-end claim → independent check → certificate → challenge
  pipeline, not a mocked demo of one.
- A product that is explicit about its own epistemic limits: INCONCLUSIVE
  is a first-class, honestly-labeled outcome, not an error state to hide.
- Measured, not estimated (18 seeded scripted cases x 3 passes, real Docker
  verifier, `docs/07_BENCHMARK_LIMITATIONS.md`): verdict accuracy 18/18,
  detection recall 5/6 (the miss, code-level exfiltration, is contained but
  not flagged, and we report it), 0/50 safe operations blocked, 4/4 false
  "tests passed" claims caught, 85/85 post-issue tampering attempts detected,
  identical outcomes across passes. Verification overhead median 1.5 s.
- Live: three runs driven by real `nvidia/nemotron-3-super-120b-a12b` on
  Nebius, independently verified, with certificates anyone can re-check
  offline from `benchmarks/live/`. Nemotron fixed the bug in the scenario
  whose scripted agent lies, so that run is VERIFIED: the verdict follows the
  measurement, not the scenario label.

## What we learned

Getting a model to produce a *strictly* typed, boundedly-scoped action per
step (rather than free-form text or shell commands) does more for safety
than any amount of post-hoc filtering. Sandboxing the agent and sandboxing
the *verifier* are two separate problems with two separate trust models —
conflating them is exactly how a false "verified" slips through. And an
evidence chain is only as honest as the UI built on top of it: it's easy to
accidentally render a hopeful default instead of an explicit "we don't know
yet."

## What's next

GitHub PR/CI integration (verify a PR's own claims before merge), workflow
and multi-step agent coverage beyond the three seeded fixtures, remote
attestation for the verifier's own integrity, and support for other model
providers/runtimes beyond Nemotron.

## Built with

NVIDIA Nemotron, Nebius Token Factory, NVIDIA OpenShell, Docker, FastAPI,
SQLAlchemy, Alembic, Next.js, TypeScript, Tailwind CSS, Vitest, pytest, ruff.

## Try it out

- Hosted demo: `[live demo URL — not deployed as of this draft]`
- Source: https://github.com/Dhyey0201/Prooflayer
- Video: `[YouTube link, <=3 minutes]`
