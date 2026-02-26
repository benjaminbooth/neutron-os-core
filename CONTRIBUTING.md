# Contributing to Neutron OS

**Sections:**
- [Development Setup](#development-setup)
- [Branching & Merge Requests](#branching--merge-requests)
- [Installing Dev Builds](#installing-dev-builds)
- [Code Conventions](#code-conventions)
- [Documentation](#documentation)
- [CI/CD Pipeline](#cicd-pipeline)
- [GitLab Settings (Maintainers)](#gitlab-settings-maintainers)
- [Runner Setup](#runner-setup)

## Development Setup

### Quick Start

```bash
git clone https://rsicc-gitlab.tacc.utexas.edu/neutron-os/neutron-os-core.git
cd Neutron_OS
./scripts/bootstrap.sh
```

This creates a venv, installs the package in editable mode, and sets up direnv
if available. After bootstrap, `neut --help` should work.

### Manual Setup

```bash
cd /path/to/UT_Computational_NE
python3 -m venv .venv
source .venv/bin/activate
cd Neutron_OS
pip install -e ".[all]"
neut --help
```

### Agent & Facility Config (Optional)

If you're running `neut sense` or `neut chat`, copy the example configs:

```bash
cp -r tools/agents/config.example/ tools/agents/config/
# Edit tools/agents/config/facility.toml and models.toml for your facility
```

See [CLAUDE.md](CLAUDE.md) for detailed setup and troubleshooting.

## Branching & Merge Requests

### Branch Naming

Use prefixed branch names:

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code restructuring (no behavior change) |
| `ci/` | CI/CD pipeline changes |
| `test/` | Test additions or fixes |

Examples: `feat/experiment-scheduler`, `fix/voice-ingest-timeout`, `docs/api-reference`

### Workflow

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature main
   ```
2. Make changes and commit with clear messages
3. Push and open a merge request into `main`:
   ```bash
   git push -u origin feat/my-feature
   ```
4. MR triggers CI — tests, lint, and a downloadable wheel artifact
5. Get review, address feedback
6. **Squash and merge** — each MR becomes one commit on `main`

### MR Checklist

Before requesting review, verify:

- [ ] Tests pass locally: `make test`
- [ ] Lint is clean: `make lint`
- [ ] MR description explains the **why**, not just the what
- [ ] New features have tests
- [ ] No secrets or credentials in committed files

### No `develop` Branch

We use `main` as the sole integration branch. Feature branches are short-lived.
Tagged releases (e.g., `v0.1.0`) cut directly from `main`.

## Installing Dev Builds

Every merge to `main` publishes a dev build to the GitLab Package Registry.
Teammates can install the latest without cloning the repo:

```bash
pip install neutron-os --upgrade \
  --index-url https://rsicc-gitlab.tacc.utexas.edu/api/v4/projects/<PROJECT_ID>/packages/pypi/simple \
  --trusted-host rsicc-gitlab.tacc.utexas.edu
```

Replace `<PROJECT_ID>` with the GitLab project ID (visible on the project homepage).

Or use the Makefile shortcut (requires `GITLAB_PROJECT_ID` env var):

```bash
export GITLAB_PROJECT_ID=<PROJECT_ID>
make install-preview
```

Dev versions follow [PEP 440](https://peps.python.org/pep-0440/) format:
`0.1.0.dev42` where `42` is the CI pipeline number. `pip install --upgrade`
always fetches the latest.

## Code Conventions

For naming, terminology, and architectural patterns, see [CLAUDE.md](CLAUDE.md).

**Key rules:**
- Use `DataTransformer` not `Transformer` (see terminology standards in CLAUDE.md)
- Use `Provider` not `Plugin` for extension system
- PostgreSQL everywhere, no SQLite (see CLAUDE.md tech stack section)

### Running Tests

```bash
make test           # Unit tests (no credentials needed)
make integration    # Integration tests (needs .env with credentials)
make test-all       # Both
make lint           # Ruff linter
```

### Validating .gitignore

```bash
git check-ignore -v your_file_pattern
```

## Documentation

### Writing Documentation

See [docs/README.md](docs/README.md) for folder structure and conventions:
- **ADR/** — Architecture Decision Records (technical decisions, immutable)
- **PRD/** — Product Requirements (what we're building, user journeys)
- **specs/** — Technical Specifications (how to build it)

### Publishing Documentation

See [PUBLISHER_USAGE.md](PUBLISHER_USAGE.md) for publishing to OneDrive.
First-time publishers: start with [PUBLISH_CHECKLIST.md](PUBLISH_CHECKLIST.md).

### Generated Outputs

- Generated Word docs go to `docs/_tools/generated/` (not alongside source markdown)
- Mermaid diagrams for Word export: see CLAUDE.md Mermaid Diagrams section

## CI/CD Pipeline

The pipeline runs automatically on GitLab. Here's what happens at each trigger:

| Trigger | What runs |
|---------|-----------|
| Push to any branch | Unit tests + lint |
| MR opened/updated | Unit tests + lint + integration tests + build wheel (downloadable artifact) |
| Merge to `main` | All tests + build + **publish dev build** to Package Registry |
| Tag `v*` pushed | All tests + build + **publish stable release** to Package Registry |

### Creating a Release

```bash
# Ensure pyproject.toml has the correct version
# Then tag and push:
git tag v0.1.0
git push origin v0.1.0
```

The CI pipeline builds and publishes the release to the GitLab Package Registry.

## GitLab Settings (Maintainers)

These must be configured in the GitLab UI — they can't be set via code:

1. **Settings > Repository > Protected Branches**
   - Protect `main`
   - Allowed to push: **Maintainers only**
   - Allowed to merge: **Maintainers only** (or Developers, depending on team size)

2. **Settings > Merge Requests**
   - Squash commits: **Encourage** or **Require**
   - Merge checks: **Pipelines must succeed**

3. **Settings > CI/CD > Variables** (masked, protected):
   - `GITLAB_TOKEN` — Personal access token
   - `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_TENANT_ID` — Azure AD

## Runner Setup

If TACC GitLab has no shared runners, register a project-specific shell runner:

```bash
# Install
brew install gitlab-runner   # macOS
# or: sudo apt install gitlab-runner  # Linux

# Register (get token from Settings → CI/CD → Runners → New project runner)
gitlab-runner register \
  --url https://rsicc-gitlab.tacc.utexas.edu \
  --token <RUNNER_TOKEN> \
  --executor shell \
  --description "neutron-os-dev"

# Start
gitlab-runner run
```

Or use `make runner-register` for a guided walkthrough.

## Standards & References

**Project Standards:**
- [CLAUDE.md](CLAUDE.md) — Terminology, tech stack, project memory
- [docs/README.md](docs/README.md) — Documentation structure & conventions
