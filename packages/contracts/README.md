# packages/contracts

Read-only Python loaders for the canonical contracts in [`/contracts`](../../contracts):
`openapi.yaml` (REST API) and `schemas.json` (proof challenge proposal).

The contract files are the source of truth. Backend tests use this package to
check that API enums and routes match the contract (`tests/test_contracts.py`).
Change the contract first, then the code.
