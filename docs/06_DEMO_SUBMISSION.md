# 06 — Demo, judging story, Devpost and release checklist
## 3-minute filmed demonstration storyboard
0:00–0:18: State problem: an AI agent's completion message is not proof. Introduce 'Claim → Challenge → Evidence'.
0:18–0:38: Open dashboard and choose seeded auth-dependency task. Show constraints and required tests. Nebius/Nemotron model badge links to actual recorded inference metadata.
0:38–1:05: Start real controlled run, show agent's claimed completion and independent trace; avoid waiting by showing a recorded run explicitly labeled 'replay' if execution > video time.
1:05–1:33: Show genuine OpenShell-denied fake secret-read fixture. Show denial evidence; never call it secret theft.
1:33–2:06: Show independent full suite failing despite agent claim. Open failing test and exit code.
2:06–2:32: Click 'Challenge claim': Nemotron proposes a focused regression case and sandbox verifier actually executes it. Display generated test hash and result.
2:32–2:50: Open machine-readable proof certificate; compare verified / failed / inconclusive statements and integrity chain.
2:50–3:00: Tech + impact: Nemotron through Nebius Token Factory, OpenShell isolation, independent verifier; highlight measured benchmark (only if actually measured).

## Concrete shot list (mapped to the current app, as of Commit 14)
The storyboard above is the timing; this is which actual screen to be on for each beat. Record against a backend running the real verifier (`VERIFIER_DRIVER=docker`, `make verifier-image` built) — without Docker every check reports INCONCLUSIVE, which is honest but not the most illustrative demo.
1. **Dashboard** (`/`) — the three scenario cards. Expand a card's "Review policy preview" to show allowed/read-denied paths and required checks before launching.
2. Launch **false-success-auth**. Land on `/runs/{id}`, **Event trace** tab selected by default — point out the live-polling status pill and the one-shot highlight on a row that just arrived.
3. Switch to the **Claim inspector** tab once the run reaches a verdict: the claim-vs-evidence banner (CONTRADICTED, if Docker is running and the suite really fails) sitting next to the per-check evidence status.
4. Launch **denied-secret-read**; in its **Event trace**, select the `policy.denied` event and show the detail drawer's full payload and hash-chain fields (`previous_hash`/`event_hash`) — label it an *attempt*, never a disclosure.
5. Back on the false-success run, open the **Certificate** tab: verdict, the failing check's reason/exit code, the manifest's verifier identity (driver/isolation/network/image), both hashes (`evidence_manifest_sha256` and the `X-Certificate-SHA256` response header), and the "Download JSON" button.
6. Switch to **Challenges**, click "Request challenge", wait for it to complete, and show the proposed test's source (rendered as code) and its measured outcome against the original certificate check.
7. Close on the **Benchmark** page (`/benchmark`) — if Commit 13 has merged by recording time, show the real numbers; if not, the honest "no benchmark results yet" state is itself a fair thing to show on-camera (it's the same principle the whole product is built on).

## Screenshots to capture
Landing screen, new-run task+policy, real timeline with denied event, check detail with failing test, challenge evidence, certificate export and benchmark summary. NEVER Photoshop fabricated logs or numbers.

**Status as of this doc's last update**: not yet captured — needs a human with a browser (and ideally a running Docker-backed verifier) to click through the flow above and save real screenshots. `docs/PROGRESS_LOG.md` notes this as an open item each time it's touched; don't let it slip to the last day.

## Sample Devpost description outline
- Inspiration/problem: existing autonomous agent claims not authoritative.
- What it does: policy-bound run, independent tests, claim-vs-evidence mapping, proof certificate.
- How built: NVIDIA Nemotron, Nebius Token Factory, NVIDIA OpenShell, FastAPI/Next.js, deterministic verifier, optional Tavily.
- Challenges: separate trusted verifier from untrusted agent; secure generated-test execution; honest unknown status.
- Accomplishments: quantified seed benchmark, repeatable denial + false-claim detection, end-to-end clickable demo.
- Learned: model structured outputs, sandbox policies, limitations of software evidence.
- What's next: GitHub PR checks, workflow agents, remote attestation, multiple runtimes.

## Submission checklist
[ ] Pick Coding and Agentic Engineering track.
[ ] Public GitHub/GitLab repo, root MIT/Apache-2.0 license visible.
[ ] Complete README with commands, architecture, env guide and limitations.
[ ] Working hosted application URL/test build (required for this track).
[ ] Public YouTube video <=3 minutes.
[ ] Clear mention NVIDIA open model ID and proof of execution via Nebius Token Factory.
[ ] Feedback on Nebius Token Factory/AI Cloud and NVIDIA tools, honest pros and limitations.
[ ] If reusing pre-hackathon project, explicitly detail significant work done during submission window.
[ ] Verify credit/spend balance; remove secrets from history, artifacts and screenshots.
[ ] Verify video links, repo visibility, license and demo in fresh browser.
[ ] Both team members added to project appropriately.
[ ] Submit before October 30 10:00 AM Arizona time; do not rely on last-minute uptime.

## Honest known limitations
OpenShell enforcement is separate from ProofLayer; our added value is task outcome checking. Tests cannot prove absence of every bug. The chain proves internal consistency, not security against someone who controls both events and detached manifest. Independent verifier must be independently provisioned. Model-generated tests are useful but themselves require a secure runner and a clear definition of expected outcome.
