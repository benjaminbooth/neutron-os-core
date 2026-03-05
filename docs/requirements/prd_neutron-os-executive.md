# Neutron OS — Executive Product Requirements

**Nuclear Energy Unified Technology for Research, Operations & Networks**

---

| Property | Value |
|----------|-------|
| Version | 1.0 |
| Last Updated | 2026-01-21 |
| Status | Active |
| Product Owner | Ben Booth |

---

## What is Neutron OS?

Neutron OS is a **modular digital platform for nuclear facilities** that unifies data management, operations tracking, experiment scheduling, and analytics into a single system. It replaces fragmented workflows (paper logs, spreadsheets, phone calls, email calendars) with integrated digital tools.

---

## Who is it for?

```mermaid
flowchart LR
    ROOT((Neutron OS Users))
    
    ROOT --- OPS[Operations]
    ROOT --- RES[Research]
    ROOT --- ADM[Administration]
    ROOT --- EXT[External]
    
    OPS --- RO[Reactor Operators]
    OPS --- SRO[Senior Reactor Operators]
    OPS --- RM[Reactor Manager]
    OPS --- HP[Health Physics]
    
    RES --- GR[Graduate Researchers]
    RES --- PI[Principal Investigators]
    RES --- VS[Visiting Scientists]
    
    ADM --- FD[Facility Director]
    ADM --- CO[Compliance Officers]
    ADM --- NRC[NRC Inspectors]
    
    EXT --- MIC[Medical Isotope Customers]
    EXT --- CS[Courier Services]
    
    style ROOT fill:#1565c0,color:#fff,stroke:#0d47a1
    style OPS fill:#2e7d32,color:#fff,stroke:#1b5e20
    style RO fill:#4caf50,color:#fff,stroke:#2e7d32
    style SRO fill:#4caf50,color:#fff,stroke:#2e7d32
    style RM fill:#4caf50,color:#fff,stroke:#2e7d32
    style HP fill:#4caf50,color:#fff,stroke:#2e7d32
    style RES fill:#5d4037,color:#fff,stroke:#3e2723
    style GR fill:#8d6e63,color:#fff,stroke:#5d4037
    style PI fill:#8d6e63,color:#fff,stroke:#5d4037
    style VS fill:#8d6e63,color:#fff,stroke:#5d4037
    style ADM fill:#1976d2,color:#fff,stroke:#0d47a1
    style FD fill:#42a5f5,color:#fff,stroke:#1565c0
    style CO fill:#42a5f5,color:#fff,stroke:#1565c0
    style NRC fill:#42a5f5,color:#fff,stroke:#1565c0
    style EXT fill:#00796b,color:#fff,stroke:#004d40
    style MIC fill:#26a69a,color:#fff,stroke:#00796b
    style CS fill:#26a69a,color:#fff,stroke:#00796b
    linkStyle default stroke:#777777,stroke-width:3px
```

---

## Product Modules

Neutron OS is modular. Facilities enable only what they need.

### Core Infrastructure

| Module | Purpose | PRD | Default |
|--------|---------|-----|---------|  
| **Core Platform** | Data lakehouse, authentication, dashboards | [Data Platform PRD](prd_data-platform.md) | Required |
| **Scheduling System** | Cross-cutting time management, resource allocation | [Scheduling System PRD](prd_scheduling-system.md) | Required |
| **Compliance Tracking** | Cross-cutting regulatory monitoring, evidence generation | [Compliance Tracking PRD](prd_compliance-tracking.md) | Required |

### Application Modules

| Module | Purpose | PRD | Default |
|--------|---------|-----|---------|  
| **Reactor Ops Log** | Operations logging, console checks, shift handoffs | [Reactor Ops Log PRD](prd_reactor-ops-log.md) | On |
| **Experiment Manager** | Sample lifecycle, metadata, results correlation | [Experiment Manager PRD](prd_experiment-manager.md) | On |
| **Analytics Dashboards** | Superset visualizations, KPIs, trending | [Analytics PRD](prd_analytics-dashboards.md) | On |
| **Medical Isotope Production** | Customer orders, QA/QC, shipping | [Medical Isotope PRD](prd_medical-isotope.md) | Off |

### Future Modules

| Module | Purpose | PRD | Default |
|--------|---------|-----|---------|  
| **Training** | Qualification tracking, requal scheduling, records | *(future PRD)* | Off |
| **Personnel** | Staff directory, certifications, contact info | *(future PRD)* | Off |
| **Search / AI** | RAG, workflow agents, tuned LLMs | *(future PRD)* | Off |
| **Connections** | External system integrations | *(future PRD)* | Off |

This swimlane diagram shows how different users interact with Neutron OS throughout a typical week:

```mermaid
flowchart LR
    %% Time headers
    Mon[Monday]:::timeHeader
    Tue[Tuesday-Thursday]:::timeHeader  
    Fri[Friday]:::timeHeader
    
    %% Operator Lane
    Op1[Check facility<br/>display]:::operator
    Op2[30-min console checks<br/>Log sample ops]:::operator
    Op3[End-of-shift<br/>review]:::operator
    
    %% Reactor Manager Lane
    RM1[Review<br/>schedule]:::manager
    RM2[Approve experiment<br/>& production requests]:::manager
    RM3[Review compliance<br/>Check burnup]:::manager
    
    %% Researcher Lane
    Rs1[Check availability<br/>Review samples]:::researcher
    Rs2[Submit metadata<br/>Request reactor time]:::researcher
    Rs3[Analyze<br/>experiment data]:::researcher
    
    %% Production Manager Lane
    PM1[Review<br/>isotope orders]:::production
    PM2[Batch & schedule<br/>production runs]:::production
    PM3[Forecast<br/>next week]:::production
    
    %% QA Officer Lane
    QA2[Perform QA/QC<br/>Generate COA]:::qa
    QA3[Verify<br/>compliance]:::qa
    
    %% Compliance Officer Lane  
    CO2[Monitor<br/>evidence]:::compliance
    CO3[Export<br/>NRC reports]:::compliance
    
    %% Connect time flow
    Mon -.-> Tue -.-> Fri
    
    %% Operator flow
    Mon --> Op1
    Op1 --> Op2
    Op2 --> Op3
    Op3 --> Fri
    
    %% Manager flow
    Mon --> RM1
    RM1 --> RM2
    RM2 --> RM3
    RM3 --> Fri
    
    %% Researcher flow
    Mon --> Rs1
    Rs1 --> Rs2
    Rs2 --> Rs3
    Rs3 --> Fri
    
    %% Production flow
    Mon --> PM1
    PM1 --> PM2
    PM2 --> PM3
    PM3 --> Fri
    
    %% QA flow
    Tue --> QA2
    QA2 --> QA3
    QA3 --> Fri
    
    %% Compliance flow
    Tue --> CO2
    CO2 --> CO3
    CO3 --> Fri
    
    %% Styling
    classDef timeHeader fill:#263238,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef operator fill:#1565c0,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef manager fill:#2e7d32,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef researcher fill:#7b1fa2,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef production fill:#e65100,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef qa fill:#c62828,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef compliance fill:#6a1b9a,color:#ffffff,stroke:#777777,stroke-width:3px
    
    linkStyle default stroke:#777777,stroke-width:3px
```

---

## Module Architecture

```mermaid
flowchart TB
    %% Application Layer
    OpsLog[Reactor<br/>Ops Log]:::active
    Exp[Experiment<br/>Manager]:::active
    Med[Medical<br/>Isotope]:::optional
    Dash[Analytics<br/>Dashboards]:::active
    Train[Training]:::future
    Pers[Personnel]:::future
    AI[Search/AI]:::future
    
    %% Cross-cutting Services
    Sched[Scheduling System]:::crosscut
    Comp[Compliance Tracking]:::crosscut
    
    %% Core Platform
    Core[Core Platform<br/>• Data Lakehouse<br/>• Authentication<br/>• Notifications<br/>• Audit Trail]:::core
    
    %% External Integrations  
    Ext[External Systems<br/>• Reactor DCS<br/>• Google/Outlook<br/>• Shipping APIs<br/>• HR Systems]:::external
    
    %% Connections (simplified)
    OpsLog --> Sched
    Exp --> Sched
    Med --> Sched
    
    OpsLog --> Comp
    Exp --> Comp
    Med --> Comp
    
    Sched --> Core
    Comp --> Core
    Dash --> Core
    
    OpsLog --> Core
    Exp --> Core
    Med --> Core
    
    Core -.-> Ext
    
    %% Styling
    classDef active fill:#2e7d32,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef optional fill:#ff6f00,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef future fill:#9e9e9e,color:#ffffff,stroke:#777777,stroke-width:3px,stroke-dasharray: 5 5
    classDef crosscut fill:#7b1fa2,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef core fill:#1565c0,color:#ffffff,stroke:#777777,stroke-width:3px
    classDef external fill:#424242,color:#ffffff,stroke:#777777,stroke-width:3px
    
    linkStyle default stroke:#777777,stroke-width:3px
```

### Module Status Legend

| Symbol | Status | Description |
|--------|--------|-------------|
| 🟢 Green | **Priority** | First release modules, enabled by default |
| 🟠 Orange | **Optional** | First release modules, off by default |
| ⬜ Grey Dashed | **Future** | Planned for later releases |
| 🟣 Purple | **Cross-cutting** | Shared services used by multiple modules |
| 🔵 Blue | **Core** | Required platform infrastructure |
| ⬛ Dark Grey | **External** | Third-party integrations |

---

## Key Value Propositions

### For Operations Staff

| Pain Point | Neutron OS Solution |
|------------|---------------------|
| Paper logbooks are hard to search | Full-text search across all entries |
| 30-minute checks sometimes missed | Timer alerts, gap detection dashboard |
| Shift handoffs lose context | Digital shift summary, persistent state |
| NRC inspection prep takes days | One-click evidence export |

### For Researchers

| Pain Point | Neutron OS Solution |
|------------|---------------------|
| Scheduling via email is slow | Self-service time slot booking |
| Sample tracking in personal spreadsheets | Unified sample lifecycle management |
| "What were reactor conditions during my experiment?" | Automatic correlation with time-series data |
| Repeating experiment setup is tedious | Templates, smart defaults, AI assistance |

### For Facility Management

| Pain Point | Neutron OS Solution |
|------------|---------------------|
| No visibility into facility utilization | Usage dashboards, capacity planning |
| Compliance gaps discovered during audits | Real-time compliance monitoring |
| Medical isotope orders via phone calls | Customer self-service portal |
| Revenue tracking in spreadsheets | Integrated billing and reporting |

---

## Key Design Decisions

Neutron OS architecture embodies several foundational decisions documented in our [Architecture Decision Records](../adr/README.md):

| Decision | Implication | ADR |
|----------|-------------|-----|
| **Streaming-first architecture** | Real-time is the default; batch processing for aggregations and fallback | [ADR 007](../adr/007-streaming-first-architecture.md) |
| **Open lakehouse (Iceberg + DuckDB)** | No vendor lock-in; on-premise deployment possible | [ADR 003](../adr/003-lakehouse-iceberg-duckdb-superset.md) |
| **Multi-facility via configuration** | Same codebase serves NETL, NRAD, etc. with facility-specific settings | Tech Spec §1.5 |
| **Module-based architecture** | Facilities enable only what they need; Medical Isotope off by default | This PRD |

### Streaming-First Philosophy

**Designed for commercial reactor scale from day one.**

As nuclear commercialization accelerates, fleet operators will manage dozens of units generating petabytes of telemetry. Streaming-first architecture enables:
- **Fleet-wide anomaly detection** — correlate signals across multiple units in real-time
- **Instant operating limit propagation** — safety parameter changes flow immediately to all systems
- **Coordinated load-following** — respond to grid demands across a fleet, not just one unit
- **Graceful scaling** — same architecture handles one research reactor or fifty commercial units

With streaming-first:
- **🟢 Live** is the default — users assume data is current
- **⚠️ Stale** warnings only appear when streaming is degraded
- Batch processing handles historical aggregations and disaster recovery

### Deployment Architecture

```mermaid
flowchart TB
    subgraph Cloud["☁️ Cloud Infrastructure"]
        subgraph Streaming["Real-Time Layer"]
            Kafka[Apache Kafka]
            Flink[Apache Flink]
            Redis[(Redis Cache)]
        end
        
        subgraph Storage["Storage Layer"]
            S3[(S3/Object Storage)]
            Iceberg[(Apache Iceberg)]
            TimeSeries[(Time Series DB)]
        end
        
        subgraph Compute["Compute Layer"]
            DuckDB[DuckDB Engine]
            Superset[Apache Superset]
            API[REST/GraphQL APIs]
        end
    end
    
    subgraph OnPrem["On-Premise"]
        subgraph Sensors["Sensor Network"]
            DCS[Reactor DCS]
            Rad[Radiation Monitors]
            Env[Environmental Sensors]
        end
        
        subgraph Edge["Edge Computing"]
            Gateway[IoT Gateway]
            Buffer[Local Buffer]
            Process[Edge Processing]
        end
    end
    
    subgraph Users["👥 User Access"]
        Web[Web Portal]
        Mobile[Mobile Apps]
        Desktop[Desktop Client]
        API_Client[API Clients]
    end
    
    Sensors --> Gateway
    Gateway --> Buffer
    Buffer --> Kafka
    Kafka --> Flink
    Flink --> Iceberg
    Flink --> Redis
    Flink --> TimeSeries
    
    Iceberg --> DuckDB
    DuckDB --> Superset
    DuckDB --> API
    
    API --> Web
    API --> Mobile
    API --> Desktop
    API --> API_Client
    
    Redis --> API
    
    style Cloud fill:#e3f2fd,color:#000000
    style OnPrem fill:#f3e5f5,color:#000000
    style Users fill:#e8f5e9,color:#000000
    linkStyle default stroke:#777777,stroke-width:3px
```

---

## Phased Rollout

```mermaid
gantt
    title Neutron OS Deployment Phases
    dateFormat  YYYY-MM
    section Phase 1
    Data Puddle (MVP Dashboards)    :done, p1a, 2026-01, 2026-02
    Data Foundation (Iceberg)       :active, p1b, 2026-01, 2026-03
    section Phase 2
    Reactor Ops Log (Core)          :p2a, 2026-03, 2026-05
    Experiment Manager (Core)       :p2b, 2026-03, 2026-05
    section Phase 3
    Scheduling Integration          :p3a, 2026-05, 2026-07
    Medical Isotope (if enabled)    :p3b, 2026-06, 2026-08
    section Phase 4
    AI/LLM Features                 :p4, 2026-08, 2026-12
    Multi-Facility Support          :p5, 2026-10, 2027-02
```

---

## Data Flow & Integration

```mermaid
flowchart LR
    subgraph Input["Data Sources"]
        Manual[Manual Entry • Console checks • Sample data • Maintenance logs]
        Auto[Automated • DCS sensors • Radiation monitors • Environmental]
        External[External • Customer orders • Shipping status • Weather API]
    end
    
    subgraph Process["Processing"]
        Stream[Stream Processing • Real-time alerts • Anomaly detection • Compliance checks]
        Batch[Batch Processing • Daily summaries • Monthly reports • Trend analysis]
        ML[ML/AI Pipeline • Predictive maintenance • Optimization • Smart defaults]
    end
    
    subgraph Store["💾 Storage Layers"]
        Bronze[(Bronze Raw data)]
        Silver[(Silver Cleaned data)]
        Gold[(Gold Analytics-ready)]
    end
    
    subgraph Output["📤 Outputs"]
        Dash[Dashboards • Operations • Compliance • Analytics]
        Reports[Reports • NRC export • Shift summary • Monthly stats]
        Alerts[Alerts • Safety limits • Missed checks • System health]
    end
    
    Manual --> Stream
    Auto --> Stream
    External --> Batch
    
    Stream --> Bronze
    Batch --> Bronze
    Bronze --> Silver
    Silver --> Gold
    
    Silver --> ML
    ML --> Gold
    
    Gold --> Dash
    Gold --> Reports
    Stream --> Alerts
    
    style Input fill:#fff3e0,color:#000000
    style Process fill:#e8f5e9,color:#000000
    style Store fill:#e3f2fd,color:#000000
    style Output fill:#f3e5f5,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## Compliance & Safety Framework

```mermaid
flowchart TB
    subgraph Regulations["Regulatory Requirements"]
        NRC[NRC 10 CFR • Part 50/55 • Reporting • Records]
        DOE[DOE Orders • Safety • Security • Training]
        State[State/Local • Environmental • Emergency • Health]
    end
    
    subgraph Monitoring["Continuous Monitoring"]
        Check30[30-Min Checks ✅ Auto-tracked ⚠️ Gap detection Compliance %]
        Limits[Operating Limits 🔴 Hard stops 🟡 Warnings 🟢 Normal]
        Training[Training Currency 👤 Individual 📅 Expiration 🔄 Renewal]
    end
    
    subgraph Actions["⚡ Automated Actions"]
        Alert[Alert Generation • SMS/Email • Console popup • Manager escalation]
        Lock[System Interlocks • Prevent operation • Require approval • Force compliance]
        Report[Auto-Reporting • Daily summary • Exception reports • Audit trail]
    end
    
    subgraph Evidence["📁 Compliance Evidence"]
        Logs[(Operation Logs)]
        Certs[(Certifications)]
        Audits[(Audit Trail)]
        Exports[(NRC Exports)]
    end
    
    NRC --> Check30
    NRC --> Limits
    DOE --> Training
    State --> Limits
    
    Check30 --> Alert
    Limits --> Lock
    Training --> Lock
    
    Check30 --> Report
    Limits --> Report
    Training --> Report
    
    Report --> Logs
    Alert --> Audits
    Lock --> Audits
    Training --> Certs
    
    Logs --> Exports
    Certs --> Exports
    Audits --> Exports
    
    style Regulations fill:#ffebee,color:#000000
    style Monitoring fill:#e8f5e9,color:#000000
    style Actions fill:#fff3e0,color:#000000
    style Evidence fill:#e3f2fd,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## Success Metrics (Platform-Wide)

| Metric | Target | Timeline |
|--------|--------|----------|
| **Adoption** | 90% of daily operations use Neutron OS | 6 months post-launch |
| **Data Entry Time** | 50% reduction vs. current workflows | 6 months |
| **Compliance Gaps** | Zero missed 30-minute checks | 3 months |
| **Self-Service Rate** | 80% of scheduling via portal (not email) | 6 months |
| **NRC Prep Time** | 75% reduction in inspection prep | 12 months |

---

## Constituent PRDs

Each module has a detailed PRD with user stories, schemas, and mockups:

### Core Infrastructure

1. **[Data Platform PRD](prd_data-platform.md)**
   - Lakehouse architecture (Bronze/Silver/Gold)
   - Time-series ingestion
   - Query layer (DuckDB, Superset)
   - Streaming and batch processing

2. **[Scheduling System PRD](prd_scheduling-system.md)** *(Cross-Cutting)*
   - Unified time slot management
   - Resource allocation and conflicts
   - Multi-module integration
   - Calendar synchronization

3. **[Compliance Tracking PRD](prd_compliance-tracking.md)** *(Cross-Cutting)*
   - Regulatory monitoring (NRC, DOE)
   - 30-minute check enforcement
   - Evidence package generation
   - Real-time compliance dashboards

### Application Modules

4. **[Reactor Ops Log PRD](prd_reactor-ops-log.md)**
   - Console check logging
   - Shift handoffs and summaries
   - Maintenance tracking
   - Tamper-proof audit trail

5. **[Experiment Manager PRD](prd_experiment-manager.md)**
   - Sample lifecycle tracking
   - Metadata and chain of custody
   - Results correlation
   - ROC authorization tracking

6. **[Analytics Dashboards PRD](prd_analytics-dashboards.md)**
   - Reactor Operations dashboard
   - Utilization metrics
   - Fuel burnup visualization
   - Data quality monitoring

### Optional Modules

5. **[Medical Isotope Production PRD](prd_medical-isotope.md)**
   - Customer order portal
   - Production batching
   - QA/QC workflow
   - Shipping and delivery tracking

---

## Module Feature Comparison

| Module | Complexity | Business Value | Priority |
|--------|------------|----------------|----------|
| **Reactor Ops Log** | Medium | Critical | First release |
| **Experiment Manager** | Medium | High | First release |
| **Analytics Dashboards** | Low | High | First release |
| **Medical Isotope Production** | High | Medium | Optional |
| **Scheduling System** | Low | Critical | Core infrastructure |
| **Compliance Tracking** | Low | Critical | Core infrastructure |
| **Training Module** | Medium | Medium | Future |
| **AI/Search** | Very High | High | Future |
| **Personnel** | Low | Low | Future |

### Module Interdependencies

```mermaid
graph TB
    subgraph Foundation["🏗️ Foundation Layer"]
        Core[Core Platform Required]
    end
    
    subgraph Operational["Operational Modules"]
        Ops[Reactor Ops Log]
        Exp[Experiment Manager]
        Med[Medical Isotope]
    end
    
    subgraph Intelligence["🧠 Intelligence Layer"]
        Dash[Analytics]
        AI[AI/Search]
    end
    
    subgraph Support["🛠️ Support Modules"]
        Train[Training]
        Pers[Personnel]
        Conn[Connections]
    end
    
    Core --> Ops
    Core --> Exp
    Core --> Med
    Core --> Dash
    
    Ops --> Dash
    Exp --> Dash
    Med --> Dash
    
    Ops -.-> AI
    Exp -.-> AI
    Dash --> AI
    
    Pers --> Train
    Core --> Pers
    Core --> Conn
    
    Conn -.-> Ops
    Conn -.-> Exp
    Conn -.-> Med
    
    style Foundation fill:#1565c0,color:#fff
    style Operational fill:#2e7d32,color:#fff
    style Intelligence fill:#7b1fa2,color:#fff
    style Support fill:#e65100,color:#fff
    
    linkStyle default stroke:#777777,stroke-width:3px
```

---

## Technical Foundation

For technical architecture, schemas, and implementation details, see:

- **[Neutron OS Master Tech Spec](../specs/neutron-os-master-tech-spec.md)** — Full technical specification
- **[Executive Technical Summary](../specs/neutron-os-executive-summary.md)** — 2-page technical overview

---

## Feedback & Stakeholder Input

This PRD incorporates feedback from:

| Stakeholder | Role | Input Incorporated |
|-------------|------|-------------------|
| Khiloni Shah | Post-Doctoral Nuclear Engineering Researcher | Experiment workflow, facility names, sample metadata |
| Jim (TJ) | NETL TRIGA Manager | Reactor Ops Log requirements, 30-min checks, compliance |
| Nick Luciano | Post-Doctoral Nuclear Engineering Researcher | Time-series data, security, dashboards |

---

## NEUP Research Addendum

This section maps NEUP 2026 proposals to Neutron OS modules and identifies platform enhancements driven by research needs.

### Research-Platform Alignment Matrix

| NEUP Proposal | Primary Module | Integration Type |
|---------------|----------------|------------------|
| DT Framework IRP | Core Platform | Architecture validation |
| Operator LLM Safety | Search/AI (future) | Safety requirements |
| Cyber-Nuclear Security | All modules | Cross-cutting security |
| Virtual Systems Engineer | Search/AI (future) | Agent capabilities |
| Semi-Autonomous Controls | Reactor Ops Log | Autonomy specification |
| KANs / PINNs / ML Neutronics | Analytics (DT) | Surrogate model options |
| Medical Isotope Optimization | Medical Isotope | Production planning AI |
| Resolving Sensor Data Conflicts | Data Platform | Data quality layer |
| Cherenkov Power Monitoring | Data Platform | New sensor modality |

### NEUP Proposal: Operator LLM Safety

**Proposal:** Establishing safety guardrails for LLM use in nuclear operations.

**Gap Addressed:** Future "Search/AI" module lacks safety specifications for operational contexts.

#### LLM Safety Framework

| Interaction Type | Safety Level | Requirements |
|-----------------|--------------|-------------|
| Information lookup | Low | Standard RAG with source citation |
| Procedure assistance | Medium | Cross-reference approved procedures; human confirmation |
| Operational recommendation | High | Multi-model consensus; physics validation; SRO approval |
| Control action suggestion | **Prohibited** | LLM cannot suggest direct control actions |

#### New Requirements for Search/AI Module

| ID | Requirement | Priority |
|----|-------------|----------|
| AI-001 | All LLM responses logged with query, response, sources cited | P0 |
| AI-002 | Confidence scores required for operational queries | P0 |
| AI-003 | Human-in-the-loop mandatory for action-oriented responses | P0 |
| AI-004 | Prompt injection prevention via input sanitization | P1 |

---

### NEUP Proposal: Cyber-Nuclear Security (Topic 11)

**Proposal:** Cybersecurity frameworks specifically for nuclear digital twins.

**Gap Addressed:** Security architecture focuses on auth/authz; lacks cyber-physical threat modeling.

#### Cyber-Physical Security Layer

| Security Domain | Current State | Needed Enhancement |
|-----------------|---------------|-------------------|
| Authentication | ✅ Defined | — |
| Authorization | ✅ Defined | — |
| Sensor integrity | ❌ Not specified | Signed readings, spoofing detection |
| Model tampering | ❌ Not specified | Secure model deployment, validation |
| Air-gap deployment | ❌ Not specified | Network isolation option |

---

### NEUP Proposal: Digital Twin Framework IRP

**Proposal:** Industry-wide standards for nuclear digital twin architectures.

**Supporting PRD Element:** Modular architecture already uses factory/provider pattern enabling multi-facility deployment.

**Recommended Enhancement:** Publish `ReactorProvider` interface as open standard for industry adoption.

---

### Research Collaboration Priorities

| Priority | Proposal | POCs | Contact Reason |
|----------|----------|------|----------------|
| 🔴 Critical | DT Framework IRP | PI TBD; Collab: Ryan Stewart (INL), U Utah | Align Neutron OS architecture with emerging standards |
| 🔴 Critical | Operator LLM Safety | PI TBD; Collab: Ron Boring (INL) | Define safety constraints before AI deployment |
| 🔴 Critical | DT Safety (Cyber-Nuclear) | PI W. Charlton (UT); Collab: C. Gentry (UT), A. Williams (SNL) | Fill security documentation gap |
| 🟡 High | Medical Isotope Optimization | PI B. Collins (UT); Collab: S. Aslam (UT), W. Charlton (UT) | Revenue-generating module enhancement |
| 🟡 High | Semi-Autonomous Controls | PI B. Collins (UT); Collab: S. Aslam (UT), J. Ross (Natural Resources) | Future roadmap acceleration |
| 🟡 High | Resolving Sensor Data Conflicts | PI TBD; Collab: K. Clarno (UT) | Data quality foundation |

**Additional NEUP POCs for Related Proposals:**
- **KANs Reactor Modeling:** PI Majdi Radaideh (U Michigan); Collab: Jeongwon Seo (UT), Cole Gentry (UT)
- **PINNs Self-Shielding:** PI Cole Gentry (UT); Collab: Nicholas Luciano (UT), Yaqi Wang (INL)
- **AI XS Library Tuning:** PI Cole Gentry (UT); Collab: Yaqi Wang (INL), Jesse Brown (ORNL)
- **ML Neutronics Acceleration:** PI Cole Gentry (UT); Collab: Cody Permann (INL)
- **Nuclear LLM Bench:** PI Kevin Clarno (UT); Collab: Derek Booth (UT), Ondrej Chvala (UT)
- **Virtual Systems Engineer:** PI TBD; Collab: Ron Boring (INL)
- **Cherenkov Power Monitoring:** PI W. Charlton (UT); Collab: J. Seo (UT), R. Steward (INL)

*This addendum establishes the research integration framework for Neutron OS evolution.*

---

## Potential Future Partners

| Organization | Capability | Alignment |
|--------------|-----------|-----------|
| **Idaho National Laboratory (INL)** | Advanced reactor design, fuel qualification, material testing | Digital twin for next-generation reactors, isotope production for materials research |
| **Oregon State University** | TRIGA reactor operations, university reactor community network | Peer validation, shared best practices for university digital twin deployment |

---

*Document Status: Active — Updated with stakeholder feedback January 2026*
