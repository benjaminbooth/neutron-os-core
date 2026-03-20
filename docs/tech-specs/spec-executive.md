# NeutronOS Executive Technical Specification

**The intelligence platform for nuclear facilities**

---

| Property | Value |
|----------|-------|
| Version | 1.0 |
| Last Updated | 2026-03-16 |
| Status | Active Development (v0.4.0) |
| Authors | Benjamin Booth, UT Computational NE |

---

> **This is the executive tech spec** — a concise overview of NeutronOS's
> architecture, what's built, and where to find details. Each section links
> to the authoritative spec. No content is duplicated; this document is an
> index with context.
>
> For strategic context, see the [Executive PRD](../requirements/prd-executive.md).

---

## Architecture Overview

NeutronOS is a modular Python platform where **everything is an extension**.
The core provides infrastructure (LLM gateway, event bus, state management,
CLI registry); all domain functionality ships as builtin extensions.

```
neut <noun> <verb> [args] [--flags]

┌─────────────────────────────────────────────────────────────────────┐
│                           neut CLI                                   │
│         cli_registry.py discovers extensions via TOML manifests      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      Infrastructure                                  │
│  gateway.py    router.py    state.py    routing_audit.py             │
│  (LLM routing) (EC classify) (hybrid store) (audit trail)           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                    Builtin Extensions (17)                            │
│                                                                      │
│  Agents:    signal  chat  mo  doctor  mirror                         │
│  Tools:     pub  rag  db  demo  repo  cost_estimation                │
│  Utilities: settings  status  test  update  note                     │
│  Services:  serve (web API)                                          │
└─────────────────────────────────────────────────────────────────────┘
```

**Key design principles** (detailed in [CLAUDE.md](../../CLAUDE.md)):
- Everything is an extension (3-tier discovery: project → user → builtin)
- Reactor-agnostic core, reactor-specific via external extensions
- Offline-first (queue locally, sync on restore)
- Human-in-the-loop for safety-adjacent writes
- Model-agnostic, cloud-agnostic, IDE-agnostic

---

## Component Specs & Implementation Status

### Core Infrastructure

| Component | Spec | Status | Key Files |
|-----------|------|--------|-----------|
| **LLM Gateway** | [Model Routing Spec](spec-model-routing.md) | ✅ Phase 1+2a shipped | `infra/gateway.py`, `infra/router.py` |
| **Export Control Router** | [Model Routing Spec §4](spec-model-routing.md) | ✅ Shipped | Keyword + Ollama SLM + sensitivity knobs |
| **Hybrid State Store** | [State Management Spec](spec-agent-state-management.md) | ✅ Shipped | `infra/state.py` (file + PostgreSQL backends) |
| **Routing Audit Log** | [Model Routing Spec §11](spec-model-routing.md) | ✅ Shipped | `infra/routing_audit.py` → JSONL |
| **Connections** | [Connections Spec](spec-connections.md) | 📋 Spec'd | Credential resolution, `neut connect` |
| **Settings** | [Model Routing Spec §6](spec-model-routing.md) | ✅ Shipped | `settings/store.py` (global + project scope) |

### Agents

| Agent | CLI Noun | Spec | Status | Description |
|-------|----------|------|--------|-------------|
| **Signal** | `neut signal` | [Agent Architecture](spec-agent-architecture.md) | ✅ Shipped | Signal ingestion: voice, Teams, GitLab, GitHub, freetext → extractors → correlator → synthesizer |
| **Chat** | `neut chat` | [Agent Architecture](spec-agent-architecture.md) | ✅ Shipped | Interactive LLM with tool use, RAG, per-turn routing, TUI + REPL |
| **M-O** | `neut mo` | [State Management Spec](spec-agent-state-management.md) | ✅ Shipped | Resource steward: scratch lifecycle, retention enforcement, vitals |
| **Doctor** | `neut doctor` | — | 🔲 Partial | LLM-powered diagnosis (Layer 3 built, security checks pending) |
| **Mirror** | `neut mirror` | — | ✅ Shipped | Public GitHub mirror sensitivity gate |

### Tools

| Tool | CLI Noun | Spec | Status | Description |
|------|----------|------|--------|-------------|
| **Publisher** | `neut pub` | [Publisher Spec](spec-publisher.md) | ✅ Shipped | Document lifecycle: markdown → generate → publish to 19 endpoints |
| **RAG** | `neut rag` | [RAG Architecture](spec-rag-architecture.md) | ✅ Shipped | Three-tier corpus (community/org/personal), pgvector, EC-compliant |
| **Database** | `neut db` | — | ✅ Shipped | PostgreSQL lifecycle (up/down/migrate/status) |
| **Demo** | `neut demo` | — | ✅ Shipped | 9-act guided walkthrough ("Jay's Story") |
| **Model Corral** | `neut model` | [Model Corral Spec](spec-model-corral.md) | 📋 Spec'd | Physics model registry: MCNP/VERA/SAM decks, ROMs, validation datasets |
| **Digital Twin** | `neut twin` | [DT Hosting Spec](spec-digital-twin-architecture.md) | 📋 Spec'd | Run ROMs, Shadow simulations, validation, comparison |

### Utilities

| Utility | CLI Noun | Status | Description |
|---------|----------|--------|-------------|
| **Settings** | `neut settings` | ✅ Shipped | get/set/reset/edit, global + project scope |
| **Status** | `neut status` | ✅ Shipped | System health: LLM providers, Ollama, routing, DB, services |
| **Update** | `neut update` | ✅ Shipped | Self-update with restart preservation |
| **Test** | `neut test` | ✅ Shipped | Test orchestration wrapper |

---

## Data Architecture

**Authoritative spec:** [Data Architecture Spec](spec-data-architecture.md)

| Layer | Technology | Status |
|-------|-----------|--------|
| **Object storage** | MinIO (S3-compatible, on-premise) | 📋 Spec'd |
| **Operational DB** | PostgreSQL 16 (K3D local, K8S production) | ✅ Running |
| **Vector store** | pgvector 0.8.2 (same PostgreSQL) | ✅ Running |
| **Data lakehouse** | Apache Iceberg + DuckDB | 📋 Spec'd |
| **Orchestration** | Dagster | 📋 Spec'd |
| **Transformation** | dbt | 📋 Spec'd |
| **State management** | Hybrid store (flat file + PostgreSQL) | ✅ Shipped |

**Medallion pattern:** Bronze (raw append-only) → Silver (cleaned, validated) → Gold (aggregated, business-ready). Detailed in the Data Architecture Spec.

**Retention:** Configurable via `runtime/config/retention.yaml`. M-O enforces automatically. See [State Management PRD](../requirements/prd-agent-state-management.md).

---

## Security Architecture

**Authoritative specs:**
- [Security & Access Control PRD](../requirements/prd-security.md)
- [Model Routing Spec §7-8-10](spec-model-routing.md)
- [Connections Spec §8](spec-connections.md)

| Layer | Description | Status |
|-------|-------------|--------|
| **Physical boundary** | VPN / private network isolates EC data | ✅ Enforced |
| **Query classification** | Keyword + Ollama SLM, 3 sensitivity levels | ✅ Shipped |
| **Tier-aware routing** | Gateway routes to public or private endpoint | ✅ Shipped |
| **Routing audit** | JSONL log of every routing decision (no plaintext) | ✅ Shipped |
| **Chunk sanitization** | Strip injection patterns before LLM context | 🔲 Planned (Phase 1) |
| **Response scanning** | Scan EC responses at network boundary | 🔲 Planned (Phase 1) |
| **System prompt hardening** | Non-negotiable security instructions for EC sessions | 🔲 Planned (Phase 1) |
| **Security event log** | PostgreSQL `security_events` table with HMAC | 🔲 Planned (Phase 1) |
| **Store quarantine** | EC content in public RAG → quarantine + alert | 🔲 Planned (Phase 2) |
| **Authorization (OpenFGA)** | ReBAC/RBAC/ABAC via OpenFGA | 🔲 Planned (Phase 3) |

**Principle:** Classification decides WHAT; authorization decides WHO. Both pass independently.

---

## Infrastructure & Deployment

| Environment | Stack | Status |
|-------------|-------|--------|
| **Local dev** | K3D + Helm (PostgreSQL, pgvector) | ✅ Running |
| **Production** | Kubernetes + Terraform + Helm | 📋 Spec'd |
| **Private endpoint** | vLLM on rascal (UT VPN) | ✅ Running |
| **TACC endpoint** | vLLM on TACC (Apptainer) | 📋 Proposed ([Routing Spec §9](spec-model-routing.md)) |

**Helm chart:** `infra/helm/charts/neutron-os/` — deploys PostgreSQL, Signal server, web API.

**Bootstrap:** `source scripts/bootstrap.sh` → venv, pip install, direnv, K3D, Ollama, git hooks.

---

## Extension System

**Authoritative docs:** [CLAUDE.md §Extension System](../../CLAUDE.md)

Extensions are discovered via `neut-extension.toml` manifests. Three tiers:
1. **Project-local:** `.neut/extensions/` (highest priority)
2. **User-global:** `~/.neut/extensions/`
3. **Builtin:** `src/neutron_os/extensions/builtins/`

Extension kinds: `agent` (LLM autonomy), `tool` (invoked by agents/CLI), `utility` (platform plumbing), `service` (long-running).

**Extension builder contract:**
- Declare connections in TOML → platform handles credentials ([Connections Spec](spec-connections.md))
- Use `get_credential()` for auth → never hardcode tokens
- Use `LockedJsonFile` or `get_state_store()` for state → never raw `json.loads` ([State Spec](spec-agent-state-management.md))

---

## Integration Points

**Authoritative spec:** [Connections Spec](spec-connections.md)

Five integration patterns, unified under the **Connection** abstraction:

| Pattern | Examples | Status |
|---------|----------|--------|
| **API** | Anthropic, GitHub, GitLab, MS Graph | ✅ Working |
| **Browser** | Teams (Playwright), OneDrive | ✅ Built |
| **MCP** | Claude Code ↔ Neut tools (stdio) | ✅ Working |
| **CLI** | Ollama, Pandoc, kubectl, git | ✅ Working |
| **A2A** | Inter-facility agent federation | 📋 Designed |

Credential resolution: env var → settings → keychain → file → browser → prompt.

---

## Model Corral

**Authoritative spec:** [Model Corral Spec](spec-model-corral.md)

Model Corral is NeutronOS's registry for physics simulation models and trained ROMs:

| Component | Description | Status |
|-----------|-------------|--------|
| **Model registry** | PostgreSQL metadata + S3 object storage | 📋 Spec'd |
| **Manifest schema** | `model.yaml` validation (JSON Schema) | 📋 Spec'd |
| **ROM extension** | Training provenance, tier assignment | 📋 Spec'd |
| **Git sync** | Optional bidirectional Git integration | 📋 Spec'd |
| **Validation framework** | Schema, file, syntax checking | 📋 Spec'd |
| **CLI** | `neut model` (search, add, pull, validate) | 📋 Spec'd |
| **Web UI** | Catalog browser, upload wizard, lineage graph | 📋 Spec'd |

**Model types:** High-fidelity input decks (MCNP, VERA, SAM, Griffin), trained ROMs (WASM, ONNX), validation datasets, CoreForge configurations.

**Access tiers:** `public` (open benchmarks) and `facility` (facility-specific). Per Nick Luciano, physics models don't require export control classification — tiers are for deployment visibility management.

---

## Digital Twin Hosting

**Authoritative spec:** [Digital Twin Hosting Spec](spec-digital-twin-architecture.md)

Digital Twin Hosting provides execution infrastructure for computational models:

| Component | Description | Status |
|-----------|-------------|--------|
| **ROM tiers** | ROM-1 (10Hz), ROM-2 (5-20s), ROM-3 (<5min), ROM-4 (minutes) | 📋 Spec'd |
| **Shadow** | Calibrated high-fidelity physics code execution | 📋 Spec'd |
| **WASM runtime** | Uniform ROM execution with capability-based security | 📋 Spec'd ([ADR-008](../requirements/adr-008-wasm-extension-runtime.md)) |
| **Run tracking** | `dt_runs`, `dt_run_states`, `dt_run_validations` | 📋 Spec'd |
| **Provider interface** | Reactor-specific physics adapters | 📋 Spec'd |
| **Validation framework** | ROM vs Shadow, prediction vs measurement | 📋 Spec'd |
| **CLI** | `neut twin` (run, shadow, rom-train, compare) | 📋 Spec'd |
| **Web UI** | Run dashboard, comparison view, Shadow manager | 📋 Spec'd |

**Use cases:**
1. Real-time display (<100ms, ROM-1)
2. Live activation / control loop (<100ms, ROM-1)
3. Comms & Viz / interactive (5-20s, ROM-2)
4. Experiment planning (<5 min, ROM-3)
5. Operational planning (minutes, ROM-4)
6. Analysis & V&V (offline, Shadow)

Digital twin capabilities are planned for post-MVP deployment. Model Corral and DT Hosting are designed together as a unified architecture — models stored in Corral, executed via DT Hosting.

**Autonomy Target:** NAL-2 (Advisory) — operator suggestions without automated execution. Progression to higher autonomy levels (NAL-3+) requires validated "progression proofs" demonstrating safety at each level. See [DT Hosting Spec §15](spec-digital-twin-architecture.md#15-autonomy-progression-framework) for the Nuclear Autonomy Levels framework.

---

## Architecture Decision Records

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](../requirements/adr-001-polyglot-monorepo-bazel.md) | Monorepo (Bazel dropped → pure Python) | Accepted (modified) |
| [ADR-002](../requirements/adr-002-hyperledger-fabric-multi-facility.md) | Hyperledger Fabric for tamper-proof audit | Accepted |
| [ADR-003](../requirements/adr-003-lakehouse-iceberg-duckdb-superset.md) | Iceberg + DuckDB lakehouse | Accepted |
| [ADR-004](../requirements/adr-004-infrastructure-terraform-k8s-helm.md) | Terraform + K8S + Helm | Accepted |
| [ADR-005](../requirements/adr-005-meeting-intake-pipeline.md) | Meeting intake → Signal pipeline | Accepted |
| [ADR-006](../requirements/adr-006-mcp-agentic-access.md) | MCP server for IDE integration | Accepted |
| [ADR-007](../requirements/adr-007-streaming-first-architecture.md) | Streaming-first architecture | Accepted |
| [ADR-008](../requirements/adr-008-wasm-extension-runtime.md) | WASM surrogate runtime | Proposed |
| [ADR-009](../requirements/adr-009-promote-media-internalize-db.md) | Media Library + internalize DB | Accepted |
| [ADR-010](../requirements/adr-010-cli-architecture.md) | CLI as agentic terminal (noun-verb, slash commands, terminal monitoring) | Accepted |

---

## Platform Positioning

### Why Open Lakehouse (Not Databricks/Snowflake)

| Factor | Managed Platform | Open Lakehouse |
|--------|-----------------|----------------|
| **Data sovereignty** | Vendor control plane has access | Full control over data residency |
| **Nuclear compliance** | Export control complexity | On-premise, air-gappable |
| **Cost trajectory** | DBU pricing scales with usage | Fixed TACC allocation; marginal cost ~$0 |
| **Customization** | Limited to platform APIs | Full access for digital twin integration |
| **Lock-in risk** | High switching costs | Portable Iceberg format |

Detailed analysis: [Platform Comparison](../research/platform-comparison-databricks.md)

### Relationship to INL DeepLynx

DeepLynx and NeutronOS are **complementary peer platforms**, not competing:

- **DeepLynx** optimizes for relationship traversal (graph-based engineering data)
- **NeutronOS** optimizes for time-series analytics and agent-driven workflows

Integration via shared identifiers and APIs. Detailed analysis: [DeepLynx Assessment](../research/deeplynx-assessment.md)

---

## Research Documents

| Document | Topic |
|----------|-------|
| [State Backend Whitepaper](../research/whitepaper-state-backend-comparison.md) | Flat file vs PostgreSQL: benchmarks, token efficiency, failure modes |
| [Platform Comparison](../research/platform-comparison-databricks.md) | NeutronOS vs Databricks positioning |
| [DeepLynx Assessment](../research/deeplynx-assessment.md) | INL DeepLynx peer-platform analysis |
| [User Personas](../research/user-personas.md) | Operator, researcher, admin personas |

---

## Test Coverage

| Area | Tests | Status |
|------|-------|--------|
| Signal pipeline | 372 | ✅ Passing |
| Publisher | 237 | ✅ Passing |
| M-O + retention | 70 | ✅ Passing |
| State management | 64 | ✅ Passing |
| Routing + red-team | 124 | ✅ Passing |
| RAG | 36 | ✅ Passing |
| Infrastructure | 38 | ✅ Passing |
| **Total** | **~1,600** | **✅ All passing (v0.4.0)** |

Red-team framework: `tests/routing/export_controlled_prompts.txt` + `public_prompts.txt` → parametrized classifier accuracy tests across all sensitivity levels.

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| 0.1.0 | 2026-01 | Initial platform: docflow, CLI, GitLab sensor |
| 0.2.0 | 2026-02 | Extension system, demo, chat TUI, setup wizard |
| 0.3.0 | 2026-02 | Extension refactor, publisher consolidation, review framework |
| 0.3.2 | 2026-03 | Export control router, settings, RAG, model routing |
| **0.4.0** | **2026-03** | **State management, hybrid backend, routing Phase 2a, UX overhaul, sense→signal rename** |
