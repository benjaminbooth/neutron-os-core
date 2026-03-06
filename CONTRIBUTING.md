# Contributing to Neutron OS

This guide covers the mechanics of contributing — setup, branching, testing,
and releasing. For project architecture, terminology, and AI assistant context,
see [CLAUDE.md](CLAUDE.md).

## Development Setup

### Quick Start

```bash
git clone https://rsicc-gitlab.tacc.utexas.edu/neutron-os/neutron-os-core.git
cd Neutron_OS
./scripts/bootstrap.sh
```

This creates a venv, installs in editable mode, and configures direnv.
After bootstrap, `neut --help` should work.

### Manual Setup

```bash
cd /path/to/UT_Computational_NE
python3 -m venv .venv
source .venv/bin/activate
cd Neutron_OS
pip install -e ".[all]"
neut --help
```

### Facility Config (Optional)

If you're running `neut sense` or `neut chat`, copy the example configs:

```bash
cp -r runtime/config.example/ runtime/config/
# Edit runtime/config/facility.toml and models.toml for your facility
```

### AI Tool Setup

```bash
cp -r .claude.example/ .claude/
# Add your API keys and personal context to .claude/
```

## Everything Is an Extension

New functionality goes into extensions, not scattered across the repo.
Before writing code, decide:

| What I'm building | Where it goes |
|---|---|
| Domain-agnostic CLI feature | `src/neutron_os/extensions/builtins/{name}/` |
| Domain-specific feature (reactor-ops, isotopes) | External repo → `.neut/extensions/` |
| Shared platform plumbing (auth, gateway) | `src/neutron_os/infra/` |

Every extension needs a `neut-extension.toml` manifest. Use `neut ext init` to
scaffold one, or copy from an existing builtin. Agent extensions must have
directory names ending with `_agent`.

See [CLAUDE.md](CLAUDE.md) for the full "Where Does New Code Go?" table.

## Testing

### Running Tests

```bash
# All tests (unit + colocated extension tests)
make test

# Verbose with traceback
pytest tests/ src/neutron_os/extensions/builtins/ -v --tb=short

# Single extension
pytest src/neutron_os/extensions/builtins/sense_agent/tests/ -v

# Unit tests only (no credentials needed)
pytest -m "not integration"

# Lint
make lint
```

### Test Organization

- **Extension tests** live colocated in `src/neutron_os/extensions/builtins/{ext}/tests/`
- **Cross-cutting tests** (framework, integration, e2e) live in `tests/`
- **Repo hygiene checks** in `tests/test_repo_hygiene.py` catch stale imports,
  misplaced files, and naming violations — these run on every `make test`

### Writing Tests

- Extension tests go in the extension's `tests/` directory, not root `tests/`
- Shared fixtures are in `tests/conftest.py` (available everywhere via root `conftest.py`)
- Mark tests needing credentials with `@pytest.mark.integration`
- Mark tests needing network with `@pytest.mark.skipif` or similar guards

## Branching & Merge Requests

### Branch Naming

| Prefix | Use for |
|--------|---------|
| `feat/` | New features or extensions |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code restructuring (no behavior change) |
| `ci/` | CI/CD pipeline changes |
| `test/` | Test additions or fixes |

### Workflow

1. Branch from `main`:
   ```bash
   git checkout -b feat/my-feature main
   ```
2. Make changes, commit with clear messages
3. Push and open a merge request:
   ```bash
   git push -u origin feat/my-feature
   ```
4. MR triggers CI — tests, lint, wheel artifact
5. Get review, address feedback
6. **Squash and merge** — each MR becomes one commit on `main`

### MR Checklist

- [ ] Tests pass locally: `make test`
- [ ] Lint is clean: `make lint`
- [ ] MR description explains the **why**, not just the what
- [ ] New features have tests (colocated with the extension)
- [ ] No secrets or credentials in committed files
- [ ] No new root-level directories without approval

### No `develop` Branch

We use `main` as the sole integration branch. Feature branches are short-lived.
Tagged releases cut directly from `main`.

## Code Conventions

For terminology, tech stack, and architecture, see [CLAUDE.md](CLAUDE.md).

**Key rules:**
- `Provider`, not `Plugin` — everything is an extension with providers
- `DataTransformer`, not `Transformer` — avoids ML collision
- PostgreSQL everywhere, no SQLite
- Mermaid diagrams only, no ASCII art

## CI/CD Pipeline

| Trigger | What runs |
|---------|-----------|
| Push to any branch | Unit tests + lint |
| MR opened/updated | Unit tests + lint + build wheel (downloadable artifact) |
| Merge to `main` | All tests + build + publish dev build to Package Registry |
| Tag `v*` pushed | All tests + build + publish stable release |

### Creating a Release

```bash
# Bump version in pyproject.toml, then:
git tag v0.3.1
git push origin v0.3.1
```

CI builds and publishes to the GitLab Package Registry.

### Installing Dev Builds

```bash
pip install neutron-os --upgrade \
  --index-url https://rsicc-gitlab.tacc.utexas.edu/api/v4/projects/<PROJECT_ID>/packages/pypi/simple \
  --trusted-host rsicc-gitlab.tacc.utexas.edu
```

Dev versions follow PEP 440: `0.3.1.dev42` where `42` is the CI pipeline number.

## Documentation

- **ADR/** — Architecture Decision Records (immutable once merged)
- **PRD/** — Product Requirements (what we're building)
- **specs/** — Technical Specifications (how to build it)

Extension-specific docs live in the extension: `src/neutron_os/extensions/builtins/{ext}/docs/`.
Cross-cutting docs go in `docs/`. See [docs/README.md](docs/README.md).

## GitLab Settings (Maintainers)

1. **Settings > Repository > Protected Branches**
   - Protect `main`, push = Maintainers only

2. **Settings > Merge Requests**
   - Squash commits: Encourage or Require
   - Merge checks: Pipelines must succeed

3. **Settings > CI/CD > Variables** (masked, protected):
   - `GITLAB_TOKEN`
   - `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_TENANT_ID`

## Runner Setup

If TACC GitLab has no shared runners:

```bash
brew install gitlab-runner   # macOS
gitlab-runner register \
  --url https://rsicc-gitlab.tacc.utexas.edu \
  --token <RUNNER_TOKEN> \
  --executor shell \
  --description "neutron-os-dev"
gitlab-runner run
```
