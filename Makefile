# Makefile for mcp-financial-data. Tab-indented (POSIX make).
# All targets prefer `uv run` so the .venv is the single source of truth.

UV ?= uv
PY ?= $(UV) run python
PKG := mcp_financial_data

.DEFAULT_GOAL := help

.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make \033[36m<target>\033[0m\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: setup
setup: ## Sync deps (and install pre-commit hooks if this is a git repo)
	$(UV) sync --all-extras
	@if [ -d .git ]; then \
		echo "==> installing pre-commit hooks"; \
		$(UV) run pre-commit install; \
	else \
		echo "==> skipping pre-commit install (no .git/ yet -- run 'make hooks' after 'git init')"; \
	fi

.PHONY: hooks
hooks: ## Install pre-commit git hooks (run after `git init`)
	@if [ ! -d .git ]; then \
		echo "ERROR: not a git repo yet. Run 'git init' first." >&2; \
		exit 1; \
	fi
	$(UV) run pre-commit install

.PHONY: lint
lint: ## Ruff lint + format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

.PHONY: fmt
fmt: ## Ruff auto-format
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

.PHONY: typecheck
typecheck: ## Mypy strict on src/
	$(UV) run mypy --strict src

.PHONY: test
test: ## Run unit tests with coverage gate
	$(UV) run pytest --cov=src --cov-report=term-missing --cov-fail-under=85

.PHONY: test-int
test-int: ## Run integration tests (real network; needs .env)
	$(UV) run pytest -m integration

.PHONY: eval-smoke
eval-smoke: ## Run smoke eval (offline, 1 case, writes JSONL)
	$(UV) run python -m $(PKG).evals.harness --smoke --offline

.PHONY: eval
eval: ## Run full eval (offline by default; set EVAL_OFFLINE=0 for live)
	$(UV) run python -m $(PKG).evals.harness --full

.PHONY: serve
serve: ## Run the MCP server locally (streamable HTTP, port from env)
	$(UV) run python -m $(PKG).server

.PHONY: oauth-dev
oauth-dev: ## Print a dev OAuth 2.1 token for local CLI testing
	$(UV) run python -m $(PKG).auth.oauth dev-token

.PHONY: ui-build
ui-build: ## Build TenKSummaryCard JS bundle (requires npm + public registry)
	@if [ ! -f ui/tenk-summary-card/package.json ]; then \
		echo "ERROR: ui/tenk-summary-card workspace missing" >&2; exit 1; \
	fi
	cd ui/tenk-summary-card && npm ci && npm run build

.PHONY: ci
ci: lint typecheck test eval-smoke ## Mirror what CI runs

.PHONY: clean
clean: ## Remove caches, builds, eval runs (keeps lock file)
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find evals/runs -mindepth 1 ! -name .gitkeep -exec rm -rf {} +
