# Neutron OS — Development Makefile
#
# Setup:
#   make install       → pip install -e .[all]
#   make env           → Copy .env.example to .env
#
# Testing:
#   make test          → Unit tests (no credentials needed)
#   make test-all      → All tests (unit + integration)

.PHONY: install env config test test-all lint build clean help

# ─── Setup ───────────────────────────────────────────────────────────────────

install:  ## Install neutron-os in editable mode with all extras
	pip install -e ".[all]" && pip install python-gitlab requests ruff

env:  ## Copy .env.example to .env (won't overwrite existing)
	@test -f .env && echo ".env already exists — not overwriting" || cp .env.example .env
	@echo "Edit .env with your credentials, then: source .env"

config:  ## Copy runtime config examples to live config
	@test -d runtime/config && echo "runtime/config/ already exists" || cp -r runtime/config.example runtime/config
	@echo "Edit runtime/config/facility.toml and models.toml"

# ─── Testing ─────────────────────────────────────────────────────────────────

test:  ## Run unit tests (no credentials needed)
	pytest tests/ src/neutron_os/extensions/builtins/ -v --tb=short -m "not integration"

test-all:  ## Run all tests (unit + integration)
	pytest tests/ src/neutron_os/extensions/builtins/ -v --tb=short

# ─── Development ─────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	ruff check src/ --select E,F,W --ignore E501

# ─── Build & Distribution ────────────────────────────────────────────────────

build:  ## Build wheel and sdist
	pip install build && python -m build

clean:  ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .pip-cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ─── Help ────────────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
