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
│  Tools:     pub  rag  db  demo  repo                                 │
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

## Extension Primitives

NeutronOS inherits the four extension kinds from Axiom (see [Axiom Executive Spec § Extension Primitives](https://github.com/…/axiom/docs/tech-specs/spec-executive.md#extension-primitives)). All shipped Axiom agents, tools, utilities, and services are available in NeutronOS. This section documents the NeutronOS-specific extensions and nuclear-domain specializations layered on top.

### Axiom Agents — Shipped in NeutronOS

| Archetype | Internal Name | CLI Noun | Spec | Status | Nuclear Specialization |
|-----------|--------------|----------|------|--------|----------------------|
| **Signal** | EVE | `neut signal` | [Agent Architecture](spec-agent-architecture.md) | ✅ Shipped | Nuclear signal sources (ops log events, reactor alarms, HP surveys) |
| **Assistant** | Neut | `neut chat` | [Agent Architecture](spec-agent-architecture.md) | ✅ Shipped | Nuclear RAG corpus, reactor-aware context |
| **Steward** | M-O | `neut mo` | [State Management Spec](spec-agent-state-management.md) | ✅ Shipped | NRC retention policies (7-year archive) |
| **Diagnostics** | D-FIB | `neut doctor` | — | 🔲 Partial | Nuclear system health checks |
| **Publisher** | PR-T | `neut pub` | [Publisher Spec](spec-publisher.md) | ✅ Shipped | NRC evidence packages, regulatory reports |

### Axiom Agents — Planned for NeutronOS

| Archetype | CLI Noun | Nuclear Specialization |
|-----------|----------|----------------------|
| **Analyst** | `neut analyze` | Reactor anomaly detection, fuel burnup trending, sensor drift analysis |
| **Planner** | `neut plan` | Experiment scheduling, irradiation planning, isotope production coordination |
| **Compliance** | `neut comply` | NRC 30-min check enforcement, training currency tracking, license condition monitoring |
| **Reviewer** | `neut review` | Ops log review, experiment authorization workflow, shift handoff validation |
| **Coach** | `neut coach` | Operator training, reactor procedure walkthroughs, competency assessment |

### Axiom Tools — Shipped & Spec'd in NeutronOS

| Tool | CLI Noun | Spec | Status | Nuclear Specialization |
|------|----------|------|--------|----------------------|
| **rag** | `neut rag` | [RAG Architecture](spec-rag-architecture.md) | ✅ Shipped | Nuclear knowledge corpus, EC-compliant |
| **db** | `neut db` | — | ✅ Shipped | — |
| **demo** | `neut demo` | — | ✅ Shipped | TRIGA-specific walkthrough ("Jay's Story") |
| **model** | `neut model` | [Model Corral Spec](spec-model-corral.md) | 📋 Spec'd | MCNP/VERA/SAM decks, trained ROMs |
| **simulate** | `neut sim` | [DT Hosting Spec](spec-digital-twin-architecture.md) | 📋 Spec'd | ROM execution, Shadow runs, SLURM job submission to TACC |

### Axiom Tools — Planned for NeutronOS

| Tool | CLI Noun | Nuclear Specialization |
|------|----------|----------------------|
| **data** | `neut data` | Nuclear Bronze/Silver/Gold schemas, reactor time-series queries |
| **export** | `neut export` | NRC evidence packages, compliance reports, data extracts |
| **audit** | `neut audit` | HMAC-chain verification for ops logs, NRC audit trail queries |
| **eval** | `neut eval` | ROM accuracy benchmarking, sensor reconciliation validation |
| **notify** | `neut notify` | 30-min check gap alerts, training expiry warnings, compliance notifications |

### Utilities — Shipped in NeutronOS

| Utility | CLI Noun | Status |
|---------|----------|--------|
| **settings** | `neut settings` | ✅ Shipped |
| **status** | `neut status` | ✅ Shipped |
| **connect** | `neut connect` | ✅ Shipped |
| **update** | `neut update` | ✅ Shipped |
| **test** | `neut test` | ✅ Shipped |
| **mirror** | `neut mirror` | ✅ Shipped (GitHub sensitivity gate) |

### Core Infrastructure

| Component | Spec | Status |
|-----------|------|--------|
| **LLM Gateway** | [Model Routing Spec](spec-model-routing.md) | ✅ Shipped |
| **Export Control Router** | [Model Routing Spec §4](spec-model-routing.md) | ✅ Shipped |
| **Hybrid State Store** | [State Management Spec](spec-agent-state-management.md) | ✅ Shipped |
| **Routing Audit Log** | [Model Routing Spec §11](spec-model-routing.md) | ✅ Shipped |
| **Provider Framework** | [ADR-012: Provider Identity](../requirements/adr-012-provider-identity.md) | ✅ Shipped |

---

## Infrastructure (Axiom Platform)

NeutronOS consumes the [Axiom platform](https://github.com/…/axiom/) for all infrastructure services. See [Axiom Executive Spec § Infrastructure Services](https://github.com/…/axiom/docs/tech-specs/spec-executive.md) for the full service inventory including:

- **Identity & Auth** (Ory Kratos, OpenFGA)
- **Object Storage** (S3-compatible, Ceph/Rook recommended)
- **Databases** (PostgreSQL 16, pgvector)
- **Streaming** (Redpanda + Flink)
- **Observability** (OpenTelemetry → Prometheus + Grafana)
- **Container Platform** (K3D local, Kubernetes production)
- **Backup, Retention & Archive** ([Axiom Data Architecture Spec § 9](https://github.com/…/axiom/docs/tech-specs/spec-data-architecture.md#9-backup-retention--archive-policy))

NeutronOS extends the base Axiom retention policy with NRC-mandatory 7-year Cold tier and indefinite Archive for safety basis documents. See [NeutronOS Data Platform PRD](../requirements/prd-data-platform.md) for nuclear-specific operational policies.

---

## Data Architecture

**Authoritative specs:**
- [Axiom Data Architecture Spec](https://github.com/…/axiom/docs/tech-specs/spec-data-architecture.md) — Generic medallion framework, Iceberg config, operational policies
- [NeutronOS Data Architecture Spec](spec-data-architecture.md) — Nuclear-specific schemas and transforms
- [NeutronOS Data Platform PRD](../requirements/prd-data-platform.md) — Nuclear Bronze/Silver/Gold table inventories

**Medallion pattern:** Bronze (raw append-only) → Silver (cleaned, validated) → Gold (aggregated, business-ready). Axiom provides the generic framework; NeutronOS defines nuclear-domain schemas (reactor time-series, ops log entries, experiments, fuel burnup, xenon dynamics, compliance summaries).

**Retention:** NRC-regulated deployments use `policy = "regulatory"` (7-year Cold + indefinite Archive). Configurable via `runtime/config/retention.yaml`. M-O enforces automatically.

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

See § Infrastructure (Axiom Platform) above for the full service inventory. NeutronOS-specific deployment targets:

| Environment | Stack | Status |
|-------------|-------|--------|
| **Private endpoint** | vLLM on Rascal (UT VPN) | ✅ Running |
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
