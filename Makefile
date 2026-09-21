# JevKit development tasks.
#
#   make setup    first-time setup
#   make check    everything CI runs

PYTHON ?= python
VENV   := .venv
BIN    := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
endif

DASHBOARD := apps/dashboard

.DEFAULT_GOAL := help
.PHONY: help setup install test test-fast lint format typecheck check \
        api dashboard db demo bench clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and install everything
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	cd $(DASHBOARD) && npm install
	@echo "Done. Copy .env.example to .env and add your credentials."

install: ## Reinstall Python dependencies
	$(BIN)/pip install -r requirements-dev.txt

test: ## Run the full test suite
	$(BIN)/pytest

test-fast: ## Skip the slower benchmark tests
	$(BIN)/pytest -m "not benchmark"

lint: ## Lint Python and the dashboard
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	cd $(DASHBOARD) && npm run lint

format: ## Auto-format Python
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

typecheck: ## Type-check Python and the dashboard
	$(BIN)/mypy
	cd $(DASHBOARD) && npm run typecheck

check: lint typecheck test ## Everything CI runs
	cd $(DASHBOARD) && npm run build

api: ## Run the API service with reload
	$(BIN)/uvicorn apps.api.main:app --reload --port 8000

dashboard: ## Run the dashboard dev server
	cd $(DASHBOARD) && npm run dev

db: ## Start Postgres only
	docker compose up -d db

demo: ## Run the support-routing example with no credentials
	$(BIN)/python examples/support-routing/run.py --dry-run

bench: ## Run the support-routing benchmark against the stub provider
	$(BIN)/jevkit bench \
	  --task examples/support-routing/task.json \
	  --dataset examples/support-routing/dataset.jsonl \
	  --dry-run

clean: ## Remove build and cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path "./$(VENV)/*" -exec rm -rf {} +
