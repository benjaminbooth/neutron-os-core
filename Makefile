# Neutron OS — Development Makefile
#
# Setup:
#   make install       Install neutron-os in editable mode
#   make env           Copy .env.example to .env
#
# Development:
#   make check         Run all local gates (lint + test) — mirrors CI
#   make test          Unit tests only
#   make lint          Ruff lint only

.PHONY: install env config check test test-all lint build clean help

# ─── Setup ───────────────────────────────────────────────────────────────────

install:  ## Install neutron-os in editable mode with all extras
	pip install -e ".[all]" && pip install python-gitlab requests ruff pre-commit
	pre-commit install
	@test -f .git/hooks/pre-push || (cp scripts/hooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push && echo "Installed pre-push hook")

env:  ## Copy .env.example to .env (won't overwrite existing)
	@test -f .env && echo ".env already exists — not overwriting" || cp .env.example .env
	@echo "Edit .env with your credentials, then: source .env"

config:  ## Copy runtime config examples to live config
	@test -d runtime/config && echo "runtime/config/ already exists" || cp -r runtime/config.example runtime/config
	@echo "Edit runtime/config/facility.toml and models.toml"

# ─── Quality Gates (ordered fast → slow) ────────────────────────────────────

check: lint test  ## Run all local gates — equivalent to CI test stage

lint:  ## Run ruff linter
	ruff check src/ --select E,F,W --ignore E501

test:  ## Run unit tests (no credentials needed)
	pytest tests/ src/neutron_os/extensions/builtins/ -n auto -v --tb=short -m "not integration"

test-all:  ## Run all tests (unit + integration)
	pytest tests/ src/neutron_os/extensions/builtins/ -n auto -v --tb=short

# ─── Build & Distribution ────────────────────────────────────────────────────

build:  ## Build wheel and sdist
	pip install build && python -m build

clean:  ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .pip-cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ─── Help ────────────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
