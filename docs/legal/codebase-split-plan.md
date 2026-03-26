# Codebase Split Plan: neutron-os → axiom + neutron-os

> **Status:** Ready to Execute  
> **Last Updated:** 2026-03-25

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          GITHUB                                  │
│  ┌─────────────────────┐       ┌─────────────────────────────┐  │
│  │  benboooth/axiom    │       │ UT-Computational-NE/        │  │
│  │  (PUBLIC)           │       │ neutron-os (PUBLIC)         │  │
│  │                     │       │                             │  │
│  │  Source of truth    │       │  Mirror from GitLab         │  │
│  └──────────┬──────────┘       └──────────────▲──────────────┘  │
│             │                                  │                  │
│             │ pull                             │ push             │
│             ▼                                  │                  │
├─────────────────────────────────────────────────────────────────┤
│                       TACC GITLAB                                │
│  ┌─────────────────────┐       ┌─────────────────────────────┐  │
│  │  rsicc-gitlab/      │       │ rsicc-gitlab/               │  │
│  │  axiom (mirror)     │       │ neutron-os-core (PRIVATE)   │  │
│  │                     │       │                             │  │
│  │  Pulls from GitHub  │       │  Source of truth            │  │
│  └─────────────────────┘       └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Dependency: neutron-os imports axiom (pip install from GitHub)
```

---

## File Inventory

### AXIOM Repository (~180 files)

All generic infrastructure with no nuclear references:

```
axiom/
├── src/axiom/
│   ├── __init__.py
│   ├── cli.py                    # renamed from neut_cli.py
│   ├── cli_registry.py
│   ├── infra/
│   │   ├── audit_log.py
│   │   ├── auth/
│   │   ├── cli_format.py
│   │   ├── config_loader.py
│   │   ├── connections.py
│   │   ├── gateway.py            # remove "mcnp" example in comment
│   │   ├── git.py
│   │   ├── hash_utils.py
│   │   ├── log_sinks.py
│   │   ├── neut_logging.py → logging.py
│   │   ├── nudges.py             # remove "triga-tools" example
│   │   ├── orchestrator/
│   │   ├── prompt_registry.py
│   │   ├── provider_base.py
│   │   ├── publication_registry.py
│   │   ├── raci.py
│   │   ├── rate_limiter.py
│   │   ├── retry.py
│   │   ├── router.py             # EXTRACT nuclear prompt → config
│   │   ├── routing_audit.py
│   │   ├── security_log.py
│   │   ├── self_heal.py
│   │   ├── services.py
│   │   ├── state.py              # parameterize docstrings
│   │   ├── state_pg.py
│   │   ├── subscribers/
│   │   ├── time_utils.py
│   │   ├── toml_compat.py
│   │   └── trace.py
│   ├── extensions/
│   │   ├── cli.py
│   │   ├── contracts.py
│   │   ├── discovery.py
│   │   ├── scaffold.py           # REPLACE reactor examples
│   │   └── builtins/             # ALL 20+ agents
│   ├── rag/                      # ALL files
│   ├── review/                   # ALL files
│   └── setup/                    # ALL files
├── tests/                        # generic tests only
├── infra/
│   ├── db/schema.sql
│   ├── systemd/
│   └── terraform/modules/
├── runtime/config.example/
│   ├── llm-providers.toml
│   ├── settings.toml
│   ├── logging.toml
│   └── models.toml               # generic version
├── pyproject.toml                # name = "axiom"
├── Dockerfile
├── Makefile
└── README.md
```

### NEUTRON-OS Repository (~15 nuclear-specific files)

```
neutron-os/
├── src/neutron_os/
│   ├── __init__.py
│   ├── config/
│   │   ├── export_control_terms.txt
│   │   ├── router_prompt.toml    # nuclear classifier prompt
│   │   └── facility_defaults.toml
│   ├── data/
│   │   ├── dbt/
│   │   │   ├── dbt_project.yml
│   │   │   └── models/
│   │   │       ├── reactor_hourly_agg.sql
│   │   │       └── reactor_timeseries_clean.sql
│   │   └── iceberg/schemas/
│   │       └── reactor_hourly_metrics.avsc
│   └── extensions/
│       └── reactor_scaffold.py   # reactor_logs, reactor_query
├── tests/
│   ├── test_scaffold.py
│   └── test_export_control.py
├── infra/
│   ├── helm/charts/neutron-os/
│   │   ├── Chart.yaml
│   │   └── values-rascal.yaml
│   └── terraform/environments/rascal/
├── runtime/config.example/
│   ├── facility.toml             # reactor = "triga"
│   └── export_control_terms.txt
├── docs/
│   ├── glossary-neutronos.toml
│   └── requirements/             # nuclear-specific PRDs
├── pyproject.toml                # depends on axiom
└── README.md
```

---

## Migration Steps

### Phase 1: Prepare Current Repo (In-Place Refactoring)

Before splitting, clean up files that have nuclear content embedded in generic code:

| File | Change |
|------|--------|
| `infra/router.py` | Extract nuclear classifier prompt to `_nuclear_classifier_prompt.toml`, load from config |
| `infra/gateway.py` | Change `"mcnp"` comment → `"domain-tag"` |
| `infra/nudges.py` | Change `"triga-tools"` → `"example-tools"` |
| `infra/state.py` | Parameterize "Reactor Ops Log" in docstring |
| `extensions/scaffold.py` | Extract reactor examples to separate file |

### Phase 2: Create axiom Repository

```bash
# Create new repo on GitHub
gh repo create benboooth/axiom --public --description "Generic LLM/RAG platform framework"

# Clone current repo to temp location
git clone --mirror git@github.com:UT-Computational-NE/neutron-os-core.git temp-axiom

# Use git-filter-repo to keep only generic files
cd temp-axiom
git filter-repo --paths-from-file axiom-paths.txt

# Rename package: neutron_os → axiom
find . -name "*.py" -exec sed -i '' 's/neutron_os/axiom/g' {} +
find . -name "*.toml" -exec sed -i '' 's/neutron-os/axiom/g' {} +

# Push to new repo
git remote set-url origin git@github.com:benboooth/axiom.git
git push --mirror
```

### Phase 3: Update neutron-os Repository

```bash
# In neutron-os-core on GitLab
cd neutron-os-core

# Remove files that moved to axiom
git rm -r src/neutron_os/infra/*.py  # except keep config files
git rm -r src/neutron_os/rag/
git rm -r src/neutron_os/review/
git rm -r src/neutron_os/setup/
git rm -r src/neutron_os/extensions/builtins/

# Keep nuclear-specific files
# (already in correct location)

# Update pyproject.toml to depend on axiom
```

### Phase 4: Configure Mirroring

#### axiom: GitHub → GitLab (GitLab pulls)

On TACC GitLab, create `rsicc-gitlab/axiom`:

1. Project Settings → Repository → Mirroring repositories
2. Add: `https://github.com/benboooth/axiom.git`
3. Direction: **Pull**
4. Authentication: None (public repo)
5. Only mirror protected branches: No
6. Schedule: Every hour or on-demand

#### neutron-os: GitLab → GitHub (existing setup)

Already configured. Verify:
1. rsicc-gitlab/neutron-os-core pushes to
2. github.com/UT-Computational-NE/neutron-os

---

## pyproject.toml Templates

### axiom/pyproject.toml

```toml
[project]
name = "axiom"
version = "0.1.0"
description = "Generic LLM/RAG platform framework"
readme = "README.md"
license = "MIT"
authors = [{ name = "Benjamin Booth", email = "..." }]
requires-python = ">=3.11"

dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
    "rich>=13.0",
    "typer>=0.12",
    "structlog>=24.0",
    "pgvector>=0.2",
    "psycopg[binary]>=3.1",
    "tomli>=2.0",
    "openai>=1.0",
    "anthropic>=0.25",
]

[project.scripts]
axiom = "axiom.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### neutron-os/pyproject.toml

```toml
[project]
name = "neutron-os"
version = "0.1.0"
description = "Nuclear facility digital operations platform"
readme = "README.md"
license = "MIT"
authors = [{ name = "Benjamin Booth", email = "..." }]
requires-python = ">=3.11"

dependencies = [
    "axiom @ git+https://github.com/benboooth/axiom.git",
    # OR after PyPI release:
    # "axiom>=0.1.0",
]

[project.scripts]
neut = "neutron_os.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Files Requiring Manual Refactoring

### 1. router.py — Extract Nuclear Prompt

**Before:**
```python
NUCLEAR_CLASSIFIER_PROMPT = """
You are classifying queries for nuclear facility sensitivity...
Keywords: MCNP, SCALE, HEU, LEU, 10 CFR 810...
"""
```

**After (axiom):**
```python
def load_classifier_prompt(config_path: Path | None = None) -> str:
    """Load domain-specific classifier prompt from config."""
    if config_path and config_path.exists():
        return config_path.read_text()
    return DEFAULT_GENERIC_PROMPT
```

**After (neutron-os):**
```toml
# config/router_prompt.toml
[classifier]
prompt = """
You are classifying queries for nuclear facility sensitivity...
"""
```

### 2. scaffold.py — Extract Reactor Examples

**Before:**
```python
EXAMPLE_TOOLS = {
    "reactor_logs": "Query reactor operations logs...",
    "reactor_query": "Execute reactor data queries...",
}
```

**After (axiom):**
```python
EXAMPLE_TOOLS = {
    "data_logs": "Query operations logs...",
    "data_query": "Execute data queries...",
}
```

**After (neutron-os):**
```python
from axiom.extensions.scaffold import register_example

register_example("reactor_logs", "Query reactor operations logs...")
register_example("reactor_query", "Execute reactor data queries...")
```

---

## Verification Checklist

After split, verify:

- [ ] `pip install axiom` works from GitHub
- [ ] `pip install neutron-os` works and imports axiom
- [ ] `axiom --help` shows generic CLI
- [ ] `neut --help` shows nuclear CLI with axiom extensions
- [ ] No nuclear keywords in axiom repo: `grep -r "TRIGA\|MCNP\|reactor" axiom/`
- [ ] GitLab mirror of axiom syncs successfully
- [ ] GitHub mirror of neutron-os syncs successfully
- [ ] All tests pass in both repos

---

## Timeline Estimate

| Task | Duration |
|------|----------|
| Phase 1: In-place refactoring | 2-4 hours |
| Phase 2: Create axiom repo | 1 hour |
| Phase 3: Update neutron-os | 1 hour |
| Phase 4: Configure mirroring | 30 min |
| Verification & fixes | 2-4 hours |
| **Total** | **1-2 days** |

---

## Next Steps

1. **Run refactoring script** (created separately)
2. **Create axiom repo on GitHub**
3. **Execute git-filter-repo extraction**
4. **Update neutron-os dependencies**
5. **Configure GitLab mirroring**
6. **Update disclosure guide with actual URLs/line counts**
7. **Send intro email to Discovery to Impact**
