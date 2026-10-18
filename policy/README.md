# OpenShell policy generation instructions
This is NOT a ready-to-use policy schema because actual OpenShell versions evolve. On Day 4:
1. Install pinned OpenShell version and read `openshell --help`, `openshell sandbox create --help`, `openshell policy --help`, and official current policy schema.
2. Create `openshell-policy.yaml` matching **installed version**, with read deny for `/workspace/.env.production` and verifier/evidence directories; minimal writable paths; default denied egress; only necessary model service if runtime requires it; no Docker host socket.
3. Test that policy is active **before** agent begins; capture actual denied event using official observable logs/OCSF.
4. Write automated integration test that fails when blocked read succeeds or telemetry is absent. Do not certify a policy with a mocked log.
5. Do not add unsafe policies to make a broken integration 'work'.
Docs: https://docs.nvidia.com/openshell/latest/home
