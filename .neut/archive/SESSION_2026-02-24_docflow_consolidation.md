# Session Memory: DocFlow Consolidation & Infrastructure Rationalization

**Date**: February 24, 2026  
**Status**: Planning Complete, Awaiting Execution

---

## Critical Architecture Decision

**DocFlow is a Sense capability, NOT a separate module.**

- ONE RAG system: Sense
- ONE embedding store: PostgreSQL + pgvector
- DocFlow's diagram intelligence → Sense skill/provider
- No parallel `tools/docflow/` - merge into `tools/agents/sense/`

---

## Critical Discovery

An elaborate, **forgotten DocFlow system** exists in `docs/_tools/docflow/` (~7,300 lines). Most of it duplicates Sense functionality and should be discarded. Only salvage:

1. **Terraform/Helm** - Infrastructure patterns (valuable)
2. **Diagram analysis** - Unique capability (merge into Sense)
3. **Tests** - Consolidate valid tests

### What to Salvage vs Discard

| Component | Action | Rationale |
|-----------|--------|-----------|
| `deploy/terraform/modules/` | **SALVAGE** → `infra/terraform/` | Real infrastructure value |
| `deploy/helm/docflow/` | **SALVAGE** → `infra/helm/charts/neutron-os/` | Adapt for unified chart |
| `src/docflow/diagrams/` | **SALVAGE** → `tools/agents/sense/providers/diagrams/` | Unique Sense capability |
| `src/docflow/embedding/` | **DISCARD** | Duplicates Sense embedding |
| `src/docflow/rag/` | **DISCARD** | Duplicates Sense RAG |
| `src/docflow/agent/` | **DISCARD** | Duplicates Sense agent |
| `src/docflow/workflow/` | **EVALUATE** | May have useful patterns |
| `docker/` | **DISCARD** | Will use unified Dockerfile |
| `tests/` | **CONSOLIDATE** | Merge diagram tests to tests/sense/ |

---

## Consolidation Plan

### 1. Extract Infrastructure Only

```
docs/_tools/docflow/deploy/terraform/modules/ → infra/terraform/modules/
docs/_tools/docflow/deploy/helm/docflow/      → infra/helm/charts/neutron-os/ (adapted)
```

### 2. Merge Diagram Intelligence into Sense

```
docs/_tools/docflow/src/docflow/diagrams/ → tools/agents/sense/providers/diagrams/
```

This becomes a Sense "provider" or "skill" for:
- Mermaid diagram parsing
- Diagram relationship extraction
- Documentation graph analysis

### 3. Consolidate Tests

```
docs/_tools/docflow/tests/test_diagrams*.py → tests/sense/test_diagram_provider.py
(discard RAG/embedding tests - covered by Sense tests)
```

### 4. Archive/Delete the Rest

Everything else in `docs/_tools/docflow/` is duplicate functionality. Archive or delete.

---

## Unified Server Topology (Target)

```
infra/helm/charts/neutron-os/
├── Chart.yaml
├── values.yaml
├── values-local.yaml      # K3D overrides
├── values-stage.yaml
├── values-prod.yaml
└── templates/
    ├── sense-deployment.yaml     # Port 8765 (websocket) - THE agent
    ├── api-deployment.yaml       # Port 8000 (REST gateway)
    ├── postgres-statefulset.yaml # Port 5432 (DB + pgvector)
    ├── ingress.yaml
    └── _helpers.tpl
```

**No separate DocFlow service** - diagram capability lives inside Sense.

---

## Infrastructure Status

### Already Implemented

- `tools/agents/setup/infra.py` - Docker/K3D/PostgreSQL automation
- `neut infra` CLI command
- Bootstrap.sh Step 5 - Infrastructure auto-setup
- K3D cluster "neut" with postgres StatefulSet + pgvector

### Pending

- Populate `infra/` directory with extracted Terraform/Helm
- Merge diagram provider into Sense

---

## Files Modified This Session

| File | Change |
|------|--------|
| `tools/agents/setup/infra.py` | NEW: ~500 lines Docker/K3D/PostgreSQL automation |
| `tools/agents/setup/probe.py` | Added docker, k3d, kubectl to tool_checks |
| `tools/neut_cli.py` | Added "infra" to SUBCOMMANDS |
| `tools/agents/setup/wizard.py` | Added infra phase, _phase_infra() method |
| `scripts/bootstrap.sh` | Added DIRENV_LOG_FORMAT="", Step 5 Infrastructure |

---

## Next Actions (Priority Order)

1. **Update REFACTORING_PLAN.md** - Add Step 0 DocFlow consolidation (see below)
2. **Extract Terraform** → `infra/terraform/modules/`
3. **Create unified Helm chart** → `infra/helm/charts/neutron-os/`
4. **Merge diagram code into Sense** → `tools/agents/sense/providers/diagrams/`
5. **Update tests** → diagram tests to `tests/sense/`
6. **Archive/delete elaborate DocFlow** → `docs/_tools/docflow/`
7. **Execute REFACTORING_PLAN.md Steps 1-11** → test consolidation

---

## REFACTORING_PLAN.md Update Needed

Add this section after the Executive Summary (around line 22):

```markdown
---

## Step 0: DocFlow → Sense Consolidation (Prerequisite)

**Status**: Planning Complete  
**Priority**: Execute before test refactoring  
**Architecture**: DocFlow is a Sense capability, not a separate module

### Principle

- **ONE RAG**: Sense
- **ONE embedding store**: PostgreSQL + pgvector  
- **ONE agent**: Sense with multiple providers/skills
- DocFlow's diagram analysis → Sense provider

### Discovery

Elaborate DocFlow system (~7,300 lines) in `docs/_tools/docflow/` duplicates Sense. Salvage only:
1. Terraform/Helm infrastructure patterns
2. Diagram analysis capability (unique)

### Consolidation Tasks

#### 0.1 Extract Infrastructure
```
docs/_tools/docflow/deploy/terraform/modules/ → infra/terraform/modules/
docs/_tools/docflow/deploy/helm/docflow/      → infra/helm/charts/neutron-os/ (adapted)
```

#### 0.2 Merge Diagram Provider into Sense
```
docs/_tools/docflow/src/docflow/diagrams/ → tools/agents/sense/providers/diagrams/
```

Update Sense to register diagram provider for:
- Mermaid parsing
- Diagram relationship extraction
- Documentation graph analysis

#### 0.3 Consolidate Tests
```
docs/_tools/docflow/tests/test_diagrams*.py → tests/sense/test_diagram_provider.py
```

#### 0.4 Delete Duplicate Code
```
rm -rf docs/_tools/docflow/  # After extraction complete
```

### Verification

- [ ] `infra/terraform/` contains working modules
- [ ] `helm template infra/helm/charts/neutron-os/` renders
- [ ] Sense can analyze Mermaid diagrams via diagram provider
- [ ] `pytest tests/sense/test_diagram_provider.py` passes
- [ ] No `docs/_tools/docflow/` directory exists
- [ ] No duplicate RAG/embedding code in codebase

---
```

---

## Key Decision

**DocFlow ⊂ Sense** (DocFlow is a subset of Sense)

- Sense is the RAG/agent system
- DocFlow diagram intelligence is a Sense capability
- No parallel embedding systems
- No parallel RAG systems
- One agent, many skills

---

## Reference: Elaborate DocFlow Structure (to be archived)

```
docs/_tools/docflow/
├── pyproject.toml
├── WHAT_WAS_BUILT.md
├── deploy/
│   ├── helm/docflow/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── values-prod.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── ingress.yaml
│   │       ├── hpa.yaml
│   │       ├── pdb.yaml
│   │       ├── configmap.yaml
│   │       ├── secret.yaml
│   │       └── _helpers.tpl
│   └── terraform/
│       ├── environments/
│       │   ├── stage/
│       │   └── prod/
│       └── modules/
│           ├── eks/
│           ├── rds/
│           ├── elasticache/
│           └── vpc/
├── docker/
│   ├── Dockerfile.api
│   └── Dockerfile.agent
├── src/docflow/
│   ├── __init__.py
│   ├── agent/
│   ├── cli/
│   ├── convert/
│   ├── core/
│   ├── diagrams/
│   ├── embedding/
│   ├── git/
│   ├── llm/
│   ├── meetings/
│   ├── providers/
│   ├── rag/
│   ├── review/
│   └── workflow/
└── tests/
```

---

## Action Items (from Sense signals)

- [ ] **Get OPR-1 and OPR-2 from Jim Terry** — Review NETL operating procedures to understand how reactor log is structured as an attachment. Informs Reactor Ops Log PRD design (log format, mandatory fields, relationship to startup/shutdown procedures).
