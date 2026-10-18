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

## Screenshots to capture
Landing screen, new-run task+policy, real timeline with denied event, check detail with failing test, challenge evidence, certificate export and benchmark summary. NEVER Photoshop fabricated logs or numbers.

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
