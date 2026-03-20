# NeutronOS 2026 OKRs

> **Last Updated:** March 20, 2026
> **Planning Horizon:** Q2-Q4 2026 (Q1 complete)
> **Aligned With:** [Executive PRD](prd-executive.md), [Digital Twin Hosting PRD](prd-digital-twin-hosting.md), [Model Corral PRD](prd-model-corral.md), [RAG PRD](prd-rag.md), [Prompt Registry PRD](prd-prompt-registry.md)
>
> **Major update (2026-03-20):** Intelligence Platform objectives added; INL federated learning partnership incorporated; Rascal EC staging (ADR-013) added; implementation priority list expanded with v0.4.3 and v0.4.4 milestones.

---

## PRD → OKR Linkage Matrix

| PRD | OKR Objective | Implementation Status |
|-----|---------------|----------------------|
| [Executive PRD](prd-executive.md) | All | ✅ Platform shipped (v0.4.1) |
| [CLI PRD](prd-neut-cli.md) | All | ✅ Shipped |
| [Agent Platform PRD](prd-agents.md) | O1, O5, O6, O7, **O9** | ✅ Platform shipped; domain agents + intelligence layer planned |
| [Agent State Mgmt PRD](prd-agent-state-management.md) | O1, O5 | ✅ Shipped |
| [Publisher PRD](prd-publisher.md) | O7 | ✅ Shipped |
| [Connections PRD](prd-connections.md) | O1, O3, O7 | ✅ Active (v0.4.2 shipped) |
| [RAG PRD](prd-rag.md) | **O9**, O1 | 📋 Spec'd |
| [Prompt Registry PRD](prd-prompt-registry.md) | **O9** | 📋 Spec'd |
| [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) | **O1**, O4, O8 | 📋 Spec'd |
| [Model Corral PRD](prd-model-corral.md) | **O2** | 📋 Spec'd |
| [Data Platform PRD](prd-data-platform.md) | **O3**, O1, O4 | 📋 Spec'd |
| [Reactor Ops Log PRD](prd-reactor-ops-log.md) | **O5** | 🔲 Not started |
| [Compliance Tracking PRD](prd-compliance-tracking.md) | **O5** | 🔲 Not started |
| [Scheduling System PRD](prd-scheduling-system.md) | O5, O6 | 🔲 Not started |
| [Experiment Manager PRD](prd-experiment-manager.md) | O5, O7 | 🔲 Not started |
| [Analytics Dashboards PRD](prd-analytics-dashboards.md) | O1, O3, O5 | 🔲 Not started |
| [Medical Isotope PRD](prd-medical-isotope.md) | **O6** | 🔲 Not started |
| [Security & Access Control PRD](prd-security.md) | O7, O8 | 🔲 Not started |
| [Media Library PRD](prd-media-library.md) | O7 | 🔲 Not started |

**PRDs not linked to any OKR:** None — all PRDs map to at least one objective.

---

## Immediate Priorities (Q2 2026)

These are the concrete deliverables that matter most in the next 6-8 weeks:

### 1. Ondrej's Deployment — Neut + Qwen on Rascal + RAG
**Who:** Ondrej (first external operator user)
**What:** Neut running in VS Code, routing `neut chat` to Qwen on Rascal, with a loaded RAG corpus answering real questions.
**Why now:** Validates the self-hosted LLM path end-to-end on real hardware. First external user deployment. Shows the product works outside Ben's laptop.
**Blockers to clear:** Rascal k3d + containerd setup (ADR-013), Qwen provider configured in models.toml, RAG corpus loaded (community v1 or facility docs), VS Code extension working.

### 2. Model Corral v1 — Nick and Cole
**Who:** Nick and Cole (researchers at NETL)
**What:** `neut model` CLI working — register, search, pull physics models. Basic Model Corral schema deployed.
**Why now:** Nick and Cole have immediate need. Model Corral is already spec'd. This is spec → implementation, not new design work.
**Blockers to clear:** model.yaml manifest schema, PostgreSQL schema migration, `neut model search/add/pull/validate` CLI commands.

### 3. Intelligence Platform Phase 1 — Interaction Log + Prompt Registry
**Who:** Platform (enables knowledge maturity pipeline)
**What:** Interaction log writing on every completion, feedback signals, prompt template registry shipped.
**Why now:** Every day without the interaction log is interaction data we're not capturing. The knowledge flywheel can't start spinning until logging is in place.

---

## Current State Summary (March 2026)

### ✅ Shipped (Q4 2025 - Q1 2026)

| Component | Status | Description |
|-----------|--------|-------------|
| **LLM Gateway** | ✅ Shipped | Multi-provider routing with export control classification |
| **Signal Agent** | ✅ Shipped | Voice/Teams/GitLab → extractors → correlator → synthesizer |
| **Chat Agent** | ✅ Shipped | Interactive LLM with tool use, RAG, per-turn routing |
| **Publisher** | ✅ Shipped | Markdown → generate → publish to 19 endpoints |
| **RAG** | ✅ Shipped | Three-tier corpus (community/org/personal), pgvector |
| **M-O Agent** | ✅ Shipped | Resource steward, scratch lifecycle, retention |
| **State Store** | ✅ Shipped | Hybrid file + PostgreSQL backend |
| **CLI Framework** | ✅ Shipped | `neut <noun> <verb>` with extension discovery |
| **Connections** | ✅ Shipped | Connection registry, credential resolution, managed service lifecycle (v0.4.2) |
| **Demo** | ✅ Shipped | 9-act guided walkthrough ("Jay's Story") |

### 📋 Spec'd (Ready for Implementation)

| Component | PRD | Spec | Target |
|-----------|-----|------|--------|
| **Prompt Template Registry** | [PRD](prd-prompt-registry.md) | [Spec](../tech-specs/spec-prompt-registry.md) | Q2 2026 |
| **Agentic RAG + Knowledge Maturity** | [PRD](prd-rag.md) | [Spec §14](../tech-specs/spec-rag-architecture.md) + [Maturity Spec](../tech-specs/spec-rag-knowledge-maturity.md) | Q2-Q3 2026 |
| **Community Corpus Federation** | [PRD](prd-rag.md) | [Spec](../tech-specs/spec-rag-community.md) | Q3-Q4 2026 |
| **Model Corral** | [PRD](prd-model-corral.md) | [Spec](../tech-specs/spec-model-corral.md) | Q2 2026 |
| **Digital Twin Hosting** | [PRD](prd-digital-twin-hosting.md) | [Spec](../tech-specs/spec-digital-twin-architecture.md) | Q2-Q4 2026 |
| **Data Lakehouse** | [PRD](prd-data-platform.md) | [Spec](../tech-specs/spec-data-architecture.md) | Q2 2026 |
| **Rascal EC Staging** | [ADR-013](adr-013-rascal-ec-staging.md) | `infra/environments/rascal/` | Q2 2026 |

---

## Objective 1: Digital Twin Foundation
> Establish infrastructure for ROM execution and Shadow simulations

**Aligns with:** [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) Phases 1-2

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Run tracking schema deployed | PostgreSQL tables live | Q2 | 🔲 |
| `neut twin run/status` CLI working | Commands operational | Q2 | 🔲 |
| Shadow automation for TRIGA NETL | Nightly runs | Q2 | 🔲 |
| ROM-2 inference operational | <20s latency | Q3 | 🔲 |
| Prediction vs measured comparison | Dashboard live | Q3 | 🔲 |

### Supporting Work
- [ ] Define `dt_runs`, `dt_run_states`, `dt_run_validations` schema
- [ ] Integrate SLURM job submission for secure HPC
- [ ] Complete WASM surrogate runtime (from spike)
- [ ] Build ROM-2 training pipeline
- [ ] Create basic Superset dashboards for validation

---

## Objective 2: Model Registry (Model Corral)
> Physics models versioned, searchable, validated, and federation-ready

**Aligns with:** [Model Corral PRD](prd-model-corral.md)

> **Near-term: Nick and Cole (NETL)** — Nick and Cole are actively waiting on `neut model search/add/pull`. This is not a future roadmap item; it is an immediate user need. Ship the CLI and schema first, then the web catalog.

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| `neut model` CLI working | search/add/pull/validate — **Nick and Cole unblocked** | Q2 | 🔲 |
| Model Corral schema deployed | PostgreSQL + S3 | Q2 | 🔲 |
| TRIGA models migrated | 10+ models in registry | Q2 | 🔲 |
| Web catalog UI | Browse + upload wizard | Q3 | 🔲 |
| Git sync operational | Bidirectional with lab repos | Q3 | 🔲 |
| Federated model artifact support | `federation_round`, `participating_facilities`, `aggregation_method` fields in `model.yaml`; INL LDRD models registerable | Q3 | 🔲 |

### Supporting Work
- [ ] Implement `model.yaml` manifest schema validation
- [ ] Build ROM extension fields (training provenance, tier)
- [ ] Create validation framework (schema, file, syntax checks)
- [ ] Integrate with RAG for model documentation search
- [ ] Add federated model fields to `model.yaml` schema and validation

---

## Objective 3: Data Platform Maturity
> Bronze/Silver/Gold lakehouse operational with dbt transforms

**Aligns with:** [Data Platform PRD](prd-data-platform.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Iceberg tables operational | Bronze layer populated | Q2 | 🔲 |
| dbt models for TRIGA data | Silver layer transforms | Q2 | 🔲 |
| Dagster orchestration | Scheduled pipelines | Q3 | 🔲 |
| Streaming ingest (Redpanda) | <10s latency | Q3 | 🔲 |
| Gold layer KPIs | Superset dashboards | Q3 | 🔲 |

### Supporting Work
- [ ] Deploy MinIO for object storage
- [ ] Create dbt project structure
- [ ] Define Bronze schemas for sensor data, ops logs, experiments
- [ ] Build Silver transforms for data quality
- [ ] Configure Dagster schedules and sensors

---

## Objective 4: Real-Time Predictions (ROM-1)
> Control room display shows ROM predictions alongside sensors

**Aligns with:** [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) Phase 3

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| ROM-1 inference <100ms | 10 Hz update rate | Q4 | 🔲 |
| Streaming integration | Redpanda → ROM-1 | Q4 | 🔲 |
| WebSocket endpoint | Real-time predictions | Q4 | 🔲 |
| Control room display | Sensor + prediction overlay | Q4 | 🔲 |
| NAL-1 progression proof | Accuracy validated for N hours | Q4 | 🔲 |

### Supporting Work
- [ ] Optimize ROM-1 WASM module for latency
- [ ] Build WebSocket server for real-time push
- [ ] Integrate with TRIGA DT Website `/simulator`
- [ ] Create divergence alerting system
- [ ] Document uncertainty bounds

---

## Objective 5: Operations & Compliance
> Reactor ops log and compliance reporting automated

**Aligns with:** [Reactor Ops Log PRD](prd-reactor-ops-log.md), [Compliance Tracking PRD](prd-compliance-tracking.md), [Scheduling System PRD](prd-scheduling-system.md), [Experiment Manager PRD](prd-experiment-manager.md), [Analytics Dashboards PRD](prd-analytics-dashboards.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Console check digitization | Paper → digital | Q2 | 🔲 |
| Shift handoff workflow | Structured handoffs | Q3 | 🔲 |
| Compliance report generator | One-click NRC reports | Q3 | 🔲 |
| Anomaly detection prototype | Automated flagging | Q4 | 🔲 |

### Supporting Work
- [ ] Design console check UI (per [spec-console-check-ui-mockups.md](../tech-specs/spec-console-check-ui-mockups.md))
- [ ] Build shift handoff templates
- [ ] Define compliance evidence schema
- [ ] Research anomaly detection approaches

---

## Objective 6: Medical Isotope Automation
> Reduce isotope request-to-delivery coordination overhead

**Aligns with:** [Medical Isotope PRD](prd-medical-isotope.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Current workflow documented | As-is map complete | Q2 | 🔲 |
| Digital request intake | Form replaces phone calls | Q3 | 🔲 |
| Automated ops package | DT generates config | Q3 | 🔲 |
| SLA tracking | Order status visible | Q4 | 🔲 |

### Current State Problem
When a Houston cancer clinic needs isotopes:
1. Hospital calls Dr. Charlton (NETL Director) directly
2. Dr. Charlton assigns work to available student/professor
3. Assignee manually reviews recent reactor ops
4. Assignee runs new simulations for criticality data
5. Results compiled into Word doc with bullet points
6. Word doc delivered via phone to operators next morning

**Goal:** Digital twin generates ops package automatically from request parameters.

---

## Objective 7: Community & Adoption
> Researchers and students actively using NeutronOS

**Aligns with:** [Publisher PRD](prd-publisher.md), [Security & Access Control PRD](prd-security.md), [Media Library PRD](prd-media-library.md), [Connections PRD](prd-connections.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Demo deployed publicly | Web-accessible | Q2 | 🔲 |
| Documentation site | Searchable docs | Q2 | 🔲 |
| 2+ courses using tools | ME 390G, ME 361E | Q3 | 🔲 |
| User feedback mechanism | In-app feedback | Q3 | 🔲 |
| 10+ active weekly users | WAU metric | Q4 | 🔲 |

### Supporting Work
- [ ] Deploy demo environment (non-VPN accessible)
- [ ] Create onboarding tutorials
- [ ] Meet with course instructors about integration
- [ ] Implement analytics (Plausible or PostHog)

---

## Objective 8: Multi-Facility Foundation + Federation
> Architecture ready for second reactor deployment; INL partnership grounded in working infrastructure

**Aligns with:** [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) Phase 4

The INL federated learning LDRD (PI: Jieun Lee) establishes UT-Austin, OSU, and INL NRAD as the founding federation. NeutronOS community corpus federation is the knowledge-layer complement to that model-training collaboration. Before OSU or INL can trust NeutronOS export control claims, the Rascal EC staging environment must validate the dual-store architecture end-to-end.

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Reactor provider abstraction | Generic interface | Q4 | 🔲 |
| Rascal server live — Ondrej deployment path validated | k3d + containerd deployed, Qwen running | Q2 | 🔲 |
| VS Code → Neut → Qwen (Rascal) → RAG path exercised end-to-end | Ondrej running `neut chat` in VS Code with RAG responses | Q2 | 🔲 |
| INL LDRD co-investigator commitment confirmed | Verbal → formal | Q2 | 🔲 |
| Community corpus federation v1 (bilateral UT ↔ OSU) | Facts flowing between 2 sites | Q4 | 🔲 |
| Deployment playbook documented | Rascal → TACC path documented | Q3 | 🔲 |
| 1+ external facility expressing interest | Letter of intent | Q4 | 🔲 |

### Supporting Work
- [ ] Abstract TRIGA-specific code into provider
- [ ] Document reactor provider contract
- [ ] Set up k3d + containerd on Rascal (ADR-013)
- [ ] Create `infra/environments/rascal/` Terraform target
- [ ] Validate EC dual-store architecture on Rascal hardware
- [ ] Identify potential pilot facilities beyond OSU/INL
- [ ] Cost model for deployment

---

## Objective 9: Intelligence Platform
> Build the compound knowledge flywheel: every interaction makes the system smarter

**Aligns with:** [RAG PRD](prd-rag.md), [Prompt Registry PRD](prd-prompt-registry.md), [Agent Platform PRD](prd-agents.md)

The intelligence platform closes the loop between user interactions and corpus quality. The interaction log captures every RAG completion tuple. The knowledge maturity pipeline evaluates those interactions and crystallizes recurring validated facts via EVE. The prompt registry ensures all agent prompts are versioned, auditable, and cache-efficient. Together these form a self-improving knowledge flywheel that compounds with usage rather than degrading.

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Interaction log deployed and writing on every completion | 100% completion coverage | Q2 | 🔲 |
| Agentic RAG (heuristic query planner + context evaluator) | ≥70% queries resolved single-pass | Q2 | 🔲 |
| Prompt Template Registry shipped, EC preamble migrated | All agent prompts versioned | Q2 | 🔲 |
| Prompt cache hit ratio ≥60% for active sessions | Measured via `axiom_llm_cache_hit_ratio` | Q3 | 🔲 |
| EVE crystallization producing approved facts | ≥5 approved community facts/week | Q3 | 🔲 |
| M-O knowledge sweep operational | Weekly sweeps with ≥90% GREEN/YELLOW rate | Q3 | 🔲 |
| Community corpus federation v1 (UT ↔ OSU bilateral) | Facts flowing between 2 sites | Q4 | 🔲 |
| Observability dashboard live | All 35 metrics visible | Q3 | 🔲 |

### Supporting Work
- [ ] Deploy `interaction_log` schema (Alembic migration)
- [ ] Write `interaction_log` record on every RAG completion
- [ ] Implement feedback signal capture (thumbs up/down in `neut chat`)
- [ ] Implement heuristic query planner in `store.py` (is retrieval needed? which tier/scope?)
- [ ] Implement heuristic context evaluator in `store.py` (sufficient context? or retrieve again?)
- [ ] Ship `TemplateRegistry` + `neut prompt` CLI
- [ ] Migrate `_EC_HARDENED_PREAMBLE` to versioned template
- [ ] Wire `cache_control` headers in `gateway._build_messages()`
- [ ] Ship EVE crystallization pipeline (Evaluator-Optimizer)
- [ ] Create `knowledge_facts` table + schema
- [ ] Ship GREEN/YELLOW/RED trust gradient in promotion policy
- [ ] Ship M-O knowledge maturity sweep
- [ ] Ship `neut rag review` CLI
- [ ] Ship `neut metrics` CLI from log aggregation
- [ ] Build federation sync v1 pull endpoint

---

## Implementation Priority List

> Updated 2026-03-20. Order reflects dependency chain and stakeholder value.

### v0.4.2: Connections ✅ SHIPPED

- [x] Connection registry + credential resolution (env → settings → file)
- [x] `neut connect` CLI with tab completion, health checks, JSON
- [x] Declare `[[connections]]` in all builtin extension manifests (11 connections)
- [x] Integrate connections into `neut status`
- [x] Capabilities (read/write), usage tracking, throttle detection
- [x] Adaptive rate limiter (learns from API response headers)
- [x] Managed service lifecycle (launchd/systemd/Windows)
- [x] D-FIB self-healing for connection failures
- [x] Embedding provider fallback (OpenAI → Ollama → skip)
- [x] Migrate extractors to `get_credential()` (8 files)
- [x] Auth method negotiation (browser, graph_api, manual)
- [x] Playwright browser auth with session persistence
- [x] Provider preference chain (`routing.prefer_provider`)
- [x] VPN failure guidance (configurable per connection)
- [x] `neut connect qwen-rascal` configures EC routing
- [x] Extension metadata fully documented (ConnectionDef docstring, contract docs, scaffold)

### v0.4.3: Intelligence Platform — Phase 1 (Q2 2026)

- [ ] Interaction log schema + Alembic migration
- [ ] Write `interaction_log` on every RAG completion
- [ ] Feedback signal capture (thumbs up/down in `neut chat`)
- [ ] Heuristic query planner (is retrieval needed? which tier/scope?)
- [ ] Heuristic context evaluator (sufficient context? or retrieve again?)
- [ ] Prompt Template Registry + `neut prompt` CLI
- [ ] Migrate `_EC_HARDENED_PREAMBLE` to versioned template
- [ ] `neut metrics` CLI from log aggregation

### v0.4.4: Rascal Server + Ondrej Deployment (Q2 2026)

- [ ] k3d + containerd install on Rascal
- [ ] Qwen provider configured in `llm-providers.toml` pointing to Rascal
- [ ] Community RAG corpus (or facility docs) loaded on Rascal
- [ ] VS Code → Neut → Qwen → RAG path validated with Ondrej

### v0.5.0: Security — Credential Providers + Routing Profiles

- [ ] OS Keychain credential provider (macOS/Linux/Windows)
- [ ] Credential metadata (saved_at, expires_at, last_verified)
- [ ] `neut connect --migrate` (.env → Keychain)
- [ ] M-O credential expiry watch
- [ ] EVE secret leak scanning
- [ ] Per-agent routing profiles (chat, extraction, diagnosis, embedding, classification)

### v0.5.x: Security — Identity (Ory Kratos)

- [ ] Deploy Kratos as managed service
- [ ] `neut login` / `neut logout` / `neut whoami`
- [ ] Local registration + TOTP MFA
- [ ] OAuth (Google, Microsoft, GitHub, GitLab) via Kratos
- [ ] Session management + identity in agent context

### v0.5.5: Intelligence Platform — Phase 2 (Q3 2026)

- [ ] EVE crystallization pipeline (Evaluator-Optimizer)
- [ ] `knowledge_facts` table + schema
- [ ] GREEN/YELLOW/RED trust gradient in promotion policy
- [ ] M-O knowledge maturity sweep
- [ ] `neut rag review` CLI
- [ ] Prompt `cache_control` headers wired (requires prompt registry)
- [ ] `neut eval regression` CLI

### v0.6.0: Security — Authorization (OpenFGA) + Connections Phase 3

- [ ] Deploy OpenFGA as managed service
- [ ] Kratos → OpenFGA webhook bridge
- [ ] Connection-level access control (who can use which provider)
- [ ] Document/corpus-level access control (who can query which RAG corpus)
- [ ] LDAP/AD, OIDC, SAML via Kratos
- [ ] `neut connect` shows authorization status per user

### v0.6.x: Security — EC Defense Layers

- [ ] Chunk sanitization, response scanning, prompt hardening
- [ ] Security audit log (PostgreSQL + HMAC)
- [ ] `neut doctor --security` + red-team suite (promptfoo)

### v0.7.0: Security — Vault + Rotation

- [ ] VaultProvider for production deployments
- [ ] `neut connect --migrate --target vault`
- [ ] Automatic credential rotation

### v0.7.x+: Reactor Operations (Nick & Cole focus)

- [ ] Reactor Ops Log (console checks, shift handoffs)
- [ ] Compliance Tracking (30-min check enforcement, NRC evidence)
- [ ] Data Platform (Iceberg, dbt, Bronze/Silver layers)
- [ ] Scheduling System

### v0.8.0: Digital Twin Foundation

- [ ] Model Corral (`neut model` CLI)
- [ ] DT run tracking schema
- [ ] Shadow automation for TRIGA

---

## Quarterly Roadmap Summary

### Q2 2026: Intelligence Platform Phase 1 + Rascal Staging + Security Routing Profiles
**Theme:** Intelligence Platform Phase 1 + Rascal staging + Security routing profiles

- Ship interaction log, query planner, context evaluator (v0.4.3)
- Ship Prompt Template Registry + `neut prompt` CLI
- Deploy Rascal k3d + containerd, validate EC dual-store (v0.4.4)
- Ship Security credential providers + routing profiles (v0.5.0)
- Deploy Iceberg + dbt Bronze/Silver layers
- Ship Model Corral with `neut model` CLI
- Confirm INL LDRD co-investigator role formally
- Deploy public demo environment

### Q3 2026: Intelligence Platform Phase 2 + ROM-2 + Compliance
**Theme:** Intelligence Platform Phase 2 + ROM-2 + Compliance

- Ship EVE crystallization pipeline + knowledge maturity sweep (v0.5.5)
- Ship `neut rag review`, `neut eval regression` CLIs
- ROM-2 inference with <20s latency
- Prediction vs measured dashboards
- dbt Gold layer KPIs
- Redpanda streaming ingest
- Compliance report generator
- Digital isotope request intake
- Deployment playbook (Rascal → TACC path)
- Flower AI integration scoped (if LDRD confirmed)

### Q4 2026: Real-Time + Community Corpus Federation v1 + Multi-Facility Prep
**Theme:** Real-Time + Community corpus federation v1 + Multi-facility prep

- ROM-1 at 10 Hz in control room display
- NAL-1 progression proof (accuracy validation)
- Anomaly detection prototype
- Community corpus federation v1 (UT ↔ OSU bilateral)
- Federated model artifact support (INL LDRD models registerable)
- Reactor provider abstraction
- Facility pilot engagement (1+ letter of intent)
- 10+ active weekly users

---

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| WASM runtime performance | ROM-1 misses latency target | Prototype early, optimize iteratively |
| Secure HPC access (SLURM) | Shadow runs blocked | Work with TACC on authentication |
| Streaming complexity (Redpanda) | Delayed real-time features | Start with batch, add streaming incrementally |
| ROM accuracy | Can't achieve NAL-1 proof | Increase training data, improve models |
| Course instructor buy-in | Low adoption | Early engagement, show value first |
| INL LDRD funding not confirmed | Federation scope unclear | Confirm co-PI role and UT contribution scope before building federation sync |
| Rascal hardware access | EC staging blocked | Coordinate GPU scheduling with NETL staff early |
| EVE crystallization quality | Low-trust facts flood corpus | Require human approval gate before community tier promotion |
| Ondrej's availability for first deployment validation | Medium | Schedule with Ben early; don't let this slip to end of quarter |

---

## INL Partnership Milestones

The INL federated learning LDRD (PI: Jieun Lee, INL NRAD) proposes UT-Austin, OSU, and INL NRAD as founding members of a federated nuclear AI consortium. NeutronOS is positioned as the facility-side platform for knowledge management and model registry; the LDRD focuses on federated model training (Flower AI integration path). These milestones track the partnership arc independently of the main implementation priority list.

| Milestone | Target | Notes |
|-----------|--------|-------|
| Confirm co-investigator role formally | Q2 2026 | Reply to Jieun Lee; align on UT contribution scope and deliverables |
| Align Model Corral schema with LDRD deliverables | Q2 2026 | Add `federation_round`, `participating_facilities`, `aggregation_method` to `model.yaml` |
| Rascal validates EC architecture | Q2 2026 | Required before OSU/INL can trust our EC compliance claims |
| Community corpus federation v1 (UT ↔ OSU bilateral) | Q4 2026 | First bilateral knowledge sharing between founding members |
| LDRD proposal submission | TBD — follow INL timeline | Ben as external co-PI |
| Flower AI integration scoped | Q3 2026 | Depends on LDRD funding confirmation |

---

## Review Schedule

| Cadence | Activity |
|---------|----------|
| Weekly | Implementation progress check |
| Monthly | KR scoring, blocker review |
| Quarterly | OKR retrospective, stakeholder update |

---

## Related Documents

### PRDs
- [Executive PRD](prd-executive.md) — Product vision
- [CLI PRD](prd-neut-cli.md) — CLI architecture
- [Agent Platform PRD](prd-agents.md) — Agent capabilities
- [Agent State Mgmt PRD](prd-agent-state-management.md) — State store design
- [Publisher PRD](prd-publisher.md) — Document lifecycle
- [Connections PRD](prd-connections.md) — Credential resolution
- [RAG PRD](prd-rag.md) — Retrieval-augmented generation
- [Prompt Registry PRD](prd-prompt-registry.md) — Versioned prompt templates
- [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) — DT execution infrastructure
- [Model Corral PRD](prd-model-corral.md) — Physics model registry
- [Data Platform PRD](prd-data-platform.md) — Lakehouse architecture
- [Reactor Ops Log PRD](prd-reactor-ops-log.md) — Console operations
- [Compliance Tracking PRD](prd-compliance-tracking.md) — Regulatory monitoring
- [Scheduling System PRD](prd-scheduling-system.md) — Resource scheduling
- [Experiment Manager PRD](prd-experiment-manager.md) — Sample lifecycle
- [Analytics Dashboards PRD](prd-analytics-dashboards.md) — Visualization
- [Medical Isotope PRD](prd-medical-isotope.md) — Isotope production
- [Security & Access Control PRD](prd-security.md) — Auth & permissions
- [Media Library PRD](prd-media-library.md) — Media asset management

### Tech Specs
- [Executive Tech Spec](../tech-specs/spec-executive.md) — Implementation status
- [Digital Twin Architecture](../tech-specs/spec-digital-twin-architecture.md)
- [Model Corral Spec](../tech-specs/spec-model-corral.md)
- [Data Architecture Spec](../tech-specs/spec-data-architecture.md)
- [Agent Architecture Spec](../tech-specs/spec-agent-architecture.md)
- [Connections Spec](../tech-specs/spec-connections.md)
- [RAG Architecture Spec](../tech-specs/spec-rag-architecture.md)
- [RAG Knowledge Maturity Spec](../tech-specs/spec-rag-knowledge-maturity.md)
- [RAG Community Federation Spec](../tech-specs/spec-rag-community.md)
- [Prompt Registry Spec](../tech-specs/spec-prompt-registry.md)
- [Observability Spec](../tech-specs/spec-observability.md)

### ADRs
- [ADR-011: Concurrent File Writes](adr-011-concurrent-file-writes.md)
- [ADR-012: Provider Identity](adr-012-provider-identity.md)
- [ADR-013: Rascal EC Staging](adr-013-rascal-ec-staging.md)
