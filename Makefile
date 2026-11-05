.DEFAULT_GOAL := help

# Set UV_RUN_ARGS=--no-sync to skip uv's resync check (CI does this after `uv sync --locked`).
UV_RUN := uv run $(UV_RUN_ARGS)

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: install hooks ## First-time setup: install deps and enable the pre-commit hook
	@echo ""
	@echo "✓ Leverage is ready. Run 'uv run lev --help' to start."

.PHONY: install
install: ## Install dependencies (including dev tools)
	uv sync

.PHONY: hooks
hooks: ## Point git at the repo's hooks in .githooks/
	git config core.hooksPath .githooks

# ── Code Quality ──────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff lint
	$(UV_RUN) ruff check .

.PHONY: lint-fix
lint-fix: ## Run ruff lint with auto-fix
	$(UV_RUN) ruff check --fix .

.PHONY: format
format: ## Format all files with ruff
	$(UV_RUN) ruff format .

.PHONY: format-check
format-check: ## Check formatting without writing
	$(UV_RUN) ruff format --check .

.PHONY: typecheck
typecheck: ## Run mypy (strict)
	$(UV_RUN) mypy

.PHONY: test
test: ## Run tests
	$(UV_RUN) pytest

.PHONY: check
check: typecheck lint format-check test agents-check ## Run all checks (typecheck, lint, format, test)

.PHONY: agents-check
agents-check: ## Fail unless AGENTS.md is a symlink to CLAUDE.md
	@test "$$(readlink AGENTS.md)" = CLAUDE.md || \
		{ echo "AGENTS.md must be a symlink to CLAUDE.md (ln -sf CLAUDE.md AGENTS.md)"; exit 1; }

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo "Leverage — DFS lineup and portfolio optimizer"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
