# 02 — Technical architecture, trust model and interfaces
## Components
- **Web** (Next.js): demo control surface. Uses backend REST + polling/SSE; never holds inference credentials.
- **API** (FastAPI): auth for write operations, validates fixture IDs and run settings; starts only allowlisted tasks.
- **Orchestrator**: state machine, queue (in-process + SQLite initially), concurrency=1 or 2; worker timeout and cleanup.
- **Agent adapter**: produces typed tool requests and claims. Nemotron model makes bounded proposals, no arbitrary shell command from model exposed to host.
- **OpenShell driver**: provisions agent environment, applies restrictive policy before launching agent, captures observed denies; CLI/SDK version pinned after smoke test. For CI, deterministic mock driver.
- **Verifier driver**: launches *separate*, independently provisioned environment with clean snapshot; executes only pinned test commands and validated generated tests; agent cannot access verifier files.
- **Nemotron adapter**: OpenAI-compatible API with timeout, retries on retryable codes, structured parsing, circuit breaker, request budget.
- **Evidence service**: write-once logical events, append sequence and previous digest; snapshots diff and command results. A detached digest/manifest is required to detect attacker modification of entire storage.
- **Certificate generator**: evaluate each requirement deterministically; never allow LLM to set verdict; export machine-readable report.
- **Optional Tavily adapter**: explicit use for external citations, provenance, bounded API calls, disabled by default.

## Trust boundaries
A. Browser/untrusted HTTP -> authenticated API validates fixture ID and hard limits.  
B. Orchestrator -> agent sandbox with minimal filesystem/network/process permissions.  
C. Agent sandbox -> mediated tools only; can't reach host socket, verifier workspace, evidence DB, secrets.  
D. Agent claims -> untrusted evidence inputs; independently verified before conclusion.  
E. Verifier -> separate trusted code/image and read-only tested snapshot.  
F. Third-party model/Tavily -> untrusted suggestions/reference content; never execute unvalidated instruction text.

## Precise policy semantics
- `allowed_paths` governs *actual file changes* (verified from snapshot). Distinct `read_denied_paths` must be **enforced by runtime**, not a regex applied to messages.
- Filesystem restrictions may require sandbox creation-time policies; do not assume policy hot reload applies to all controls.
- A denied access attempt is recorded with enforcement metadata; don't claim the agent read the data.
- Default deny external network egress except exactly required model API endpoints; no arbitrary Internet access in agent sandbox.
- Make test runner non-root, without docker socket, host bind mounts, SSH keys or production tokens. Supply no real credentials to fixture.

## Status state machine
`created -> queued -> provisioning -> running -> verifying -> {verified,failed,inconclusive}`. Cancellation allowed from active states -> `canceled`. Setup failures -> `error`. State transitions recorded as events, idempotent with optimistic lock/sequence.

## Verification algorithm (simplified)
1. Load task spec from trusted fixture registry and pinned repo commit/hash.
2. Snapshot source tree and requirements, start agent with hard constraints.
3. Stream sanctioned tool events, agent claims, and actual enforcement events.
4. Agent exits; preserve immutable-ish agent output snapshot and metadata.
5. Rebuild fresh verifier container from pinned image; copy diff/artifacts as allowed; no agent access.
6. Execute trusted required test list with timeout, capture exit code; calculate hash of test output. Check allowed modified files against initial snapshot.
7. If Proof Challenge enabled, Nemotron produces JSON containing `challenge_type`, `target`, `test_source`, `rationale`; validator requires Python AST parse, length cap, named test entrypoint, banned import checks; **AST checks alone are not a security boundary**. Execute only inside sandbox with read-only fixture + resource limits.
8. Map requirements to actual measurements. If evidence missing -> INCONCLUSIVE. If violation/test failure -> FAILED. All required checks passed -> VERIFIED **for enumerated requirements only**.
9. Append normalized certificate, hash event chain, export report with limitations and provenance.

## Data model
`task_templates(id,title,repo_sha,allowed_paths_json,required_checks_json,policy_version)`
`runs(id,task_id,status,model_id,started_at,finished_at,agent_claim,policy_version,worktree_digest,error_code)`
`events(run_id,seq,time,type,actor,payload_json,prev_hash,event_hash)`
`artifacts(id,run_id,type,content_sha256,location,size_bytes,created_at)`
`checks(id,run_id,requirement_id,kind,outcome,evidence_ref,command_template_id,exit_code)`
`certificates(id,run_id,schema_version,verdict,json_sha256,created_at,manifest_sha256)`

## Security threats and defenses
| Threat | Mitigation | Residual risk |
|---|---|---|
| Prompt injection from repo/tool output | Treat as data; fixed system rules and action schemas | Model may still propose unsafe steps; validator must stop execution |
| Data exfiltration | No true secrets in fixtures; denied file/network access | Sandbox misconfig/escape remains possible |
| Model-generated malicious test | Schema and static validation + isolated verifier sandbox | Sandbox escape/resource exhaustion |
| Faked 'tests passed' | Independently run pinned tests | Uncovered behavior remains unknown |
| Agent modifies verifier | Separate images, workspaces and identities | Host compromise would invalidate trust |
| Audit log tampering | SHA-256 chain, detached manifest hash, separation of writers | A fully compromised signing authority can forge chain |
| Host resource exhaustion | hard budgets, concurrency and timeouts | Unexpected container engine issue |
| Public arbitrary code execution | No arbitrary URL/repo/code submissions in hosted demo | Future generalization requires stronger multitenancy |

## Model requirements
- Primary configurable: `nvidia/nemotron-3-super-120b-a12b` per Nebius published quickstart; confirm with authenticated `GET /v1/models` before assuming account access.
- Optional: Nano tier for extraction and Ultra for difficult analysis. Store model IDs as environment values rather than hard-code guessed names.
- Chat completions through env `NEBIUS_BASE_URL` default `https://api.tokenfactory.us-central1.nebius.com/v1/`, API key server-side only.
- Model output: Pydantic/JSON schema strict validation; retry invalid JSON once, otherwise INCONCLUSIVE and log parser failure.

## Example run verification decision
`if any(check=FAILED or policy_violation_confirmed): FAILED; elif every required check has PASS and evidence chain valid: VERIFIED; else: INCONCLUSIVE`. Treat attempted policy violation according to whether task policy explicitly requires zero attempted forbidden operations; distinguish BLOCKED and DENIED from ACTUAL unauthorized access.
