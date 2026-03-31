# NeutronOS 2026 OKRs

> **Last Updated:** March 26, 2026
> **Planning Horizon:** Q2-Q4 2026 (Q1 complete)
> **Aligned With:** [Executive PRD](prd-executive.md), [Digital Twin Hosting PRD](prd-digital-twin-hosting.md), [Model Corral PRD](prd-model-corral.md), [RAG PRD](prd-rag.md), [Prompt Registry PRD](prd-prompt-registry.md)
>
> **Upstream:** [Axiom 2026 OKRs](https://github.com/…/axiom/docs/requirements/prd-okrs-2026.md) — Platform-level objectives (DT infrastructure, Model Corral, Data Platform, Intelligence Platform, Security) are owned by Axiom. This document covers NeutronOS nuclear-domain objectives and nuclear-specific key results within shared platform objectives.
>
> **Major update (2026-03-26):** Split from combined OKRs. Platform objectives moved to Axiom OKRs. Nuclear-domain objectives (Reactor Ops, Medical Isotope, NRC compliance) retained here. INL federation partnership milestones retained. SeaweedFS replaced with S3-compatible object storage (Ceph/Rook recommended).

---

## PRD → OKR Linkage Matrix

### Platform PRDs (owned by Axiom OKRs, nuclear KRs tracked here)

| PRD | Axiom Objective | Nuclear KRs in This Doc |
|-----|----------------|------------------------|
| [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) | Axiom O1 (DT Foundation) | TRIGA shadow, NETL deployment |
| [Model Corral PRD](prd-model-corral.md) | Axiom O2 (Model Registry) | TRIGA models, Nick & Cole |
| [Data Platform PRD](prd-data-platform.md) | Axiom O3 (Data Platform) | Nuclear Bronze/Silver/Gold schemas |
| [Digital Twin Hosting PRD](prd-digital-twin-hosting.md) | Axiom O4 (ROM-1) | TRIGA control room, NAL-1 proof |

### Nuclear-Domain PRDs (owned by this document)

| PRD | OKR Objective | Implementation Status |
|-----|---------------|----------------------|
| [Reactor Ops Log PRD](prd-reactor-ops-log.md) | **O1** (Reactor Ops) | 🔲 Not started |
| [Compliance Tracking PRD](prd-compliance-tracking.md) | **O1** (Reactor Ops) | 🔲 Not started |
| [Scheduling System PRD](prd-scheduling-system.md) | O1, O2 | 🔲 Not started |
| [Experiment Manager PRD](prd-experiment-manager.md) | O1, O3 | 🔲 Not started |
| [Analytics Dashboards PRD](prd-analytics-dashboards.md) | O1, O3 | 🔲 Not started |
| [Medical Isotope PRD](prd-medical-isotope.md) | **O2** (Medical Isotope) | 🔲 Not started |

---

## Nuclear-Specific Key Results for Platform Objectives

These KRs extend the Axiom platform objectives with nuclear-domain specifics. See [Axiom OKRs](https://github.com/…/axiom/docs/requirements/prd-okrs-2026.md) for the full platform objectives.

### Axiom O1 (DT Foundation) — Nuclear KRs

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Shadow automation for TRIGA NETL | Nightly runs | Q2 | 🔲 |
| TRIGA-specific ROM-2 training pipeline | Trained on NETL data | Q3 | 🔲 |
| Integrate SLURM job submission for TACC | Authenticated HPC access | Q2 | 🔲 |

### Axiom O2 (Model Registry) — Nuclear KRs

> **Near-term: Nick and Cole (NETL)** — Nick and Cole are actively waiting on `neut model search/add/pull`. This is not a future roadmap item; it is an immediate user need.

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| TRIGA models migrated | 10+ models in registry | Q2 | 🔲 |
| Nick and Cole unblocked | `neut model` CLI working | Q2 | 🔲 |
| INL LDRD models registerable | Federated model fields in `model.yaml` | Q3 | 🔲 |

### Axiom O3 (Data Platform) — Nuclear KRs

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| dbt models for TRIGA data | Silver layer transforms | Q2 | 🔲 |
| Nuclear Bronze schemas deployed | Reactor time-series, ops logs, experiments | Q2 | 🔲 |
| Nuclear Gold tables populated | Reactor metrics, compliance summary, experiment utilization | Q3 | 🔲 |
| NRC evidence package generation | One-click export | Q3 | 🔲 |

### Axiom O4 (ROM-1) — Nuclear KRs

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Integrate with TRIGA DT Website `/simulator` | Control room display | Q4 | 🔲 |
| NAL-1 progression proof | Accuracy validated for N hours | Q4 | 🔲 |

### Axiom O5 (Community) — Nuclear KRs

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| 2+ UT courses using NeutronOS tools | ME 390G, ME 361E | Q3 | 🔲 |
| Meet with course instructors | Integration plan | Q2 | 🔲 |

---

## Objective 1: Reactor Operations & NRC Compliance
> Reactor ops log and compliance reporting automated

**Aligns with:** [Reactor Ops Log PRD](prd-reactor-ops-log.md), [Compliance Tracking PRD](prd-compliance-tracking.md), [Scheduling System PRD](prd-scheduling-system.md), [Experiment Manager PRD](prd-experiment-manager.md), [Analytics Dashboards PRD](prd-analytics-dashboards.md)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Console check digitization | Paper → digital | Q2 | 🔲 |
| Shift handoff workflow | Structured handoffs | Q3 | 🔲 |
| Compliance report generator | One-click NRC reports | Q3 | 🔲 |
| 30-min check gap alerting | Automatic notification | Q3 | 🔲 |
| Training currency dashboard | Certification status visible | Q3 | 🔲 |
| Anomaly detection prototype | Automated flagging | Q4 | 🔲 |

### Supporting Work
- [ ] Design console check UI (per [spec-console-check-ui-mockups.md](../tech-specs/spec-console-check-ui-mockups.md))
- [ ] Build shift handoff templates
- [ ] Define NRC compliance evidence schema
- [ ] Define Bronze schemas: `ops_log_entries_raw`, `training_records_raw`, `authorized_experiments_raw`
- [ ] Build Silver transforms: ops log validation, training record expiry, experiment authorization cross-check
- [ ] Build Gold tables: `ops_log_compliance`, `compliance_summary`, `shift_summary`
- [ ] Research anomaly detection approaches

---

## Objective 2: Medical Isotope Automation
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

## Objective 3: Nuclear Community & Course Adoption
> NeutronOS integrated into UT nuclear engineering curriculum

**Aligns with:** Axiom O5 (Community & Adoption)

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| ME 390G integration | Students using `neut` for reactor analysis | Q3 | 🔲 |
| ME 361E integration | Students using dashboards for lab reports | Q3 | 🔲 |
| Student onboarding tutorial | Nuclear-specific getting started guide | Q2 | 🔲 |
| Experiment Manager demo | Students can track irradiation experiments | Q3 | 🔲 |

---

## Multi-Facility Foundation + INL Federation

> **Owned by Axiom O6** (Multi-Facility Foundation). The following nuclear-specific milestones extend that objective.

### Nuclear-Specific KRs

| Key Result | Target | Timeline | Status |
|------------|--------|----------|--------|
| Reactor provider abstraction | TRIGA-specific code → generic interface | Q4 | 🔲 |
| Rascal validates EC architecture | Required before OSU/INL trust EC claims | Q2 | 🔲 |
| INL LDRD co-investigator commitment confirmed | Verbal → formal | Q2 | 🔲 |

### INL Partnership Milestones

The INL federated learning LDRD (PI: Jieun Lee, INL NRAD) proposes UT-Austin, OSU, and INL NRAD as founding members of a federated nuclear AI consortium. NeutronOS is positioned as the facility-side platform for knowledge management and model registry; the LDRD focuses on federated model training (Flower AI integration path).

| Milestone | Target | Notes |
|-----------|--------|-------|
| Confirm co-investigator role formally | Q2 2026 | Reply to Jieun Lee; align on UT contribution scope and deliverables |
| Align Model Corral schema with LDRD deliverables | Q2 2026 | Add `federation_round`, `participating_facilities`, `aggregation_method` to `model.yaml` |
| Rascal validates EC architecture | Q2 2026 | Required before OSU/INL can trust our EC compliance claims |
| Community corpus federation v1 (UT ↔ OSU bilateral) | Q4 2026 | First bilateral knowledge sharing between founding members |
| LDRD proposal submission | TBD — follow INL timeline | Ben as external co-PI |
| Flower AI integration scoped | Q3 2026 | Depends on LDRD funding confirmation |

---

## Nuclear Implementation Priority

> These items layer on top of the Axiom implementation priority list. Version numbers align with Axiom milestones.

### v0.7.x+: Reactor Operations (Nick & Cole focus)

- [ ] Reactor Ops Log (console checks, shift handoffs)
- [ ] Compliance Tracking (30-min check enforcement, NRC evidence)
- [ ] Nuclear Data Platform schemas (Iceberg Bronze/Silver/Gold for reactor data)
- [ ] Scheduling System
- [ ] Experiment Manager

### v0.8.0+: Digital Twin — Nuclear Extensions

- [ ] TRIGA-specific shadow automation
- [ ] DT run tracking with nuclear reactor types
- [ ] ROM training provenance (VERA, MCNP, SAM, SCALE output schemas)

---

## Quarterly Roadmap Summary (Nuclear Extensions)

### Q2 2026
- Ship nuclear Bronze schemas (reactor time-series, ops logs, experiments) — extends Axiom O3
- TRIGA shadow automation — extends Axiom O1
- Nick and Cole unblocked on `neut model` — extends Axiom O2
- Console check digitization (O1)
- Medical isotope workflow documentation (O2)
- Confirm INL LDRD co-investigator role
- Rascal EC validation (extends Axiom O6)

### Q3 2026
- Nuclear dbt Gold layer (reactor metrics, compliance, experiment utilization) — extends Axiom O3
- NRC compliance report generator (O1)
- 30-min check gap alerting (O1)
- Training currency dashboard (O1)
- ME 390G / ME 361E course integration (O3)
- Digital isotope request intake (O2)
- TRIGA ROM-2 training pipeline — extends Axiom O1
- Deployment playbook (Rascal → TACC)
- Flower AI integration scoped (if LDRD confirmed)

### Q4 2026
- TRIGA control room display + NAL-1 proof — extends Axiom O4
- Anomaly detection prototype (O1)
- Medical isotope SLA tracking (O2)
- Reactor provider abstraction
- Community corpus federation v1 (UT ↔ OSU bilateral)
- Federated model artifact support (INL LDRD models)

---

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| TACC HPC access (SLURM auth) | Shadow runs blocked | Work with TACC on authentication early |
| ROM accuracy on TRIGA data | Can't achieve NAL-1 proof | Increase training data, improve models |
| Course instructor buy-in | Low student adoption | Early engagement, show value in ME 390G first |
| INL LDRD funding not confirmed | Federation scope unclear | Confirm co-PI role before building federation sync |
| Rascal hardware access | EC staging blocked | Coordinate GPU scheduling with NETL staff early |
| NRC evidence format requirements | Compliance reports rejected | Engage NRC inspector early for format validation |
| NETL reactor schedule | Limited data collection windows | Coordinate with reactor operations calendar |

---

## Review Schedule

| Cadence | Activity |
|---------|----------|
| Weekly | Implementation progress check |
| Monthly | KR scoring, blocker review |
| Quarterly | OKR retrospective, stakeholder update |

---

## Related Documents

### NeutronOS PRDs
- [Executive PRD](prd-executive.md) — Product vision
- [Reactor Ops Log PRD](prd-reactor-ops-log.md) — Console operations
- [Compliance Tracking PRD](prd-compliance-tracking.md) — Regulatory monitoring
- [Scheduling System PRD](prd-scheduling-system.md) — Resource scheduling
- [Experiment Manager PRD](prd-experiment-manager.md) — Sample lifecycle
- [Analytics Dashboards PRD](prd-analytics-dashboards.md) — Visualization
- [Medical Isotope PRD](prd-medical-isotope.md) — Isotope production
- [Data Platform PRD](prd-data-platform.md) — Nuclear data schemas

### Axiom PRDs (platform layer)
- [Axiom OKRs](https://github.com/…/axiom/docs/requirements/prd-okrs-2026.md) — Platform objectives
- [Axiom Data Platform PRD](https://github.com/…/axiom/docs/requirements/prd-data-platform.md) — Generic lakehouse
- [Axiom Digital Twin Hosting PRD](https://github.com/…/axiom/docs/requirements/prd-digital-twin-hosting.md) — DT infrastructure
- [Axiom Model Corral PRD](https://github.com/…/axiom/docs/requirements/prd-model-corral.md) — Model registry

### Tech Specs
- [Digital Twin Architecture](../tech-specs/spec-digital-twin-architecture.md)
- [Data Architecture Spec](../tech-specs/spec-data-architecture.md)
- [Console Check UI Mockups](../tech-specs/spec-console-check-ui-mockups.md)

### ADRs
- [ADR-013: Rascal EC Staging](adr-013-rascal-ec-staging.md)
