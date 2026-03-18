# NeutronOS 2026 OKRs

> **Last Updated:** March 18, 2026
> **Planning Horizon:** Q2-Q4 2026 (Q1 nearly complete)
> **Aligned With:** [Executive PRD](prd-executive.md), [Digital Twin Hosting PRD](prd-digital-twin-hosting.md), [Model Corral PRD](prd-model-corral.md)

---

## PRD → OKR Linkage Matrix

| PRD | OKR Objective | Implementation Status |
|-----|---------------|----------------------|
| [Executive PRD](prd-executive.md) | All | ✅ Platform shipped (v0.4.1) |
| [CLI PRD](prd-neut-cli.md) | All | ✅ Shipped |
| [Agent Platform PRD](prd-agents.md) | O1, O5, O6, O7 | ✅ Platform shipped; domain agents planned |
| [Agent State Mgmt PRD](prd-agent-state-management.md) | O1, O5 | ✅ Shipped |
| [Publisher PRD](prd-publisher.md) | O7 | ✅ Shipped |
| [Connections PRD](prd-connections.md) | O1, O3, O7 | 📋 Spec'd |
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
| **Demo** | ✅ Shipped | 9-act guided walkthrough ("Jay's Story") |

### 📋 Spec'd (Ready for Implementation)

| Component | PRD | Spec | Target |
|-----------|-----|------|--------|
| **Model Corral** | [PRD](prd-model-corral.md) | [Spec](../tech-specs/spec-model-corral.md) | Q2 2026 |
| **Digital Twin Hosting** | [PRD](prd-digital-twin-hosting.md) | [Spec](../tech-specs/spec-digital-twin-architecture.md) | Q2-Q4 2026 |
| **Data Lakehouse** | [PRD](prd-data-platform.md) | [Spec](../tech-specs/spec-data-architecture.md) | Q2 2026 |
| **Connections** | [PRD](prd-connections.md) | [Spec](../tech-specs/spec-connections.md) | Q2 2026 |

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
> Physics models versioned, searchable, and validated

**Aligns with:** [Model Corral PRD](prd-model-corral.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Model Corral schema deployed | PostgreSQL + S3 | Q2 | 🔲 |
| `neut model` CLI working | search/add/pull/validate | Q2 | 🔲 |
| TRIGA models migrated | 10+ models in registry | Q2 | 🔲 |
| Web catalog UI | Browse + upload wizard | Q3 | 🔲 |
| Git sync operational | Bidirectional with lab repos | Q3 | 🔲 |

### Supporting Work
- [ ] Implement `model.yaml` manifest schema validation
- [ ] Build ROM extension fields (training provenance, tier)
- [ ] Create validation framework (schema, file, syntax checks)
- [ ] Integrate with RAG for model documentation search

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

## Objective 8: Multi-Facility Foundation
> Architecture ready for second reactor deployment

**Aligns with:** [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) Phase 4

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Reactor provider abstraction | Generic interface | Q4 | 🔲 |
| MSR provider prototype | Second reactor type | Q4+ | 🔲 |
| Deployment playbook | Documented process | Q4 | 🔲 |
| 1+ facility expressing interest | Letter of intent | Q4 | 🔲 |

### Supporting Work
- [ ] Abstract TRIGA-specific code into provider
- [ ] Document reactor provider contract
- [ ] Identify potential pilot facilities
- [ ] Cost model for deployment

---

## Implementation Priority List

> Updated 2026-03-18. Order reflects dependency chain and stakeholder value.

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

### v0.5.0: Security — Credential Providers + Routing Profiles

- OS Keychain credential provider (macOS/Linux/Windows)
- Credential metadata (saved_at, expires_at, last_verified)
- `neut connect --migrate` (.env → Keychain)
- M-O credential expiry watch
- EVE secret leak scanning
- Per-agent routing profiles (chat, extraction, diagnosis, embedding, classification)

### v0.5.x: Security — Identity (Ory Kratos)

- Deploy Kratos as managed service
- `neut login` / `neut logout` / `neut whoami`
- Local registration + TOTP MFA
- OAuth (Google, Microsoft, GitHub, GitLab) via Kratos
- Session management + identity in agent context

### v0.6.0: Security — Authorization (OpenFGA) + Connections Phase 3

- Deploy OpenFGA as managed service
- Kratos → OpenFGA webhook bridge
- Connection-level access control (who can use which provider)
- Document/corpus-level access control (who can query which RAG corpus)
- LDAP/AD, OIDC, SAML via Kratos
- `neut connect` shows authorization status per user

### v0.6.x: Security — EC Defense Layers

- Chunk sanitization, response scanning, prompt hardening
- Security audit log (PostgreSQL + HMAC)
- `neut doctor --security` + red-team suite (promptfoo)

### v0.7.0: Security — Vault + Rotation

- VaultProvider for production deployments
- `neut connect --migrate --target vault`
- Automatic credential rotation

### Then: Original Roadmap Resumes

### v0.7.x+: Reactor Operations (Nick & Cole focus)

- Reactor Ops Log (console checks, shift handoffs)
- Compliance Tracking (30-min check enforcement, NRC evidence)
- Data Platform (Iceberg, dbt, Bronze/Silver layers)
- Scheduling System

### v0.8.0: Digital Twin Foundation

- Model Corral (`neut model` CLI)
- DT run tracking schema
- Shadow automation for TRIGA

---

## Quarterly Roadmap Summary

### Q2 2026: Foundation
**Theme:** Data platform + Model Corral + DT run tracking

- Deploy Iceberg + dbt Bronze/Silver layers
- Ship Model Corral with `neut model` CLI
- Implement DT run tracking schema
- Automate Shadow runs for TRIGA
- Document isotope workflow as-is
- Deploy public demo environment

### Q3 2026: Intelligence
**Theme:** ROM-2 operational + Compliance + Streaming

- ROM-2 inference with <20s latency
- Prediction vs measured dashboards
- dbt Gold layer KPIs
- Redpanda streaming ingest
- Compliance report generator
- Digital isotope request intake

### Q4 2026: Real-Time
**Theme:** ROM-1 + NAL-1 + Multi-facility prep

- ROM-1 at 10 Hz in control room display
- NAL-1 progression proof (accuracy validation)
- Anomaly detection prototype
- Reactor provider abstraction
- Facility pilot engagement
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
