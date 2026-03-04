# NeutronOS Monorepo Test Refactoring Plan

**Date**: February 24, 2026  
**Status**: Design Phase (Ready for Execution)  
**Scope**: Test structure consolidation, coverage enforcement, multi-language Bazel readiness

---

## Executive Summary

Refactor NeutronOS to follow **monorepo hygiene best practices** with:
- **Domain-first architecture** respecting language conventions and Bazel expectations
- **Colocated Python tests** with protected conventions (tests/ subdirectories, non-importable)
- **70% coverage enforcement** for Python code; compiled code tested via integration tests
- **Zero-fragmentation**: Consolidate dual docflow tests, loose test files, and split sense tests
- **AI-maintainable documentation**: TEST.md, DIR_INTENTS.md, FIXTURES.md with clear patterns

**Key Outcomes**:
1. All tests discoverable via single `pytest testpaths = ["tests"]`
2. Baseline coverage documented by component
3. Structure ready for future Bazel migration (BUILD files placeholders)
4. Explicit patterns for multi-language (Python, Rust, WASM, TypeScript, C, C++, Fortran)

---

## Current State Analysis

### Test Organization Issues

| Issue | Location | Severity | Impact |
|-------|----------|----------|--------|
| **Dual docflow tests** | `tests/docflow/` (10) + `docs/_tools/docflow/tests/` (4) | 🔴 Critical | Duplication, unclear authority, maintenance burden |
| **Loose test files** | `tools/test_gitlab_tracker_export.py`, `tools/cost_estimation_tool/test_scenarios.py` | 🔴 Critical | Not discovered by standard pytest; inconsistent placement |
| **Split sense tests** | `tools/pipelines/sense/tests/` (2) + `tests/sense/` (13) | 🔴 Critical | Requires dual testpaths config; discovery friction |
| **No conftest hierarchy** | Only 2 conftest files total | 🟡 Medium | Limited fixture isolation by subsuite |
| **No coverage enforcement** | No coverage thresholds in config | 🟡 Medium | No quality gate; hard to track regression |
| **Under-tested modules** | `tests/serve/` (1 file), `tools/pipelines/sense/tests/` (2 files) | 🟡 Medium | Risk areas for bugs |
| **Empty structural dirs** | `packages/`, `services/`, `plugins/` | 🟢 Minor | Confusion about intended modularization |

### Current Test Stats

- **Total test files**: 63
- **Root tests/ directory**: 47 files
  - docflow: 10
  - sense: 13
  - orchestrator: 4
  - chat: 5
  - setup: 6
  - serve: 1
  - integration: 9
  - e2e: 4
- **Tools subdirectories**: 16 files
- **Docs _tools**: 4 files

### Pytest Configuration (Current)

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "tools/pipelines/sense/tests"]
pythonpath = ["."]
markers = [
    "integration",
    "gitlab",
    "onedrive",
    "teams",
    "voice",
    "inbox",
    "slow",
]
```

**Problem**: Two testpaths, inconsistent discovery pattern.

---

## Architecture Decision

### Domain-First + Language-Respecting + Bazel-Ready

**Principle**: Organize by domain (what the code does), respect language conventions (how different languages structure code), maintain Bazel compatibility (how builds are orchestrated).

```
tools/
├── agents/
│   ├── chat/
│   │   ├── src/           (Python source)
│   │   └── tests/         (Python tests) ← colocated
│   ├── orchestrator/
│   │   ├── src/
│   │   └── tests/
│   ├── sense/
│   │   ├── src/
│   │   └── tests/         (moved from tools/pipelines/sense/tests/)
│   ├── sessions/
│   ├── setup/
│   └── inbox/
├── docflow/
│   ├── src/
│   └── tests/             (consolidated: tests/docflow/ → unified here)
├── orchestrator/
├── cost_estimation_tool/
│   ├── src/
│   └── tests/             (moved from tools/cost_estimation_tool/test_scenarios.py)
├── tracker/
│   ├── src/
│   └── tests/             (moved from tools/test_gitlab_tracker_export.py)
├── db/
├── mcp_server/
└── test/                  (TEST UTILITY LIBRARY, not test cases)

tests/                      (only root conftest and integration/shared fixtures)
├── conftest.py
├── sense/
│   ├── conftest.py
│   ├── fixtures/
│   └── test_*.py
├── chat/
│   ├── conftest.py
│   └── test_*.py
├── docflow/
│   ├── conftest.py
│   └── test_*.py
├── orchestrator/
│   ├── conftest.py
│   └── test_*.py
├── integration/
├── e2e/
└── setup/
```

**Rationale**:
- **Colocated tests**: Each tool has `tests/` subdirectory for package-scoped tests
- **Root tests/**: Shared fixtures, integration tests, e2e tests
- **Single testpath**: `testpaths = ["tests"]` discovers everything
- **Conftest hierarchy**: Each subsuite (sense/, chat/, docflow/) has its own conftest for isolated fixtures
- **Bazel-ready**: Future BUILD files map naturally to test discovery rules
- **Multi-language support**: Structure doesn't assume language; compiled code integrates via external binaries or BUILD dependencies

### Multi-Language Considerations

**Current**: Python-dominant with external C/C++/Fortran binaries  
**Future**: Bazel builds for mixed-language domains

**Pattern**:
```
tools/simulator/                     (example domain with compiled code)
├── BUILD                            (Bazel rules)
├── python/
│   ├── wrapper.py
│   └── tests/
│       └── test_wrapper.py
├── cpp/
│   ├── BUILD
│   ├── simulator.cc
│   └── simulator_test.cc
└── README.md                        (documents language breakdown)
```

For now: Document that compiled code is tested via integration tests calling binaries; future Bazel migration will formalize this.

---

## Refactoring Plan (12 Steps)

### Step 0: DocFlow → Sense Consolidation (Prerequisite)

**Status**: Planning Complete  
**Priority**: Execute before test refactoring  
**Architecture Decision**: DocFlow is a Sense capability, not a separate module

#### Principle

- **ONE RAG**: Sense (`signal_rag.py` + `pgvector_store.py`)
- **ONE embedding store**: PostgreSQL + pgvector
- **ONE agent**: Sense with multiple providers/skills
- DocFlow's diagram analysis → Sense provider

#### Discovery

Elaborate DocFlow system (~7,300 lines) in `docs/_tools/docflow/` duplicates Sense functionality. Salvage only:
1. Terraform/Helm infrastructure patterns (valuable)
2. Diagram analysis capability (unique)

#### What to Salvage vs Discard

| Component | Action | Rationale |
|-----------|--------|-----------|
| `deploy/terraform/modules/` | **SALVAGE** → `infra/terraform/modules/` | Real infrastructure value |
| `deploy/helm/docflow/` | **SALVAGE** → `infra/helm/charts/neutron-os/` | Adapt for unified chart |
| `src/docflow/diagrams/` | **SALVAGE** → `tools/pipelines/sense/providers/diagrams/` | Unique Sense capability |
| `src/docflow/embedding/` | **DISCARD** | Duplicates Sense embedding |
| `src/docflow/rag/` | **DISCARD** | Duplicates Sense RAG |
| `src/docflow/agent/` | **DISCARD** | Duplicates Sense agent |
| `tests/` | **CONSOLIDATE** | Merge diagram tests to `tests/sense/` |

#### Consolidation Tasks

##### 0.1 Extract Infrastructure
```
docs/_tools/docflow/deploy/terraform/modules/ → infra/terraform/modules/
docs/_tools/docflow/deploy/helm/docflow/      → infra/helm/charts/neutron-os/ (adapted)
```

##### 0.2 Merge Diagram Provider into Sense
```
docs/_tools/docflow/src/docflow/diagrams/ → tools/pipelines/sense/providers/diagrams/
```

Update Sense to register diagram provider for:
- Mermaid parsing
- Diagram relationship extraction
- Documentation graph analysis

##### 0.3 Consolidate Tests
```
docs/_tools/docflow/tests/test_diagrams*.py → tests/sense/test_diagram_provider.py
```

##### 0.4 Delete Duplicate Code
```
rm -rf docs/_tools/docflow/  # After extraction complete
```

#### Verification

- [ ] `infra/terraform/modules/` contains working modules
- [ ] `helm template infra/helm/charts/neutron-os/` renders valid YAML
- [ ] Sense can analyze Mermaid diagrams via diagram provider
- [ ] `pytest tests/sense/test_diagram_provider.py` passes
- [ ] No `docs/_tools/docflow/` directory exists
- [ ] No duplicate RAG/embedding code in codebase

**Reference**: [SESSION_2026-02-24_docflow_consolidation.md](../.neut/SESSION_2026-02-24_docflow_consolidation.md)

---

### Step 1: Consolidate Docflow Tests
- **Action**: Merge `docs/_tools/docflow/tests/` into `tests/docflow/`
- **Verification**:
  - [ ] Compare 4 docs files vs 10 root files; identify duplicates
  - [ ] Merge unique tests; update imports
  - [ ] Run: `pytest tests/docflow/ -v`
  - [ ] Delete `docs/_tools/docflow/tests/`

**Files affected**:
- `tests/docflow/` (add/merge)
- `docs/_tools/docflow/tests/` (delete)

---

### Step 2: Move Loose Test Files to Colocated Structure
- **Action**: Reorganize stray test files into proper tool directories
- **Changes**:
  1. `tools/test_gitlab_tracker_export.py` → `tools/tracker/tests/test_gitlab_tracker_export.py`
  2. `tools/cost_estimation_tool/test_scenarios.py` → `tools/cost_estimation_tool/tests/test_scenarios.py`
  3. Create `tools/test/__init__.py` (mark as non-importable)
  4. Create `tools/test/README.md` (clarify this is a test utility library)

**Files affected**:
- `tools/tracker/` (create tests/ subdirectory)
- `tools/cost_estimation_tool/` (move test file)
- `tools/test/README.md` (add)
- `tools/test/__init__.py` (add)

---

### Step 3: Unify Sense Test Location
- **Action**: Merge `tools/pipelines/sense/tests/` into root `tests/sense/`
- **Files to move**:
  - `tools/pipelines/sense/tests/test_bootstrap.py` → `tests/sense/test_bootstrap.py`
  - `tools/pipelines/sense/tests/test_correction_errors.py` → `tests/sense/test_correction_errors.py`
- **Delete**: `tools/pipelines/sense/tests/` directory

**Files affected**:
- `tests/sense/` (add 2 files)
- `tools/pipelines/sense/tests/` (delete)

---

### Step 4: Create Conftest Hierarchy
- **Root conftest** ([tests/conftest.py](tests/conftest.py)): repo_root, tmp_config, docflow_config, sample_gitlab_export, gitlab_token (from integration)
- **Sense conftest** (new [tests/sense/conftest.py](tests/sense/conftest.py)): audio_fixture, voice test data
- **Chat conftest** (new [tests/chat/conftest.py](tests/chat/conftest.py)): chat-specific mocks
- **Orchestrator conftest** (new [tests/orchestrator/conftest.py](tests/orchestrator/conftest.py)): orchestrator isolation

**Action**:
- Extract integration-specific fixtures from `tests/conftest.py` → move to `tests/integration/conftest.py`
- Create 3 new conftest files in sense/, chat/, orchestrator/
- Add docstrings explaining fixture scope and usage

**Files affected**:
- `tests/conftest.py` (refactor, remove integration-specific)
- `tests/integration/conftest.py` (add integration-specific fixtures)
- `tests/sense/conftest.py` (create)
- `tests/chat/conftest.py` (create)
- `tests/orchestrator/conftest.py` (create)

---

### Step 5: Restructure Top-Level Directories (Optional)
- **Decision**: Keep `tools/` as primary; document intent of `packages/`, `services/`, `plugins/`
- **Action**:
  - Add `BUILD` placeholder files to key domains (for future Bazel migration)
  - Update [DIR_INTENTS.md](DIR_INTENTS.md) documenting each directory's purpose
  - Do NOT delete unused dirs; instead document that they're reserved for future expansion

**Files affected**:
- `packages/BUILD` (create)
- `services/BUILD` (create)
- `plugins/BUILD` (create)
- `DIR_INTENTS.md` (update)

---

### Step 6: Update Pytest Configuration
- **File**: [pyproject.toml](pyproject.toml)
- **Changes**:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]  # ← Single path, not ["tests", "tools/pipelines/sense/tests"]
  pythonpath = ["."]
  addopts = "--cov=tools --cov-report=term-missing --cov-report=html --cov-fail-under=70"
  markers = [
      "integration",
      "gitlab",
      "onedrive",
      "teams",
      "voice",
      "inbox",
      "slow",
  ]
  
  [tool.coverage.run]
  source = ["tools"]
  omit = [
      "*/tests/*",
      "*/test_*.py",
      "*/__pycache__/*",
  ]
  
  [tool.coverage.report]
  exclude_lines = [
      "pragma: no cover",
      "def __repr__",
      "raise AssertionError",
      "raise NotImplementedError",
      "if __name__ == .__main__.:",
  ]
  ```

**Verification**:
- [ ] `pytest --co -q` lists only tests from `tests/` directory
- [ ] No reference to `tools/pipelines/sense/tests` in config

---

### Step 7: Run Comprehensive Test Suite & Baseline Coverage
- **Command**: 
  ```bash
  pytest tests/ -v --cov=tools --cov-report=term-missing --cov-report=html
  ```
- **Capture baseline**:
  - Total tests run
  - Total coverage %
  - Coverage by subsuite (docflow, sense, chat, orchestrator, integration, e2e)
  - Under-tested modules (anything <70%)
- **Output**: Store results in `COVERAGE_BASELINE.md`

**Verification**:
- [ ] All tests pass
- [ ] Coverage >= 70% overall
- [ ] No failing tests in integration suite (unless creds missing)

---

### Step 8: Create TEST.md Documentation
- **Location**: [Neutron_OS/TEST.md](TEST.md)
- **Contents**:

```markdown
# NeutronOS Test Structure & Conventions

## Overview

Tests in NeutronOS follow **colocated, protected conventions** optimized for monorepo clarity and future Bazel migration. This document explains the structure, patterns, and how to add tests.

## Directory Structure

### Root Tests
`tests/` contains shared fixtures, integration tests, and test suites by component:

```
tests/
├── conftest.py                    # Root fixtures: repo_root, tmp_config, docflow_config
├── sense/
│   ├── conftest.py               # Audio fixtures, voice test data
│   ├── fixtures/
│   │   └── audio_clips/          # Golden audio files for testing
│   └── test_*.py                 # 13 test files
├── chat/
│   ├── conftest.py
│   └── test_*.py
├── docflow/
│   ├── conftest.py
│   └── test_*.py                 # 10 test files
├── orchestrator/
│   ├── conftest.py
│   └── test_*.py
├── setup/
│   └── test_*.py
├── serve/
│   └── test_serve.py
├── integration/
│   ├── conftest.py               # Credential fixtures: gitlab_token, ms_graph_creds
│   └── test_*.py                 # 9 files requiring external services
└── e2e/
    └── test_*.py                 # 4 end-to-end tests
```

### Why Root Tests?
- **Shared fixtures**: Integration and cross-domain tests live here
- **Single discovery path**: `pytest testpaths = ["tests"]` finds everything
- **Isolation**: Conftest hierarchy allows fixture scope per subsuite

### Colocated Tests (Future)
Tools with complex test suites will have local `tests/` subdirectories:
```
tools/pipelines/sense/
├── src/
├── tests/
│   ├── conftest.py
│   └── test_*.py
└── README.md
```

## Test Execution

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Subsuite
```bash
pytest tests/sense/ -v
pytest tests/docflow/ -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=tools --cov-report=html
open htmlcov/index.html
```

### Run by Marker
```bash
pytest -m "not integration" tests/       # Skip integration tests
pytest -m "gitlab" tests/                # Only GitLab-related tests
```

## Fixture Patterns

### Root Conftest (tests/conftest.py)
- `repo_root`: Absolute path to repository root
- `tmp_config`: Temporary config dir with sample people.md, initiatives.md
- `docflow_config`: DocFlow-specific configuration fixture
- `sample_gitlab_export`: Mock GitLab export data

### Sense Conftest (tests/sense/conftest.py)
- `audio_fixture`: Path to golden audio test file
- `voice_test_data`: Voice command test samples

### Chat Conftest (tests/chat/conftest.py)
- `mock_chat_client`: Mocked chat service
- `chat_context`: Pre-configured chat context

### Integration Conftest (tests/integration/conftest.py)
- `gitlab_token`: GitLab API token from .env
- `ms_graph_creds`: Microsoft Graph credentials
- `github_token`: GitHub API token

## Adding New Tests

### For New Python Code in tools/
1. Create `tests/module_name/` directory in root `tests/`
2. Add `conftest.py` if you need custom fixtures
3. Add `test_*.py` files following `pytest` conventions
4. Run: `pytest tests/module_name/ -v`

### For Integration Tests (External Services)
1. Add test file to `tests/integration/`
2. Mark with appropriate marker: `@pytest.mark.gitlab`, `@pytest.mark.onedrive`, etc.
3. Use credentials from `tests/integration/conftest.py`
4. Tests skip gracefully if credentials missing

### Example: New Test File
```python
# tests/mymodule/test_feature.py
import pytest
from tools.mymodule.feature import compute

def test_compute_basic():
    result = compute(5)
    assert result == 10

@pytest.mark.slow
def test_compute_large_input():
    result = compute(1_000_000)
    assert result > 0
```

## Fixture Usage

### In conftest.py
```python
import pytest
from pathlib import Path

@pytest.fixture
def my_config(tmp_config):
    """Use root-level fixture in subsuite conftest."""
    config = tmp_config
    config['custom'] = 'value'
    return config
```

### In test file
```python
def test_with_fixture(my_config):
    assert my_config['custom'] == 'value'
```

## Coverage Targets

- **Minimum**: 70% line coverage for Python code
- **Check coverage**: `pytest tests/ --cov=tools --cov-fail-under=70`
- **Generate report**: `pytest tests/ --cov=tools --cov-report=html`

**Note**: Compiled code (C/C++/Fortran) coverage tested via integration tests, not unit metrics.

## Test Data Management

### Golden Files
Audio fixtures stored in: `tests/sense/fixtures/audio_clips/`
- `golden_correction_clip.m4a`: Test audio file
- `golden_correction_metadata.json`: Metadata

### Adding Test Data
1. Create `tests/[subsuite]/fixtures/` directory
2. Store golden files there
3. Reference in conftest or test via `fixture_path`

## CI/CD Integration

### GitHub Actions
- Runs on Python 3.11, 3.12, 3.13
- Command: `pytest tests/ -v --tb=short`
- Installed with: `pip install -e ".[dev,docflow]"`

### Makefile Commands
```bash
make test              # Unit tests only (no integration)
make integration       # Integration tests (requires .env)
make test-all          # Both unit and integration
make test-gitlab       # GitLab-specific tests
make test-onedrive     # OneDrive-specific tests
```

## Pytest Markers

Available markers for test selection:
- `integration`: External service tests (skip if no creds)
- `gitlab`: GitLab API tests
- `onedrive`: Microsoft Graph / OneDrive tests
- `teams`: Teams transcript tests
- `voice`: Voice/serve integration tests
- `inbox`: Inbox notes tests
- `slow`: Slow-running tests (skip by default with `-m "not slow"`)

## Troubleshooting

### Tests not discovered
Ensure test files follow naming: `test_*.py` or `*_test.py`
Check that `pytest.ini` includes your directory in `testpaths = ["tests"]`

### Fixture not found
Verify conftest.py is in correct location (same dir or parent)
Run with `-v` to see fixture resolution

### Integration tests skip
Ensure .env file exists with required credentials:
```
GITLAB_TOKEN=...
GITHUB_TOKEN=...
MS_GRAPH_CREDENTIALS=...
```

## Bazel Migration Notes

In future, tests will be managed by Bazel BUILD files. Current structure is compatible:
- `tests/` maps to root `py_test()` rules
- Tool-level `tests/` subdirectories map to local `py_test()` targets
- Conftest hierarchy maps to Bazel `test_suites`

No structural changes needed for Bazel readiness.
```

---

### Step 9: Create FIXTURES.md (Reference for Developers)
- **Location**: [tests/FIXTURES.md](tests/FIXTURES.md)
- **Contents**: Complete fixture reference with parameters, return types, scope, examples

---

### Step 10: Update DIR_INTENTS.md
- **Location**: [DIR_INTENTS.md](DIR_INTENTS.md)
- **Add sections**:
  - Purpose of each directory
  - Whether it contains source, tests, config, data
  - Link to TEST.md for test-specific info
  - Bazel compatibility notes

---

### Step 11: Verify Zero Regression
- **Commands**:
  ```bash
  # Full test suite
  pytest tests/ -v
  
  # Coverage check
  pytest tests/ --cov=tools --cov-report=term-missing --cov-fail-under=70
  
  # CI simulation (test on multiple Python versions)
  # (Manually verify GitHub Actions passes)
  ```
- **Document**: Create `COVERAGE_BASELINE.md` with:
  - Date of refactor
  - Total tests run
  - Total coverage %
  - Coverage by component
  - Any under-tested areas flagged

---

## File Operations Summary

### Create
- `tests/sense/conftest.py`
- `tests/chat/conftest.py`
- `tests/orchestrator/conftest.py`
- `tests/integration/conftest.py`
- `tests/FIXTURES.md`
- `tools/test/README.md`
- `tools/test/__init__.py`
- `tools/tracker/tests/` directory
- `tools/cost_estimation_tool/tests/` directory
- `packages/BUILD`, `services/BUILD`, `plugins/BUILD`
- `Neutron_OS/TEST.md`
- `COVERAGE_BASELINE.md`

### Move
- `tools/pipelines/sense/tests/test_bootstrap.py` → `tests/sense/test_bootstrap.py`
- `tools/pipelines/sense/tests/test_correction_errors.py` → `tests/sense/test_correction_errors.py`
- `tools/test_gitlab_tracker_export.py` → `tools/tracker/tests/test_gitlab_tracker_export.py`
- `tools/cost_estimation_tool/test_scenarios.py` → `tools/cost_estimation_tool/tests/test_scenarios.py`
- `docs/_tools/docflow/tests/*` → `tests/docflow/` (consolidate)

### Modify
- `pyproject.toml` (pytest config, coverage config)
- `tests/conftest.py` (refactor, move integration-specific fixtures)
- `DIR_INTENTS.md` (update with directory purposes)

### Delete
- `tools/pipelines/sense/tests/` (directory)
- `docs/_tools/docflow/tests/` (directory)

---

## Execution Checklist

### Pre-Refactor
- [ ] Current working directory clean (git status)
- [ ] All tests passing: `pytest tests/ -v`
- [ ] Baseline coverage: `pytest tests/ --cov=tools --cov-report=term-missing`

### During Refactor
- [ ] Step 1: Consolidate docflow tests
  - [ ] Compare and merge; verify no loss
  - [ ] Delete `docs/_tools/docflow/tests/`
- [ ] Step 2: Move loose test files
  - [ ] Create `tools/tracker/tests/`
  - [ ] Create `tools/cost_estimation_tool/tests/`
  - [ ] Update imports in moved files
- [ ] Step 3: Unify sense tests
  - [ ] Move 2 files to `tests/sense/`
  - [ ] Delete `tools/pipelines/sense/tests/`
- [ ] Step 4: Create conftest hierarchy
  - [ ] Extract integration fixtures
  - [ ] Create 3 new conftest files
  - [ ] Verify fixtures resolve correctly
- [ ] Step 5: Restructure directories
  - [ ] Add BUILD placeholders
  - [ ] Update DIR_INTENTS.md
- [ ] Step 6: Update pytest config
  - [ ] Modify [pyproject.toml](pyproject.toml)
  - [ ] Verify `pytest --co -q` shows only `tests/` paths

### Post-Refactor
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Coverage >= 70%: `pytest tests/ --cov=tools --cov-fail-under=70`
- [ ] No regressions: Compare baseline vs. new coverage
- [ ] Documentation complete: TEST.md, FIXTURES.md, DIR_INTENTS.md
- [ ] CI pipeline passes on all Python versions
- [ ] Commit and push changes

---

## Success Criteria

- ✅ **Single testpath**: `pytest testpaths = ["tests"]` (not multiple paths)
- ✅ **No loose test files**: All `test_*.py` in `tests/` or colocated `tools/*/tests/`
- ✅ **Docflow unified**: One test suite location, no duplication
- ✅ **Coverage enforced**: 70% threshold set in pytest config
- ✅ **Conftest hierarchy**: Each subsuite has own conftest for fixture isolation
- ✅ **Zero regression**: Coverage % same or improved vs. baseline
- ✅ **Documentation**: TEST.md, FIXTURES.md, DIR_INTENTS.md comprehensive and AI-maintainable
- ✅ **Bazel-ready**: Structure compatible with future BUILD file migration
- ✅ **All tests pass**: Full suite runs successfully on Python 3.11, 3.12, 3.13

---

## Notes for Future Sessions

### Bazel Migration Path
When ready to adopt Bazel:
1. Current structure maps directly to BUILD rules
2. No directory reorganization needed
3. `tests/` → root-level `py_test()` rules
4. `tools/*/tests/` → local `py_test()` targets
5. `testpaths = ["tests"]` becomes Bazel `test_suite()` target

### Coverage Gaps to Address
From current baseline analysis:
- `tests/serve/`: Only 1 file; consider expanding
- `tools/` utilities: Some helpers under-tested
- Document these in COVERAGE_BASELINE.md for follow-up work

### Multi-Language Integration
- Document compiled code integration pattern in TEST.md
- Create examples for how to test Python wrappers around C/C++/Fortran
- Placeholder for future language-specific test runners

---

**Generated**: February 24, 2026  
**Next Step**: Execute refactoring plan in order (Steps 1–11)
