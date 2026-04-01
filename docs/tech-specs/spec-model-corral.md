# Model Corral Technical Specification

**Part of:** [Neutron OS Master Tech Spec](spec-executive.md)

---

> **Scope:** This document specifies the Model Corral architecture — NeutronOS's registry for physics simulation models (high-fidelity input decks and trained ROMs). It defines storage architecture, manifest schemas, access control, and system integration.

| Property | Value |
|----------|-------|
| Version | 0.1 |
| Last Updated | 2026-03-17 |
| Status | Draft |
| PRD | [Model Corral PRD](../requirements/prd-model-corral.md) |
| Related | [Digital Twin Hosting Spec](spec-digital-twin-hosting.md), [Data Architecture Spec](spec-data-architecture.md), [DOE Data Management & Sharing PRD](../requirements/prd-doe-data-management.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Storage Architecture](#2-storage-architecture)
3. [Data Model](#3-data-model)
4. [Model Manifest Schema](#4-model-manifest-schema)
5. [Physics Code Integration](#5-physics-code-integration)
6. [ROM Extension Schema](#6-rom-extension-schema)
7. [Logical Organization](#7-logical-organization)
8. [Access Control](#8-access-control)
9. [Git Integration](#9-git-integration)
10. [Validation Framework](#10-validation-framework)
11. [System Integration](#11-system-integration)
12. [CLI Interface](#12-cli-interface)
13. [Web Interface](#13-web-interface)
14. [TRIGA DT Website Integration](#14-triga-dt-website-integration)

---

## 1. Overview

Model Corral is NeutronOS's unified registry for computational models:

| Model Type | Examples | Storage |
|------------|----------|---------|
| **High-fidelity input decks** | MCNP, VERA, SAM, Griffin, RELAP, OpenMC, BISON, MPACT | Object storage + PostgreSQL metadata |
| **Trained ROMs** | WASM modules, ONNX files, PyTorch checkpoints | Object storage + PostgreSQL metadata |
| **Validation datasets** | HDF5, Parquet benchmark data | Object storage |
| **CoreForge configurations** | JSON parameter files | Object storage |

**Design Principles:**
- **NeutronOS-primary**: Models managed by NeutronOS; Git is optional sync, not required
- **Schema-enforced**: All models have validated `model.yaml` manifests
- **Lineage-tracked**: ROMs trace back to training data and physics models
- **Dual access**: CLI and web interfaces with equivalent capabilities

---

## 2. Storage Architecture

### 2.1 Component Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Model Corral Storage                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   PostgreSQL (Metadata)                              │   │
│   │                                                                      │   │
│   │  • model_registry table (model.yaml contents)                       │   │
│   │  • model_versions table (version history)                           │   │
│   │  • model_lineage table (parent-child relationships)                 │   │
│   │  • model_validations table (validation results)                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                  Object Storage (SeaweedFS/S3)                           │   │
│   │                                                                      │   │
│   │  • Input files (MCNP decks, XML geometries, material libraries)     │   │
│   │  • ROM artifacts (WASM modules, ONNX files)                         │   │
│   │  • Validation datasets (HDF5, Parquet)                              │   │
│   │  • Documentation (README, images, papers)                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                    ┌───────────────┴───────────────┐                        │
│                    │                               │                        │
│                    ▼                               ▼                        │
│   ┌─────────────────────────┐     ┌─────────────────────────┐              │
│   │   Git Sync (Optional)   │     │   Standalone Mode       │              │
│   │                         │     │                         │              │
│   │ • GitHub/GitLab push    │     │ • No Git required       │              │
│   │ • Version = Git tag     │     │ • NeutronOS sequences   │              │
│   │ • Bidirectional sync    │     │ • Web/CLI only          │              │
│   └─────────────────────────┘     └─────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Object Storage Layout

```
models/
├── {reactor_type}/
│   └── {facility}/
│       └── {physics_code}/
│           └── {model_id}/
│               ├── v{version}/
│               │   ├── model.yaml
│               │   ├── input.i
│               │   ├── materials.dat
│               │   ├── geometry.xml
│               │   └── README.md
│               └── latest -> v3.2.1
│
roms/
├── {reactor_type}/
│   └── {facility}/
│       └── {rom_tier}/
│           └── {model_id}/
│               ├── v{version}/
│               │   ├── model.yaml
│               │   ├── rom.wasm
│               │   ├── training_manifest.json
│               │   └── validation/
│               └── latest -> v2.0.0
│
datasets/
├── {dataset_id}/
│   ├── manifest.yaml
│   ├── data.hdf5
│   └── README.md
```

---

## 3. Data Model

### 3.1 Core Entities

| Entity | Description | Primary Key |
|--------|-------------|-------------|
| **Model** | A versioned physics model or ROM | `model_id` |
| **ModelVersion** | Specific version of a model | `model_id` + `version` |
| **ModelLineage** | Parent-child relationships | `model_id` + `parent_model_id` |
| **ModelValidation** | Validation run results | `validation_id` |
| **Dataset** | Validation/training dataset | `dataset_id` |

### 3.2 Entity Relationships

```
Model (1) ──────────< ModelVersion (N)
  │
  └─────────< ModelLineage (N) >─────────┘
                                         │
                                         └─── Parent Model
  
ModelVersion (1) ──────< ModelValidation (N)
                              │
                              └─── Dataset (FK)

ROM Model ───────────> Training Source Model (via model.yaml)
           ───────────> Training Runs (via training_manifest.json)
```

---

## 4. Model Manifest Schema

Every model requires a `model.yaml` manifest. The schema enforces consistency across all model types.

### 4.1 Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | string | Unique identifier (kebab-case) |
| `name` | string | Human-readable display name |
| `version` | semver | Semantic version (x.y.z) |
| `status` | enum | `draft` \| `review` \| `production` \| `deprecated` \| `archived` |
| `reactor_type` | enum | `TRIGA` \| `MSR` \| `PWR` \| `BWR` \| `HTGR` \| `VHTR` \| `SFR` \| `custom` |
| `facility` | string | Facility identifier (NETL, MIT, generic, etc.) |
| `physics_domain` | array | List of physics domains covered |
| `physics_code` | string | Code name (MCNP, VERA, SAM, etc.) |
| `created_by` | email | Creator's email address |
| `created_at` | ISO8601 | Creation timestamp |
| `access_tier` | enum | `public` \| `facility` |

### 4.2 Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `code_version` | string | Physics code version |
| `input_files` | array | List of input file paths and types |
| `parent_model` | string | Fork source model_id |
| `coreforge_config` | string | Path to CoreForge config (if generated) |
| `validation_status` | enum | `unvalidated` \| `in_progress` \| `validated` \| `failed` |
| `validation_dataset` | string | Reference to validation dataset |
| `validation_metrics` | object | Key validation metrics |
| `description` | string | Detailed description (supports markdown) |
| `publications` | array | List of DOIs and titles |
| `tags` | array | Searchable tags |

### 4.3 Validation Rules

| Rule | Constraint |
|------|------------|
| `model_id` format | `^[a-z0-9-]+$` (lowercase, hyphens only) |
| `version` format | Semantic versioning (major.minor.patch) |
| `reactor_type` | Must be from allowed enum |
| `status` transitions | `draft` → `review` → `production` → `deprecated` → `archived` |
| File references | All `input_files` paths must exist in model directory |

---

## 5. Physics Code Integration

Model Corral supports input decks for major nuclear simulation codes. Each code has specific file structure requirements and validation capabilities.

### 5.1 Supported Physics Codes

| Code | Domain | Developer | Input Format | Typical Files |
|------|--------|-----------|--------------|---------------|
| **MCNP** | Monte Carlo neutronics | LANL | Fixed-format text | `input.i`, `xsdir`, `wssa` |
| **VERA/MPACT** | Deterministic neutronics + TH | ORNL/CASL | XML + HDF5 | `vera_inp.xml`, `mpact_inp.xml` |
| **SAM** | Systems analysis (MSR) | ANL | MOOSE input | `*.i`, `mesh.e` |
| **Griffin** | Reactor physics | INL | MOOSE input | `*.i`, `cross_sections/` |
| **OpenMC** | Monte Carlo neutronics | MIT | XML | `geometry.xml`, `materials.xml`, `settings.xml` |
| **RELAP5/RELAP7** | Thermal-hydraulics | INL | Card-based / MOOSE | `relap.i` |
| **BISON** | Fuel performance | INL | MOOSE input | `*.i`, `mesh.e` |
| **Nek5000/NekRS** | CFD | ANL | Fortran par files | `*.par`, `*.re2`, `*.usr` |
| **TRACE** | Thermal-hydraulics | NRC | ASCII input | `trcin` |
| **PARCS** | Nodal diffusion | Purdue/NRC | Fixed-format | `*.inp` |

### 5.2 Code-Specific Manifest Fields

Extended `model.yaml` fields for physics codes:

| Field | Type | Description |
|-------|------|-------------|
| `physics_code` | string | Code name (required) |
| `code_version` | string | Minimum compatible version |
| `input_files` | array | List of input files with types |
| `input_files[].path` | string | Relative path to file |
| `input_files[].type` | enum | `main_input` \| `geometry` \| `materials` \| `cross_sections` \| `mesh` \| `restart` \| `auxiliary` |
| `dependencies.cross_sections` | string | XS library reference (ENDF, JEFF, etc.) |
| `dependencies.mesh_generator` | string | Mesh tool used (Cubit, MOOSE, gmsh) |
| `execution.mpi_ranks` | int | Recommended MPI parallelism |
| `execution.memory_gb` | float | Estimated memory requirement |
| `execution.runtime_estimate` | string | Expected runtime (e.g., "2-4 hours") |

### 5.3 Code-Specific Validation

| Code | Syntax Check | Completeness Check | Notes |
|------|--------------|-------------------|-------|
| MCNP | ✅ Parser available | ✅ Check referenced files | Validate cell/surface references |
| VERA/MPACT | ✅ XML schema | ✅ XSD validation | CASL XML schemas available |
| SAM/Griffin/BISON | ✅ MOOSE syntax | ✅ Check mesh, XS files | Use MOOSE `--check-input` |
| OpenMC | ✅ XML schema | ✅ Schema validation | Official XSD provided |
| RELAP5 | ⚠️ Limited | ⚠️ Card format only | Legacy format challenges |

### 5.4 Multi-Physics Coupling

For coupled simulations, the manifest tracks coupling relationships:

```yaml
coupling:
  type: loose  # loose | tight | monolithic
  codes:
    - code: MPACT
      role: neutronics
      interface: power_distribution
    - code: CTF
      role: thermal_hydraulics  
      interface: temperature_feedback
  coupling_frequency: per_timestep
  data_exchange_format: HDF5
```

### 5.5 Example: VERA/MPACT Model Manifest

```yaml
model_id: triga-netl-mpact-shadow-v3
name: NETL TRIGA MPACT Shadow Model
version: 3.2.1
status: production
reactor_type: TRIGA
facility: NETL
physics_code: MPACT
code_version: "4.3.0"
physics_domain:
  - neutronics
  - depletion
  - thermal_hydraulics

input_files:
  - path: mpact_inp.xml
    type: main_input
  - path: core_geometry.xml
    type: geometry
  - path: materials.xml
    type: materials
  - path: cross_sections/
    type: cross_sections

dependencies:
  cross_sections: ENDF/B-VIII.0
  mesh_generator: VERA-internal

execution:
  mpi_ranks: 64
  memory_gb: 128
  runtime_estimate: "4-6 hours"

validation_status: validated
validation_dataset: triga-2025-benchmark
validation_metrics:
  k_eff_bias_pcm: -12
  power_rmse_percent: 2.3
  temperature_max_error_c: 5.1
```

---

## 6. ROM Extension Schema

ROMs extend the base schema with training and deployment metadata.

### 5.1 ROM-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `rom_tier` | enum | `ROM-1` \| `ROM-2` \| `ROM-3` \| `ROM-4` |
| `model_type` | enum | `surrogate` \| `physics_informed_nn` \| `gaussian_process` |
| `training.source_model` | string | model_id of physics model used for training |
| `training.training_runs` | array | List of run_ids used for training data |
| `training.training_hash` | string | SHA256 of training data |
| `training.framework` | string | ML framework (pytorch, tensorflow, etc.) |
| `deployment.format` | enum | `onnx` \| `wasm` \| `pytorch` \| `tensorflow` |
| `deployment.wasm_module` | string | Path to WASM module |
| `performance.inference_latency_ms` | number | Measured inference latency |
| `performance.valid_input_ranges` | object | Valid input ranges for each parameter |

### 6.2 ROM Tier Requirements

| Tier | Latency Requirement | Resolution | Typical Format |
|------|---------------------|------------|----------------|
| ROM-1 | <100ms | Low spatial, transient | WASM |
| ROM-2 | 5-20s | Low spatial, high energy | WASM/ONNX |
| ROM-3 | <5 min | High spatial, transient | WASM/ONNX |
| ROM-4 | Minutes | High spatial, quasi-static | ONNX |

---

## 7. Logical Organization

### 7.1 Hierarchy

```
NeutronOS Model Registry
│
├── reactor_type: TRIGA
│   ├── facility: NETL
│   │   ├── physics_code: MCNP
│   │   │   └── triga-netl-mcnp-transient-v3
│   │   ├── physics_code: VERA
│   │   │   └── triga-netl-vera-shadow-canonical
│   │   └── physics_code: OpenMC
│   └── facility: MIT
│
├── reactor_type: MSR
│   ├── facility: MSRE
│   │   └── physics_code: SAM
│   └── facility: generic
│
├── roms/
│   └── triga/netl/
│       ├── rom-1-transient/
│       ├── rom-2-quasistatic/
│       └── rom-3-highres/
│
└── datasets/
    ├── triga-2025-benchmark/
    └── msr-safety-benchmark/
```

### 7.2 Naming Convention

```
{reactor}-{facility}-{code}-{variant}-v{version}

Examples:
- triga-netl-mcnp-transient-v3
- triga-netl-vera-shadow-canonical
- msr-msre-sam-thermal-v1
- triga-netl-rom2-quasistatic-v2
```

---

## 8. Access Control

### 8.1 Access Tiers

| Tier | Description | Storage | Network |
|------|-------------|---------|---------|
| `public` | Open benchmarks, educational examples | Cloud NeutronOS | Public internet |
| `facility` | Facility-specific configurations | On-prem NeutronOS | Campus/VPN |

> **Open Question:** Do physics code input models (geometry, materials, operating parameters) require export control classification? Initial assessment suggests these tiers are for deployment/visibility management rather than regulatory compliance, but this requires validation with export control officers.

### 8.2 Authorization Matrix

| Operation | Public Models | Facility Models |
|-----------|---------------|-----------------|
| Browse/Search | Any NeutronOS user | Facility members |
| Download | Any NeutronOS user | Facility members |
| Submit new | Any authenticated user | Facility members |
| Approve/Promote | Maintainers | Facility maintainers |
| Delete/Archive | Admins | Facility admins |

---

## 9. Git Integration

### 9.1 Integration Modes

| Mode | Primary | Direction | Use Case |
|------|---------|-----------|----------|
| `none` | NeutronOS | — | Standalone, proprietary, non-Git users |
| `sync` | NeutronOS | NeutronOS → Git | Default: NeutronOS manages, Git for sharing |
| `mirror` | Git | Git → NeutronOS | Import existing Git repos |

### 9.2 Version Alignment

When Git sync is enabled:
- NeutronOS releases create Git tags
- Draft versions map to branches
- Git commits without NeutronOS versions remain accessible but not "released"
- NeutronOS can have versions not in Git (for facility-only models)

### 9.3 Sync Workflow

```
Submit to NeutronOS
        │
        ▼
┌───────────────────┐
│ Store in Object   │
│ Storage + DB      │
└─────────┬─────────┘
          │
    Git sync enabled?
          │
    ┌─────┴─────┐
    │           │
   Yes          No
    │           │
    ▼           ▼
┌─────────┐  Done
│ Push to │
│ Remote  │
└─────────┘
```

---

## 10. Validation Framework

### 10.1 Validation Levels

| Level | Description | Automated |
|-------|-------------|-----------|
| **Schema** | model.yaml conforms to JSON Schema | Yes |
| **Files** | All referenced files exist and readable | Yes |
| **Syntax** | Input deck syntax valid for physics code | Partial |
| **Reference** | Comparison against benchmark dataset | No |

### 10.2 Validation Workflow

```
neut model validate ./my-model
        │
        ▼
┌───────────────────┐
│ 1. Schema Check   │ → model.yaml valid?
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. File Check     │ → All files present?
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. Syntax Check   │ → Input deck parseable? (if validator available)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. Report         │ → Pass/Fail + Details
└───────────────────┘
```

### 10.3 Validation Metrics

For reference validation against datasets:

| Metric | Description |
|--------|-------------|
| `rmse_power` | Root mean square error for power predictions |
| `max_error_temp` | Maximum temperature error (°C) |
| `reactivity_bias_pcm` | Reactivity bias in pcm |
| `timing_offset_ms` | Timing offset for transient predictions |

---

## 11. System Integration

### 11.1 RAG Integration

Model documentation indexed into `rag-models` corpus:

| Content | Indexed |
|---------|---------|
| README.md | Full text |
| model.yaml description | Full text |
| Publication titles | Metadata |
| Tags | Metadata |

### 11.2 dbt Integration

| Layer | Table | Description |
|-------|-------|-------------|
| Bronze | `model_registry_raw` | Raw model.yaml JSON |
| Silver | `model_registry_validated` | Schema-validated, enriched |
| Gold | `model_catalog` | Searchable catalog |
| Gold | `model_lineage` | Parent-child relationships |
| Gold | `model_validation_metrics` | Aggregated validation stats |

### 11.3 Agent Tools

| Tool | Category | Description |
|------|----------|-------------|
| `corral_search` | READ | Search models by query and filters |
| `corral_get_model` | READ | Retrieve model metadata |
| `corral_validate` | READ | Validate model directory |
| `corral_get_lineage` | READ | Get model lineage graph |

---

## 12. CLI Interface

### 12.1 Command Structure

```
neut model <verb> [args] [--flags]

Verbs:
  search    Search for models
  list      List models with filters
  show      Show model details
  init      Initialize new model directory
  validate  Validate model against schema
  add       Submit model to registry
  pull      Download model
  export    Export model as archive
  diff      Compare model versions
  lineage   Show ROM → physics model chain
  sync      Push/pull Git remote
  audit     View change history
```

### 12.2 Key Commands

| Command | Description |
|---------|-------------|
| `neut model search "TRIGA transient"` | Full-text search |
| `neut model list --reactor=triga --code=mcnp` | Filtered listing |
| `neut model show triga-netl-mcnp-v3` | Model details |
| `neut model pull triga-netl-mcnp-v3 ./` | Download model |
| `neut model validate ./my-model` | Validate before submit |
| `neut model add ./my-model` | Submit to registry |

---

## 13. Web Interface

### 13.1 Views

| View | Description |
|------|-------------|
| **Catalog Browser** | Hierarchical navigation, card grid |
| **Search Results** | Full-text + faceted search |
| **Model Detail** | Metadata, files, README, validation |
| **Version History** | Timeline, diff viewer |
| **Lineage Graph** | D3 visualization of relationships |
| **Upload Wizard** | Step-by-step submission |
| **Admin Dashboard** | Validation queue, sync status |

### 13.2 Design Principles

- Every CLI operation has web equivalent
- Non-Git users can use without Git knowledge
- Drag-drop upload for model files
- Real-time validation feedback
- Visual diff for version comparison

---

## 14. TRIGA DT Website Integration

The existing [TRIGA Digital Twin Website](../../../TRIGA_Digital_Twin/triga_dt_website/) provides a natural integration point for Model Corral features.

### 14.1 Current Website Structure

| Route | Feature | Description |
|-------|---------|-------------|
| `/core` | Core configuration | Hex grid with burnup colors, position tooltips |
| `/simulator` | Real-time simulator | Control rod movement, physics stepping |
| `/shadowcaster` | MPACT predictions | Critical rod height predictions vs measured |
| `/data_by_date` | Historical data | Plotly charts by date |
| `/txt2sql` | Natural language SQL | LLM-powered database queries |
| `/operation_log` | Operation logging | Protected log entry system |

### 14.2 Integration Mapping

| Model Corral Feature | Integration Point | Implementation |
|---------------------|-------------------|----------------|
| **Catalog Browser** | New `/models` nav item | Card grid similar to `/core` pattern |
| **Model Detail** | `/models/{model_id}` | Metadata + file viewer + README |
| **MPACT Model View** | Extend `/shadowcaster` | Link to canonical Shadow model in Corral |
| **Core Config Models** | Link from `/core` | "View model in Corral" button |
| **Lineage Graph** | Tab on model detail | D3 visualization (existing JS patterns) |
| **Upload Wizard** | `/models/upload` | Step-by-step form with drag-drop |

### 14.3 Early Implementation Path

**Phase 1: Read-Only Catalog** (Low effort)
1. Add `/models` route to Flask app
2. List models from PostgreSQL `model_catalog` table
3. Card grid UI matching existing site style
4. Model detail page with metadata display

**Phase 2: Cross-Linking** (Medium effort)
1. Link `/core` configurations to their Corral models
2. Link `/shadowcaster` MPACT to canonical Shadow model
3. Add "Source Model" links to ROMs

**Phase 3: Upload & Validation** (Higher effort)
1. Upload wizard with drag-drop
2. Real-time `model.yaml` validation
3. Git sync configuration (optional)

### 14.4 UI Consistency

Follow existing website patterns:
- Same CSS (`static/css/style.css`)
- Same nav structure in `base.html`
- Same card/grid layouts as `/core`
- Plotly for any visualizations
- MathJax for equations in descriptions

---

## DMSP Manifest Extensions

For DOE DMSP compliance, the `model.yaml` manifest schema extends with three fields: `license` (required, SPDX identifier), `funding_source` (optional, DOE award number), and `doi` (assigned when the model is published to a public repository). These fields enable automated OSTI reporting and DataCite DOI minting for models produced under DOE-funded research. See [prd-doe-data-management.md](../requirements/prd-doe-data-management.md).

---

## Related Documents

- [Model Corral PRD](../requirements/prd-model-corral.md) — User requirements
- [Digital Twin Hosting Spec](spec-digital-twin-architecture.md) — Execution infrastructure
- [Data Architecture Spec](spec-data-architecture.md) — Lakehouse integration
- [RAG Architecture Spec](spec-rag-architecture.md) — Documentation indexing
