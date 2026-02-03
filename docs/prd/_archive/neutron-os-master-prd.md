# Neutron OS Product Requirements Document

**Nuclear Energy Unified Technology for Research, Operations & Networks**

---

> ⚠️ **DRAFT - FOR INTERNAL REVIEW ONLY** ⚠️
>
> Version 0.1 | Generated: January 15, 2026 | Status: Draft for Colleague Review

---

| Property | Value |
|----------|-------|
| Document Type | Product Requirements Document (PRD) |
| Version | 0.1 DRAFT |
| Last Updated | 2026-01-15 |
| Status | Draft - Pending Review |
| Product Owner | [TBD] |
| Stakeholders | UT Computational NE Team, Nick Luciano, [Others TBD] |

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [User Personas](#2-user-personas)
3. [Problem Statement](#3-problem-statement)
4. [Solution Overview](#4-solution-overview)
5. [Feature Requirements](#5-feature-requirements)
6. [User Journeys](#6-user-journeys)
7. [Success Metrics](#7-success-metrics)
8. [Roadmap](#8-roadmap)
9. [Dependencies & Risks](#9-dependencies--risks)
10. [Appendices](#10-appendices)

---

## 1. Vision & Goals

### 1.1 Vision Statement

Neutron OS is a **digital twin data platform** that provides the infrastructure for nuclear reactor digital twins across multiple use cases—from real-time state estimation to fuel management to experiment planning.

> **Key Insight:** Digital twins serve multiple critical purposes in reactor operations. While real-time state estimation (predict faster than sensors) is technically demanding, the broader value spans fuel optimization, predictive maintenance, safety analysis, and research validation.

### 1.2 Digital Twin Use Cases

Digital twins powered by Neutron OS serve five primary categories:

| Use Case | Description | Key Capabilities |
|----------|-------------|------------------|
| **Real-Time State Estimation** | Predict reactor state faster than sensors (~10ms vs ~100ms) | Continuous state visibility, fill gaps between readings, estimate unmeasurable quantities |
| **Fuel Management** | Optimize fuel utilization and identify issues | Burnup tracking, hot spot identification, anomalous rod detection, reload optimization |
| **Predictive Maintenance** | Anticipate component degradation | Thermal cycling stress, control rod wear, scheduled maintenance windows |
| **Experiment Planning** | Simulate before execution | Irradiation planning, activation prediction, safety margin analysis |
| **Research & Validation** | Compare models to reality | Physics code validation, ML training data, academic publications |

### 1.3 Strategic Goals

- **🎯 Multi-Purpose Digital Twins:** Enable digital twin simulations across all five use case categories, with data infrastructure that supports both real-time and analytical workloads.

- **Unified Data Foundation:** Consolidate reactor operational data, simulation outputs, and research data into a single, queryable lakehouse with time-travel capabilities—serving as the training data and validation source for digital twin models.

- **ML Model Training Pipeline:** Provide the data infrastructure for training physics-informed machine learning models that power digital twin predictions across all use cases.

- **Fuel Management Intelligence:** Track burnup distribution, identify hot spots, detect anomalous fuel rod behavior, and optimize core reload patterns.

- **Prediction Validation Loop:** Compare digital twin predictions against actual sensor readings to continuously validate and improve model accuracy.

- **Regulatory Compliance:** Provide immutable audit trails via blockchain technology, enabling facilities to demonstrate data integrity to regulators with cryptographic proof.

- **Intelligent Operations:** Automate routine tasks like meeting documentation, requirements tracking, and report generation using AI/LLM capabilities.

- **Cross-Facility Collaboration:** Enable multiple nuclear facilities to share data and insights while maintaining security and audit separation.

- **Commercialization Pathway:** Build a platform that can be licensed to other reactors and nuclear facilities.

### 1.4 Strategic Partnerships & Integration Opportunities

#### Multi-Organization Design

Neutron OS is architected to support **multi-tenant deployments**, enabling multiple organizations to share infrastructure while maintaining strict data isolation. This design choice opens future collaboration opportunities, though our current focus is UT Austin's NETL facility.

**Design Principles:**
- Row-level security (RLS) enables tenant isolation
- Common schemas allow cross-facility benchmarking (with explicit consent)
- Federated deployment options support air-gapped or hybrid scenarios

#### Potential Future Partners

| Partner | Opportunity | Status |
|---------|-------------|--------|
| MIT NRL | MITR digital twin, Irradiation Loop DT tools | Active collaboration |
| Penn State RSEC | Breazeale TRIGA, NRC inspection innovation | Potential |
| UT Austin NETL | Primary implementation site | Current |
| Texas A&M NSC | AGN-201 digital twin | Potential |
| Idaho National Laboratory (INL) | Advanced reactor DT, fuel qualification, isotope production for materials research | Potential |
| Oregon State University | TRIGA reactor operations, university reactor community network validation | Potential |

---

## 2. User Personas

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              USER PERSONA MAP                                            │
│                              [DRAFT v0.1]                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   PRIMARY USERS                                                                          │
│   ─────────────                                                                          │
│                                                                                          │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐                    │
│   │        OPERATOR             │    │       RESEARCHER            │                    │
│   │        "Alex"               │    │        "Dana"               │                    │
│   │                             │    │                             │                    │
│   │ Role: Reactor Operator      │    │ Role: Graduate Researcher   │                    │
│   │                             │    │                             │                    │
│   │ Goals:                      │    │ Goals:                      │                    │
│   │ • Monitor reactor status    │    │ • Analyze experimental      │                    │
│   │ • Log operations accurately │    │   results                   │                    │
│   │ • Respond to anomalies      │    │ • Correlate simulations     │                    │
│   │                             │    │   with measurements         │                    │
│   │ Pain Points:                │    │                             │                    │
│   │ • Manual logbook entry      │    │ Pain Points:                │                    │
│   │ • Data scattered across     │    │ • Data in many formats      │                    │
│   │   systems                   │    │ • Manual data prep          │                    │
│   │ • Audit prep is tedious     │    │ • Hard to reproduce work    │                    │
│   └─────────────────────────────┘    └─────────────────────────────┘                    │
│                                                                                          │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐                    │
│   │     FACILITY MANAGER        │    │        INSPECTOR            │                    │
│   │        "Jordan"             │    │        "Morgan"             │                    │
│   │                             │    │                             │                    │
│   │ Role: Reactor Director      │    │ Role: NRC Inspector         │                    │
│   │                             │    │                             │                    │
│   │ Goals:                      │    │ Goals:                      │                    │
│   │ • Ensure compliance         │    │ • Verify data integrity     │                    │
│   │ • Track utilization         │    │ • Review operations logs    │                    │
│   │ • Plan experiments          │    │ • Audit trail completeness  │                    │
│   │                             │    │                             │                    │
│   │ Pain Points:                │    │ Pain Points:                │                    │
│   │ • Manual report generation  │    │ • Verifying unaltered       │                    │
│   │ • Coordinating schedules    │    │   records is difficult      │                    │
│   │ • Audit preparation burden  │    │ • Paper-based audits slow   │                    │
│   └─────────────────────────────┘    └─────────────────────────────┘                    │
│                                                                                          │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐                    │
│   │    DT RESEARCHER            │    │    DEPARTMENT HEAD          │                    │
│   │       "Chris"               │    │       "William"             │                    │
│   │                             │    │                             │                    │
│   │ Role: Digital Twin Dev      │    │ Role: Dept Head/Director    │                    │
│   │                             │    │                             │                    │
│   │ Goals:                      │    │ Goals:                      │                    │
│   │ • Log DT simulation runs    │    │ • Cross-team visibility     │                    │
│   │ • Validate predictions vs   │    │ • Access both ops & DT logs │                    │
│   │   measured data             │    │ • Audit oversight           │                    │
│   │ • Keep DT activity separate │    │                             │                    │
│   │   from ops log              │    │ Pain Points:                │                    │
│   │                             │    │ • Siloed information        │                    │
│   │ Pain Points:                │    │ • No unified view           │                    │
│   │ • No structured DT log      │    │                             │                    │
│   │ • Hard to correlate with    │    │                             │                    │
│   │   reactor conditions        │    │                             │                    │
│   └─────────────────────────────┘    └─────────────────────────────┘                    │
│                                                                                          │
│   SECONDARY USERS                                                                        │
│   ───────────────                                                                        │
│                                                                                          │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐                    │
│   │      DEVELOPER              │    │    EXTERNAL RESEARCHER      │                    │
│   │       "Sam"                 │    │        "Riley"              │                    │
│   │                             │    │                             │                    │
│   │ Role: Software Developer    │    │ Role: Visiting Scientist    │                    │
│   │                             │    │                             │                    │
│   │ Goals:                      │    │ Goals:                      │                    │
│   │ • Build data pipelines      │    │ • Access relevant data      │                    │
│   │ • Integrate simulations     │    │ • Collaborate on analysis   │                    │
│   │ • Extend platform           │    │                             │                    │
│   └─────────────────────────────┘    └─────────────────────────────┘                    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Problem Statement

### 3.1 The Core Challenge: Sensor-Limited Operations

**The fundamental problem:** Physical sensors and processors have ~100ms latency to assess reactor state. During this time, the internal state of the reactor is essentially unknown. Critical transients can develop in <50ms.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                THE SENSOR LATENCY PROBLEM                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   Timeline: ─────────────────────────────────────────────────────────────────────────►  │
│                                                                                          │
│             t=0ms        t=50ms       t=100ms      t=150ms      t=200ms                 │
│               │            │            │            │            │                     │
│               ▼            ▼            ▼            ▼            ▼                     │
│           ┌──────┐                  ┌──────┐                  ┌──────┐                  │
│           │Sensor│                  │Sensor│                  │Sensor│                  │
│           │Read  │                  │Read  │                  │Read  │                  │
│           └──────┘                  └──────┘                  └──────┘                  │
│               │                        │                        │                       │
│               │    UNKNOWN STATE       │    UNKNOWN STATE       │                       │
│               │◄──────────────────────►│◄──────────────────────►│                       │
│                                                                                          │
│   CONSEQUENCE:                                                                           │
│   • Safety margins must be conservative to account for uncertainty                       │
│   • Cannot safely operate near optimal capacity                                          │
│   • Transients may not be detected until after they've progressed                        │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why this matters:** If we can predict reactor state in ~10ms (via digital twin simulation), we gain continuous visibility into reactor behavior between sensor readings. This enables:
- Predictive safety margins (act before anomalies manifest)
- Higher capacity utilization (tighter operating envelopes)  
- Eventually: closed-loop simulation-driven control

### 3.2 Supporting Challenges

#### 3.2.1 Data Fragmentation

Reactor data, simulation outputs, and research results are stored in disparate systems (CSV files, HDF5, databases, spreadsheets) with no unified access layer. **This prevents effective ML model training for digital twins.**

#### 3.2.2 Manual Audit Burden

Preparing for NRC inspections requires significant manual effort to compile records and demonstrate their integrity. **This is critical for eventual closed-loop control approval.**

#### 3.2.3 Meeting Documentation Gap

Requirements and decisions made in meetings are not systematically captured and linked to project artifacts.

#### 3.2.4 Limited Time-Travel

Cannot easily query historical data states or understand how data has changed over time. **This limits ability to train models on specific historical scenarios.**

#### 3.2.5 Siloed Digital Twins

Each digital twin project (TRIGA, MSR, MIT Loop, OffGas) maintains separate tooling with duplicated effort.

---

## 4. Solution Overview

### 4.1 The Core Solution: Simulate-to-Operate

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│               NEUTRON OS: SIMULATE-TO-OPERATE SOLUTION                                   │
│                              [DRAFT v0.2]                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   THE CORE LOOP:                                                                         │
│                                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                                 │   │
│   │     PHYSICAL REACTOR          NEUTRON OS           DIGITAL TWIN                │   │
│   │     ────────────────          ──────────           ────────────                │   │
│   │                                                                                 │   │
│   │     ┌──────────────┐         ┌──────────────┐     ┌──────────────┐             │   │
│   │     │              │  Sensor │              │ ML  │              │             │   │
│   │     │   Sensors    │─────────│ Data Ingest  │────▶│  Simulation  │             │   │
│   │     │   (~100ms)   │  Data   │ (Bronze)     │Train│  (~10ms)     │             │   │
│   │     │              │         │              │     │              │             │   │
│   │     └──────────────┘         └──────────────┘     └──────┬───────┘             │   │
│   │            │                                             │                      │   │
│   │            │                                             │ Predictions          │   │
│   │            │                 ┌──────────────┐             │                      │   │
│   │            │     Actual      │              │◄────────────┘                      │   │
│   │            └─────────────────│   Validate   │                                   │   │
│   │                              │   & Improve  │──────▶ Continuous accuracy       │   │
│   │                              │              │        improvement                │   │
│   │                              └──────────────┘                                   │   │
│   │                                                                                 │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│   VALUE:                                                                                 │
│   • 10x faster state assessment (10ms prediction vs 100ms sensor)                        │
│   • Continuous visibility between sensor readings                                        │
│   • Predictive safety margins                                                            │
│   • Future: Closed-loop simulation-driven control                                        │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Supporting Solutions

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         SUPPORTING CAPABILITIES                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   PROBLEM                           SOLUTION                        VALUE                │
│   ───────                           ────────                        ─────                │
│                                                                                          │
│   ┌─────────────────┐              ┌─────────────────┐             ┌─────────────────┐  │
│   │ Data scattered  │────────────▶ │ Unified         │────────────▶│ ML training     │  │
│   │ across systems  │              │ Lakehouse       │             │ data ready      │  │
│   └─────────────────┘              │ (Iceberg)       │             │                 │  │
│                                    └─────────────────┘             │ Query any data  │  │
│                                                                    │ with SQL        │  │
│                                                                    └─────────────────┘  │
│                                                                                          │
│   ┌─────────────────┐              ┌─────────────────┐             ┌─────────────────┐  │
│   │ Audit prep is   │────────────▶ │ Blockchain      │────────────▶│ Closed-loop     │  │
│   │ manual & tedious│              │ Audit Trail     │             │ approval ready  │  │
│   └─────────────────┘              │ (Fabric)        │             │                 │  │
│                                    └─────────────────┘             │ Cryptographic   │  │
│                                                                    │ proof           │  │
│                                                                    └─────────────────┘  │
│                                                                                          │
│   ┌─────────────────┐              ┌─────────────────┐             ┌─────────────────┐  │
│   │ No historical   │────────────▶ │ Time-Travel     │────────────▶│ Train on any    │  │
│   │ data queries    │              │ Queries         │             │ scenario        │  │
│   └─────────────────┘              │ (Iceberg)       │             │                 │  │
│                                    └─────────────────┘             │ Reproduce past  │  │
│                                                                    │ conditions      │  │
│                                                                    └─────────────────┘  │
│                                                                                          │
│   ┌─────────────────┐              ┌─────────────────┐             ┌─────────────────┐  │
│   │ Siloed digital  │────────────▶ │ Shared DT       │────────────▶│ Consistent      │  │
│   │ twins           │              │ Infrastructure  │             │ approach        │  │
│   └─────────────────┘              │                 │             │                 │  │
│                                    └─────────────────┘             │ Transfer        │  │
│                                                                    │ learning        │  │
│                                                                    └─────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Feature Requirements

### 5.1 Feature Prioritization Matrix

| Feature | Priority | Effort | Value | Status |
|---------|----------|--------|-------|--------|
| Data Lakehouse (Bronze/Silver/Gold) | P0 | Large | Critical | In Progress |
| Superset Dashboards | P0 | Medium | Critical | In Progress |
| Reactor Operations Dashboard | P0 | Medium | High | Designed |
| Performance Analytics Dashboard | P0 | Medium | High | Designed |
| Unified Log System (Ops + DT) | P1 | Large | High | Designed (Jan 2026) |
| Meeting Intake Pipeline | P1 | Medium | Medium | Designed |
| Audit Evidence Generation | P1 | Medium | High | Planned |
| Sample/Experiment Tracking | P2 | Medium | Medium | Schema Designed |
| Measured vs Modeled Data Labels | P0 | Small | Critical | Designed (Jan 2026) |
| Multi-Facility Support | P2 | Large | High | Architecture |
| External Researcher Access | P3 | Medium | Low | Future |
| **AI Safety Framework** | P1 | Medium | Critical | NEUP-aligned (Jan 2026) |
| **Sensor Data Quality Layer** | P1 | Medium | High | NEUP-aligned (Jan 2026) |
| **Autonomy Roadmap** | P2 | Large | High | NEUP-aligned (Jan 2026) |
| **Cyber-Physical Security** | P1 | Large | Critical | NEUP-aligned (Jan 2026) |
| **Surrogate Model Interface** | P2 | Medium | High | NEUP-aligned (Jan 2026) |

> **Update (Jan 2026):** Per Nick Luciano's review, the Elog system is now a "Unified Log System" with `entry_type` discriminator supporting both Operations logs and Digital Twin activity logs. Access control allows DT researchers to include ops data if needed, while ops staff can be granted DT visibility (typically only department heads like William Charlton would use this).

### 5.2 Detailed Feature Specifications

#### 5.2.1 F1: Data Lakehouse

| Attribute | Specification |
|-----------|---------------|
| Description | Unified storage for all reactor, simulation, and research data |
| Technology | Apache Iceberg + DuckDB + dbt |
| Key Capabilities | Time-travel, schema evolution, SQL access |
| Data Sources | Reactor serial data, MPACT outputs, core configs, unified logs |
| Acceptance Criteria | Gold tables available in Superset with < 2s query time |

#### 5.2.2 F2: Superset Dashboards

| Attribute | Specification |
|-----------|---------------|
| Description | Interactive analytics dashboards for reactor operations |
| Technology | Apache Superset |
| Key Dashboards | Ops Dashboard, Performance Analytics, Log Activity, Audit |
| Data Source | Gold layer tables via DuckDB/Iceberg |
| Acceptance Criteria | Dashboards load < 3s, filters work correctly |

#### 5.2.3 F3: Unified Log System (Ops + DT)

| Attribute | Specification |
|-----------|---------------|
| Description | Unified logbook supporting both Operations and Digital Twin activity with access control |
| Technology | FastAPI + PostgreSQL + Hyperledger Fabric + Alembic migrations |
| Key Capabilities | CRUD operations, blockchain audit, evidence generation, entry_type filtering, role-based access |
| Reference | See [Reactor Ops Log PRD](../reactor-ops-log-prd.md), updated per Nick Luciano review Jan 2026 |
| Acceptance Criteria | Entries verified via blockchain proof, DT researchers can optionally include ops data |

**Entry Types:**
| entry_type | Description | Primary Users | Access |
|------------|-------------|---------------|--------|
| `ops` | Operations log entries (startup, shutdown, maintenance) | Operators, Facility Manager | Ops team, inspectors, dept heads |
| `dt` | Digital twin activity (simulation runs, predictions, validations) | DT Researchers | DT team, dept heads |
| `experiment` | Sample/experiment tracking entries | Researchers | Research team, dept heads |

**Access Control Model:**
- Operations staff: See `ops` entries by default
- DT researchers: See `dt` entries by default, can include `ops` if needed
- Department heads (e.g., William Charlton): See all entry types
- Inspectors: See `ops` entries only (audit scope)

#### 5.2.4 F4: Sample/Experiment Tracking

| Attribute | Specification |
|-----------|---------------|
| Description | Track samples from preparation through irradiation, decay, counting, and analysis |
| Technology | Unified log system with `entry_type='experiment'` + dedicated sample_tracking table |
| Key Capabilities | Unique sample IDs, metadata capture, irradiation location tracking, activity calculation |
| Reference | Requirements from Nick Luciano (Jan 2026), pending validation from Khiloni Shah |
| Acceptance Criteria | Complete sample lifecycle tracked, prepopulated dropdowns for locations/facilities |

**Sample Metadata Fields (per Nick Luciano):**
- Sample Name (unique), Sample ID (auto-assigned)
- Chemical Composition, Isotopic Composition, Density, Mass
- Irradiation Location (central thimble, lazy susan, etc.)
- Irradiation Facility (cadmium covered, bare, etc.)
- Datetime of insertion/removal, Decay time
- Count live time, Total counts, Total activity
- Activity by isotope, Measurement raw data (spectra)

#### 5.2.5 F5: AI Safety Framework

| Attribute | Specification |
|-----------|---------------|
| Description | Safety guardrails for LLM/AI interactions with reactor operations |
| Technology | Prompt sanitization, confidence scoring, human-in-the-loop gates |
| Key Capabilities | Query logging, response validation, prohibited action detection |
| Reference | NEUP Proposals: `docs/NEUP_2026/OperatorLLMSafety.docx`, `docs/NEUP_2026/NuclearLLMBench.docx`, `docs/NEUP_2026/DT_Safety.docx` |
| Acceptance Criteria | No AI response can suggest direct control actions; all queries logged |

**NEUP Alignment:**
- **OperatorLLMSafety**: LLM guardrails for operator-facing AI; confidence scoring; prohibited action detection
  - *POCs:* PI TBD; Collaborators: Ron Boring (INL), UT-AI group
- **NuclearLLMBench**: Benchmarking framework for validating LLM responses in nuclear context
  - *POCs:* PI Kevin Clarno (UT); Collaborators: Derek Booth (UT), Ondrej Chvala (UT), Cole Gentry (UT), PNNL team
- **DT_Safety**: Digital twin safety requirements; fault reversion; human override
  - *POCs:* PI William Charlton (UT); Collaborators: Cole Gentry (UT), Adam Williams (SNL)

**LLM Interaction Safety Levels:**

| Interaction Type | Safety Level | Requirements |
|-----------------|--------------|-------------|
| Information lookup | Low | Standard RAG with source citation |
| Procedure assistance | Medium | Cross-reference approved procedures; human confirmation |
| Operational recommendation | High | Multi-model consensus; physics validation; SRO approval |
| Control action suggestion | **Prohibited** | LLM cannot suggest direct control actions |

**Safety Requirements:**
- AI-001: All LLM responses logged with query, response, sources cited
- AI-002: Confidence scores required for operational queries
- AI-003: Human-in-the-loop mandatory for action-oriented responses
- AI-004: Prompt injection prevention via input sanitization

---

#### 5.2.6 F6: Sensor Data Quality Layer

| Attribute | Specification |
|-----------|---------------|
| Description | Reconciliation and fusion of redundant sensor data |
| Technology | Silver layer transforms with configurable fusion algorithms |
| Key Capabilities | Conflict detection, weighted averaging, Kalman filtering, quality flagging |
| Reference | NEUP Proposal: Resolving Sensor Data Conflicts (`docs/NEUP_2026/ResolvingSensorDataConflicts.docx`) |
| POCs | PI TBD; Collaborators: Kevin Clarno (UT) |
| Acceptance Criteria | Reconciled values with confidence scores for all redundant sensor pairs |

**As-Is State (Existing Implementations):**
- **TRIGA ZOC Parser**: `TRIGA_Digital_Twin/triga_modsim_tools/triga_modsim_tools/dataproc/zoc_parser.py`
  - Implements `TEMPERATURE_CUTOFF`, `LINEAR_POWER_CUTOFF`, `ROD_SIMILARITY_THRESHOLD` for sensor filtering
  - `parse_temperature_data()` handles multi-sensor temperature fusion (FuelTemp1, FuelTemp2, WaterTemp)
  - Quality-aware value extraction via `safe_value_extract()` with type-safe conversion
- **Controller Abstraction**: `TRIGA_Digital_Twin/triga_modsim_tools/triga_modsim_tools/controller.py`
  - Abstract `Controller` base class with `input_signals` and `output_signals` for sensor/actuator interface
  - `receive_system_signals(signals: Dict[str, float], dt: float)` pattern for timestamped sensor ingestion

**Reconciliation Strategies:**

| Strategy | Use Case | Output |
|----------|----------|--------|
| Weighted average | Normal operation, minor disagreements | reconciled_value + confidence |
| Voting | Redundant identical sensors | majority_value + dissent_count |
| Kalman filter | Time-series with known dynamics | filtered_state + uncertainty |
| ML fusion | Complex multi-modal scenarios | predicted_value + feature_importance |

**Quality Flags:**
- `GOOD`: All sensors agree within threshold
- `CONFLICT`: Sensors disagree beyond threshold (requires reconciliation)
- `DEGRADED`: Fewer than minimum required sensors available
- `FAILED`: No valid sensor readings

---

#### 5.2.7 F7: Autonomy Roadmap

| Attribute | Specification |
|-----------|---------------|
| Description | Staged autonomy levels from advisory to semi-autonomous operation |
| Technology | Ops log extensions, approval workflows, bounded automation |
| Key Capabilities | Autonomy mode tracking, operator override, fault reversion |
| Reference | NEUP Proposals: `docs/NEUP_2026/SemiAutonomousControls.docx`, `docs/NEUP_2026/VirtualSystemsEngineer.docx` |
| Acceptance Criteria | Clear autonomy level at all times; all transitions logged |

**NEUP Alignment:**
- **SemiAutonomousControls**: Staged autonomy framework; bounded operation envelopes; NRC-compatible approval workflow
  - *POCs:* PI Benjamin Collins (UT); Collaborators: Soha Aslam (UT), John Ross (Natural Resources)
- **VirtualSystemsEngineer**: AI agent for systems engineering tasks; automated procedure generation; human-in-the-loop validation
  - *POCs:* PI TBD; Collaborators: Ron Boring (INL), UT-AI group

**Autonomy Levels:**

| Level | Name | DT Role | Human Role | Ops Log Requirement |
|-------|------|---------|------------|---------------------|
| 0 | Manual | Information display only | Full control | Standard entries |
| 1 | Advisory | Suggests actions | Approval required | Log recommendations + decisions |
| 2 | Semi-Auto (Bounded) | Executes within pre-approved envelope | Monitoring + override | Log autonomous actions |
| 3 | Semi-Auto (Extended) | Handles routine operations | Exception handling | Continuous audit trail |

**New Entry Types for Autonomy:**
- `AUTONOMY_MODE_CHANGE`: Transition between levels (SRO signature required)
- `AUTONOMOUS_ACTION`: Action taken by DT (system + SRO review)
- `OPERATOR_OVERRIDE`: Human overrode DT recommendation
- `AUTONOMY_FAULT`: System reverted to lower level

> **Note:** Level 2+ requires NRC approval process. Current implementation targets Level 0-1 only.

---

#### 5.2.8 F8: Cyber-Physical Security

| Attribute | Specification |
|-----------|---------------|
| Description | Security architecture addressing cyber-physical threats to digital twin |
| Technology | Signed sensor readings, model checksums, network isolation options |
| Key Capabilities | Spoofing detection, tampering prevention, air-gap deployment |
| Reference | NEUP Topic 11: Cyber-Nuclear Security; `docs/NEUP_2026/DT_Safety.docx` |
| Acceptance Criteria | Threat model documented; mitigations implemented for critical paths |

**NEUP Alignment:**
- **NEUP Topic 11** (Cyber-Nuclear Security): Research area focus on securing critical nuclear infrastructure from cyber threats
- **DT_Safety**: Digital twin fault tolerance; adversarial input detection; graceful degradation
  - *POCs:* PI William Charlton (UT); Collaborators: Cole Gentry (UT), Adam Williams (SNL)

**Threat Model:**

| Threat Vector | Attack | Impact | Mitigation |
|---------------|--------|--------|------------|
| Sensor ingestion | Spoofing, replay | False state estimation | Signed readings, time bounds |
| Model execution | Tampering, poisoning | Incorrect predictions | Model checksums, adversarial detection |
| Actuator interface | Command injection | Unauthorized control | Cryptographic auth, rate limiting |
| State database | Unauthorized access | Data exfiltration | Encryption at rest, RBAC |
| Network | Man-in-the-middle | Data manipulation | TLS, certificate pinning |

**Deployment Modes:**

| Mode | Network | Data Flow | Use Case |
|------|---------|-----------|----------|
| Connected | Full internet | Bidirectional | Development, low-security research |
| Hybrid | Limited egress | Outbound summaries only | Production with monitoring |
| Air-gapped | No external network | Manual transfer | High-security, NRC-regulated |

---

#### 5.2.9 F9: Surrogate Model Interface

| Attribute | Specification |
|-----------|---------------|
| Description | Standardized interface for physics-informed surrogate models (KAN, PINN, ROM) |
| Technology | Python API with model registry, versioning, validation hooks |
| Key Capabilities | Model hot-swap, uncertainty quantification, interpretability |
| Reference | NEUP Proposals: `docs/NEUP_2026/KANs_ReactorModeling_rev02.docx`, `docs/NEUP_2026/PINNS_SelfShielding_INL.docx`, `docs/NEUP_2026/SaltLoopROM.docx` |
| POCs | **KANs:** PI Majdi Radaideh (U Michigan); Collab: Jeongwon Seo (UT), Cole Gentry (UT) | 
|  | **PINNs:** PI Cole Gentry (UT); Collab: Nicholas Luciano (UT), Yaqi Wang (INL) |
|  | **SaltLoopROM:** PI TBD; Collab: ACU, VCU, Texas A&M |
| Acceptance Criteria | Any registered surrogate can be swapped without code changes |

**As-Is State (Existing Implementations):**
- **Dakota Surrogate Interface**: `MSR_Digital_Twin_Open/msr-dakota/dakota_examples/dakota-examples/contributed/auxiliary-tools/surrogate_from_python/dakota_surrogate.py`
  - `DakotaSurrogate` class with `predict(X, surrogate)` supporting multiple surrogate types:
    - `'gaussian_process surfpack trend quadratic'`
    - `'neural_network'`
    - `'polynomial quadratic'`
    - `'radial_basis'`
    - `'moving_least_squares'`
    - `'mars'` (Multivariate Adaptive Regression Splines)
  - Training data interface: `__init__(X, f, bounds)` with (N, ndim) input array and (N,) response vector
- **MSR Dakota UQ Module**: `MSR_Digital_Twin_Open/msr-dakota/src/msr_dakota/dakota/`
  - `build.py`: Model construction from parameterized packs (geometry, materials, settings)
  - `run.py`: Dakota job execution and result collection
  - Integration with OpenMC for neutronics validation
- **Off-Gas Inverse Modeling**: `OffGas_Digital_Twin/offgas_inverse_modeling/offgas_inverse_modeling/offgas_model.py`
  - `OffGasModel` with `Transfer` dataclass for isotope transport modeling
  - `simulate(timesteps, transfers, power)` for depletion + transfer coupled physics

**Surrogate Model Types:**

| Type | Strengths | Use Case | Interface |
|------|-----------|----------|----------|
| KAN (Kolmogorov-Arnold Network) | Interpretable, symbolic extraction | Neutronics where explainability matters | `predict()` + `explain()` |
| PINN (Physics-Informed Neural Network) | Enforces conservation laws | Thermal-hydraulics, transients | `predict()` + `physics_residual()` |
| ROM (Reduced-Order Model) | Fast, well-understood | Real-time state estimation | `project()` + `reconstruct()` |
| Traditional ML | Flexible, proven | Anomaly detection, classification | `predict()` + `confidence()` |

**Common Interface:**
```python
class SurrogateModel(Protocol):
    def predict(self, inputs: dict) -> SurrogateResult:
        """Returns prediction with uncertainty bounds."""
        ...
    
    def validate(self, inputs: dict, measured: dict) -> ValidationResult:
        """Compares prediction to measured values."""
        ...
    
    @property
    def metadata(self) -> ModelMetadata:
        """Returns version, training data hash, validation metrics."""
        ...
```

> **[PLACEHOLDER: Additional Feature Specifications]**
> → Add detailed specs for remaining features as designed

---

## 6. User Journeys

### 6.1 Operator Daily Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         OPERATOR DAILY JOURNEY - "ALEX"                                  │
│                              [DRAFT v0.1]                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   TIME        ACTION                              NEUTRON OS INTERACTION                 │
│   ────        ──────                              ──────────────────────                 │
│                                                                                          │
│   7:00 AM     Start shift                         Open Ops Dashboard                     │
│               ──────────                          ──────────────────────                 │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • View overnight power │             │
│               │                                   │ • Check any anomalies  │             │
│               │                                   │ • Review rod positions │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   7:30 AM     Log shift start                     Create Ops Log entry                   │
│               ───────────────                     ─────────────────────                  │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Enter shift start    │             │
│               │                                   │ • Note any handoff     │             │
│               │                                   │   issues               │             │
│               │                                   │ • Auto-hash to chain   │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   9:00 AM     Monitor startup                     Real-time dashboard                    │
│               ───────────────                     ────────────────────                   │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Watch power ramp     │             │
│               │                                   │ • Monitor temps        │             │
│               │                                   │ • Track rod movement   │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   12:00 PM    Log observation                     Quick Ops Log entry                    │
│               ───────────────                     ────────────────────                   │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Note rod calibration │             │
│               │                                   │ • Attach data ref      │             │
│               │                                   │ • Blockchain commit    │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   3:00 PM     End shift                           Close Ops Log + handoff                │
│               ─────────                           ─────────────────────                  │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Summary entry        │             │
│               │                                   │ • Shift metrics auto   │             │
│               │                                   │ • Handoff notes        │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   VALUE: Reduced manual logging, verified audit trail, real-time visibility              │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Inspector Audit Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         INSPECTOR AUDIT JOURNEY - "MORGAN"                               │
│                              [DRAFT v0.1]                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   STEP        ACTION                              NEUTRON OS INTERACTION                 │
│   ────        ──────                              ──────────────────────                 │
│                                                                                          │
│   1           Request audit scope                 Facility provides access               │
│               ────────────────────                ──────────────────────                 │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Inspector account    │             │
│               │                                   │   created              │             │
│               │                                   │ • Date range scoped    │             │
│               │                                   │ • Read-only access     │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   2           Query operations logs               Audit Dashboard                        │
│               ────────────────────                ───────────────────                    │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Filter by date       │             │
│               │                                   │ • Search keywords      │             │
│               │                                   │ • View entry details   │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   3           Verify data integrity               Blockchain verification                │
│               ────────────────────                ──────────────────────                 │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Select records       │             │
│               │                                   │ • Click "Verify"       │             │
│               │                                   │ • View Merkle proof    │             │
│               │                                   │ • Confirmation shown   │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   4           Generate evidence package           Export to PDF/ZIP                      │
│               ────────────────────────            ────────────────────                   │
│               │                                   │                                      │
│               │                                   ▼                                      │
│               │                                   ┌────────────────────────┐             │
│               │                                   │ • Select scope         │             │
│               │                                   │ • Generate package     │             │
│               │                                   │ • Includes:            │             │
│               │                                   │   - Data records       │             │
│               │                                   │   - Blockchain proofs  │             │
│               │                                   │   - Audit log          │             │
│               │                                   └────────────────────────┘             │
│                                                                                          │
│   VALUE: Self-service audit, cryptographic proof, reduced facility burden                │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Success Metrics

### 7.1 Key Performance Indicators

| Metric | Current State | Target (6 mo) | Target (12 mo) |
|--------|---------------|---------------|----------------|
| Audit prep time | 2 weeks | 2 days | < 1 day |
| Data query time | Hours (manual) | < 5 seconds | < 2 seconds |
| Meeting→GitLab latency | Days (manual) | < 1 hour | < 15 minutes |
| Data source coverage | 20% | 60% | 90% |
| Dashboard adoption | 0 users | 10 users | 50+ users |
| Blockchain-verified records | 0% | 80% | 100% |

### 7.2 User Satisfaction Targets

| Persona | Satisfaction Metric | Target |
|---------|---------------------|--------|
| Operator | Ops Log entry time | < 2 minutes per entry |
| Researcher | Data access ease (1-5) | ≥ 4.0 |
| Facility Manager | Audit confidence (1-5) | ≥ 4.5 |
| Inspector | Verification time | < 30 minutes |

---

## 8. Roadmap

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              NEUTRON OS ROADMAP                                          │
│                              [DRAFT v0.1]                                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   Q1 2026                Q2 2026                Q3 2026                Q4 2026           │
│   ───────                ───────                ───────                ───────           │
│                                                                                          │
│   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐    │
│   │ FOUNDATION  │       │  ANALYTICS  │       │   AUDIT     │       │   SCALE     │    │
│   │             │       │             │       │             │       │             │    │
│   │ □ Lakehouse │       │ □ Ops Dash  │       │ □ Ops Log   │       │ □ Multi-    │    │
│   │   setup     │       │   MVP       │       │   v1        │       │   facility  │    │
│   │             │       │             │       │ □ Blockchain│       │             │    │
│   │ □ Bronze    │       │ □ Perf      │       │   integration       │ □ External  │    │
│   │   ingestion │       │   Analytics │       │             │       │   access    │    │
│   │             │       │             │       │ □ Evidence  │       │             │    │
│   │ □ dbt       │       │ □ Gold      │       │   generation│       │ □ Additional│    │
│   │   models    │       │   tables    │       │             │       │   projects  │    │
│   │             │       │             │       │ □ Meeting   │       │             │    │
│   │ □ Superset  │       │ □ Ops Log   │       │   intake    │       │ □ Commercial│    │
│   │   setup     │       │   design    │       │   MVP       │       │   pilot     │    │
│   │             │       │             │       │             │       │             │    │
│   └─────────────┘       └─────────────┘       └─────────────┘       └─────────────┘    │
│         │                     │                     │                     │            │
│         ▼                     ▼                     ▼                     ▼            │
│   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐    │
│   │ MILESTONE:  │       │ MILESTONE:  │       │ MILESTONE:  │       │ MILESTONE:  │    │
│   │ Data        │       │ Dashboards  │       │ Audit-ready │       │ Production  │    │
│   │ queryable   │       │ in use      │       │ Ops Log     │       │ multi-site  │    │
│   └─────────────┘       └─────────────┘       └─────────────┘       └─────────────┘    │
│                                                                                          │
│   ─────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                          │
│   DEPENDENCIES:                                                                          │
│   • Q1: Infrastructure hosting decision needed                                           │
│   • Q2: Nick's Superset scenario input needed                                           │
│   • Q3: NRC feedback on blockchain audit approach                                       │
│   • Q4: Partner facility identified for multi-site pilot                                │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Dependencies & Risks

### 9.1 Critical Dependencies

| Dependency | Owner | Status | Mitigation |
|------------|-------|--------|------------|
| Infrastructure hosting decision | Team | Pending | K3D for local dev |
| Superset scenario requirements | Nick Luciano | In Progress | Draft scenarios created |
| GitLab API access | IT | Available | N/A |
| MPACT output format documentation | Simulation team | Needed | Reverse engineer |
| NRC audit requirements clarity | Facility | Ongoing | Conservative approach |

### 9.2 Risk Register

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Hosting delays | Medium | High | Local K3D development continues |
| Scope creep | High | Medium | Strict prioritization, MVP focus |
| Data quality issues | Medium | Medium | dbt tests, quality gates |
| Adoption resistance | Medium | Medium | Early user involvement, training |
| Blockchain complexity | Medium | Medium | Immudb fallback for dev |
| **Cyber-physical attack** | Low | Critical | Threat modeling, signed sensor data, air-gap option |
| **AI/LLM safety incident** | Medium | High | Safety framework, human-in-the-loop, prohibited actions |
| **Sensor conflict undetected** | Medium | High | Reconciliation layer, quality flags, alerts |
| **Autonomy mode confusion** | Medium | High | Clear UI indicators, mandatory logging, fault reversion |
| **Model tampering** | Low | Critical | Checksums, version control, validation before deployment |

---

## 10. Appendices

### A. Related Documents

- Neutron OS Technical Specification (companion document)
- [Reactor Ops Log PRD](../reactor-ops-log-prd.md)
- Data Platform PRD
- Superset Scenarios for Review
- Architecture Decision Records (ADRs)

### B. Stakeholder Sign-off

| Stakeholder | Role | Date | Signature |
|-------------|------|------|-----------|
| [TBD] | Product Owner | | |
| [TBD] | Technical Lead | | |
| Nick Luciano | Domain Expert | | |
| [TBD] | Facility Representative | | |

### C. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-01-15 | Auto-generated | Initial draft for review |

---

*Document generated: January 15, 2026*
