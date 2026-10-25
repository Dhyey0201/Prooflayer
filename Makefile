PYTHON ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install lint format test check-docs migrate seed run ci clean sandbox-image policy live-smoke \
	verifier-image verifier-test verify-certificate

install: ## Create venv and install pinned dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r apps/api/requirements-dev.txt

lint: ## Ruff lint + format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Apply Ruff fixes and formatting
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test: ## Run the test suite (no cloud keys needed)
	$(BIN)/pytest -q

check-docs: ## Validate the handoff package
	$(BIN)/python scripts/check_docs.py

migrate: ## Apply database migrations to DATABASE_URL
	cd apps/api && ../../$(BIN)/alembic upgrade head

seed: migrate ## Seed fixture templates and one queued fixture run per template
	cd apps/api && ../../$(BIN)/python -m prooflayer_api.seed --with-runs

run: migrate ## Run the API locally on :8000 (mock mode by default)
	cd apps/api && ../../$(BIN)/uvicorn prooflayer_api.main:app --host 127.0.0.1 --port 8000 --reload

ci: lint test check-docs ## Everything CI runs

FIXTURES := success-validation false-success-auth denied-secret-read
SANDBOX_IMAGE ?= prooflayer-workspace
SANDBOX_TAG ?= 0.1.0

sandbox-image: ## Build the OpenShell agent workspace image for each fixture (needs Docker)
	for f in $(FIXTURES); do \
		docker build -f infra/sandbox/workspace.Dockerfile --build-arg FIXTURE=$$f \
			-t $(SANDBOX_IMAGE)-$$f:$(SANDBOX_TAG) apps/api/prooflayer_api/fixture_workspaces || exit 1; \
	done

policy: ## Print the generated OpenShell policy for FIXTURE (default denied-secret-read)
	cd apps/api && ../../$(BIN)/python -m prooflayer_api.sandbox.policy $(or $(FIXTURE),denied-secret-read)

VERIFIER_IMAGE ?= prooflayer-verifier:0.1.0

verifier-image: ## Build the independent verifier image (needs Docker)
	docker build -f infra/verifier/verifier.Dockerfile -t $(VERIFIER_IMAGE) infra/verifier

verifier-test: ## Real-container verifier tests (needs Docker + verifier-image)
	RUN_DOCKER_VERIFIER=1 $(BIN)/pytest -q -rs tests/test_docker_verifier.py

verify-certificate: ## Check RUN=<id>'s certificate against the API and the detached ledger
	cd apps/api && ../../$(BIN)/python -m prooflayer_api.evidence.verify_cli \
		--api http://127.0.0.1:8000/api/v1 --run $(RUN) --ledger data/evidence-ledger.jsonl

live-smoke: ## Opt-in live Nebius + OpenShell checks (uses credits; never in CI)
	RUN_LIVE_INTEGRATION=1 $(BIN)/pytest -q -rs tests/test_live_integration.py

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
