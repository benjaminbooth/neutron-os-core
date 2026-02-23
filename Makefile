# Neutron OS — Development Makefile
#
# Three tiers:
#   make test          → Unit tests (no credentials needed)
#   make integration   → Live channel tests (needs .env credentials)
#   make test-all      → Both
#
# Setup:
#   make install       → pip install -e .[all]
#   make env           → Copy .env.example to .env

.PHONY: install env test integration test-all lint build clean serve help

# ─── Setup ───────────────────────────────────────────────────────────────────

install:  ## Install neutron-os in editable mode with all extras
	pip install -e ".[all]" && pip install python-gitlab requests ruff

env:  ## Copy .env.example to .env (won't overwrite existing)
	@test -f .env && echo ".env already exists — not overwriting" || cp .env.example .env
	@echo "Edit .env with your credentials, then: source .env"

config:  ## Copy agent config examples to live config
	@test -d tools/agents/config && echo "tools/agents/config/ already exists" || cp -r tools/agents/config.example tools/agents/config
	@echo "Edit tools/agents/config/facility.toml and models.toml"

# ─── Testing ─────────────────────────────────────────────────────────────────

test:  ## Run unit tests (no credentials needed)
	pytest tests/ -v --tb=short -m "not integration"

integration:  ## Run integration tests against live services (needs .env)
	@test -n "$$GITLAB_TOKEN" || (echo "Run: source .env" && exit 1)
	pytest tests/integration/ -v --tb=short -m "integration"

test-all:  ## Run all tests (unit + integration)
	pytest tests/ -v --tb=short

test-gitlab:  ## Test GitLab channel only
	pytest tests/integration/test_gitlab_channel.py -v --tb=short

test-onedrive:  ## Test OneDrive channel only
	pytest tests/integration/test_onedrive_channel.py -v --tb=short

test-teams:  ## Test Teams channel only
	pytest tests/integration/test_teams_channel.py -v --tb=short

test-voice:  ## Test voice/serve channel only
	pytest tests/integration/test_voice_channel.py -v --tb=short

# ─── Development ─────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	ruff check tools/ --select E,F,W --ignore E501

serve:  ## Start the inbox ingestion server on port 8765
	neut sense serve --port 8765

status:  ## Show sense pipeline status
	neut sense status

# ─── Build & Distribution ────────────────────────────────────────────────────

build:  ## Build wheel and sdist
	pip install build && python -m build

clean:  ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .pip-cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ─── GitLab Runner ───────────────────────────────────────────────────────────

runner-register:  ## Register a GitLab CI runner (interactive)
	@echo "Register a shell runner for TACC GitLab:"
	@echo ""
	@echo "  1. Go to: https://rsicc-gitlab.tacc.utexas.edu/<your-project>/-/settings/ci_cd"
	@echo "  2. Expand 'Runners' → click 'New project runner'"
	@echo "  3. Copy the runner token"
	@echo "  4. Run:"
	@echo ""
	@echo "     gitlab-runner register \\"
	@echo "       --url https://rsicc-gitlab.tacc.utexas.edu \\"
	@echo "       --token <RUNNER_TOKEN> \\"
	@echo "       --executor shell \\"
	@echo "       --description \"neutron-os-dev\""
	@echo ""
	@echo "  5. Start the runner:"
	@echo ""
	@echo "     gitlab-runner run"
	@echo ""
	@echo "Install gitlab-runner: brew install gitlab-runner (macOS)"

# ─── Help ────────────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
