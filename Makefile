PYTHON ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install lint format test check-docs migrate run ci clean

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

run: migrate ## Run the API locally on :8000 (mock mode by default)
	cd apps/api && ../../$(BIN)/uvicorn prooflayer_api.main:app --host 127.0.0.1 --port 8000 --reload

ci: lint test check-docs ## Everything CI runs

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
