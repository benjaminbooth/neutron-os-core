| | |
|-----------------------------------|------------------------------------------------|
| Submission Deadline | January 28, 2026 (Pre-Application) |
| Full Proposal (if invited) | April 2026 |
| Lead Institution | The University of Texas at Austin |
| PI | [TBD] |
| Estimated Budget | $800,000 - $1,200,000 over 3 years (pending NOFO confirmation) |

---

# Proposed Title

**Neutron OS: An Integrated Platform for Research Reactor Digital Twins and Data-Driven Operations**

---

# The Core Problem

Research reactors face a fundamental operational challenge: **between sensor readings, the reactor state is unknown.**

- Physical sensors require ~100ms to measure, process, and transmit reactor state
- Critical transients can develop in <50ms
- Operators must maintain **conservative safety margins** to account for this uncertainty
- Result: reactors cannot safely operate near full capacity

Beyond this real-time challenge, university reactors struggle with **fragmented data infrastructure**—operational logs in spreadsheets, simulation outputs in HDF5 files, experimental records in paper notebooks. This fragmentation creates compliance risk, prevents effective analysis, and makes cross-facility benchmarking impractical.

---

# Proposed Solution: Digital Twin Data Platform

We propose a **data platform for nuclear digital twins**—shared infrastructure that connects reactor sensors, physics simulations, and operational decisions.

**Core capabilities:**
- **Simulation-augmented operations:** Digital twin predictions fill the temporal gaps between sensor readings
- **Unified data management:** All reactor data (sensors, simulations, logs, experiments) in queryable, versioned storage
- **Reproducible analytics:** Versioned data with auditable pipelines for research validation
- **Compliance-ready architecture:** Append-only storage with audit trails for regulatory inspection

**Key Capability:** Digital twin models predict reactor state in ~10ms, providing continuous state *estimation* between sensor readings. When actual sensor data arrives, predictions are validated and models are refined.

> **Honest framing:** Predictions are estimates with uncertainty bounds, not perfect knowledge. Achieving trustworthy accuracy is a core research objective of this project.

The architecture is designed to grow: the same data contracts that power digital twin predictions can support compliance automation, AI-assisted queries, and multi-facility collaboration as needs evolve.

---

# Five Digital Twin Use Cases

The platform supports the full spectrum of reactor management:

| Use Case | Value | Deliverable |
|----------|-------|-------------|
| **1. Real-Time State Estimation** | Fill gaps between sensor readings with validated predictions | Operations dashboard with DT overlay |
| **2. Fuel Management** | Track burnup, identify hot spots, optimize reload patterns | Fuel analytics dashboard |
| **3. Predictive Maintenance** | Anticipate component degradation before failure | Maintenance scheduling tools |
| **4. Experiment Planning** | Simulate irradiations before execution, predict activation | Experiment planning interface |
| **5. Research Validation** | Compare physics codes to operational data | Model validation framework |

---

# Technical Approach

## Development Strategy: Dual-Track Delivery

We pursue **immediate value and solid architecture in parallel**:

| Track | Deliverable | Timeline |
|-------|-------------|----------|
| **MVP ("Data Puddle")** | Superset dashboards on DMSRI-web PostgreSQL | Immediate |
| **Foundation** | Full lakehouse with proper data contracts | Q1-Q2 2026 |

The MVP delivers visible analytics now—stakeholders see dashboards this quarter. (DMSRI-web does minimal aggregation/scrubbing for Plotly today; connecting Superset gives immediate visibility while we build proper infrastructure.) The foundation ensures we don't rebuild when complexity increases. The puddle migrates onto proper infrastructure once validated.

## Data Architecture
Modern lakehouse (Apache Iceberg + DuckDB) with medallion layers:
- **Bronze:** Raw sensor streams, simulation outputs, logs (immutable)
- **Silver:** Validated, cleaned data with `source='measured'` vs `source='modeled'`
- **Gold:** Analytics-ready aggregates for dashboards

## Digital Twin Integration
Clear separation of measured vs. modeled data. Any simulation code (MPACT, OpenMC, point kinetics) can register predictions alongside sensor readings. Side-by-side visualization enables continuous validation.

## Uncertainty Quantification (Research Contribution)
Surrogate models trade fidelity for speed. This project will develop validated uncertainty bounds so operators know how much to trust predictions—a key research gap in nuclear digital twins.

## Agentic Data Ecosystem
LLM-powered pipelines process unstructured inputs (meeting transcripts, documents, notifications) into structured outputs (action items, requirements, GitLab issues). Enables AI-assisted querying of reactor data.

## Regulatory Compliance
Append-only ledger tables with cryptographic verification. Evidence package generation for NRC inspections with proof of record integrity.

---

# Multi-Facility Design

The architecture supports **multi-tenant deployments** with row-level security, enabling future cross-facility collaboration while maintaining data isolation. Schema standards and APIs enable benchmarking across reactor sites (with explicit consent).

*Current focus: UT Austin NETL. Architecture designed for adoption across the full reactor ecosystem—university research reactors, national lab test facilities, and commercial power plants. The same data infrastructure that validates digital twins on a 1 MW TRIGA can scale to support fleet operations on advanced commercial reactors.*

**Future opportunity:** Cross-site model validation—comparing TRIGA physics predictions across facilities like NETL (UT Austin) and NRAD (INL)—would significantly strengthen confidence in digital twin accuracy. The platform schema is designed to be compatible with INL's DeepLynx ontology standards, enabling future data exchange. However, core deliverables do not depend on external partnerships; UT can validate and demonstrate the full platform on NETL data alone.

---

# Deliverables

| Year | Capabilities | Research Outputs |
|------|--------------|------------------|
| **Year 1** | Core platform, electronic logbook, real-time ops dashboard, DT prediction overlay | Open-source platform release |
| **Year 2** | Fuel analytics, experiment tracking, MPACT integration, evidence package generator | Uncertainty quantification methodology |
| **Year 3** | Agentic query tools, adoption guide, cross-facility demo (if partners available) | Publications on DT validation |

---

# Relevance to DOE-NE Mission

| DOE Priority | Project Contribution |
|--------------|---------------------|
| **Reactor Safety** | Simulation-augmented operations reduce blind spots between sensor readings |
| **Regulatory Modernization** | Standardized audit infrastructure for NRC compliance across facilities |
| **Fleet Sustainability** | Reusable platform benefits entire university reactor community |
| **Workforce Development** | Students trained in modern data engineering + nuclear operations |
| **Research Infrastructure** | Validated datasets for physics code benchmarking and ML model training |

---

# Critical Pathway to Advanced Reactor Commercialization

**The commercial imperative:** Advanced reactor vendors (X-energy, Kairos, TerraPower, Oklo) will require validated digital twin infrastructure for NRC licensing and commercial operations. The NRC is developing regulatory frameworks for simulation-informed operations, but needs demonstrated, validated approaches before approving commercial deployment.

**Research reactors are the proving ground:**

| Challenge | Why Research Reactors First |
|-----------|---------------------------|
| **Regulatory acceptance** | NRC can evaluate DT validation approaches on operating reactors without commercial deployment risk |
| **Uncertainty quantification** | Develop trustworthy accuracy bounds where mistakes don't cost $billions |
| **Operational data** | Generate validated datasets that inform commercial reactor predictions |
| **Standards development** | University work shapes commercial DT standards before vendors lock in proprietary approaches |

**Technology transfer pathway:**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  RESEARCH       │    │  DEMONSTRATION  │    │  COMMERCIAL     │
│  REACTORS       │───▶│  REACTORS       │───▶│  DEPLOYMENT     │
│  (This project) │    │  (NRIC, Hermes) │    │  (Fleet ops)    │
│                 │    │                 │    │                 │
│  • Validate UQ  │    │  • Scale testing│    │  • Licensed DTs │
│  • Train        │    │  • NRC review   │    │  • Autonomous   │
│    workforce    │    │  • Vendor pilot │    │    operations   │
│  • Open-source  │    │                 │    │                 │
│    platform     │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Workforce pipeline:** Students trained on this infrastructure at UT Austin become the engineers deploying digital twins at advanced reactor sites. This is not just research—it's building the human capital the industry needs.

**Open-source as commercialization strategy:** By developing an open-source platform, we enable:
- Vendors to adopt/fork without licensing barriers
- Startups to build on proven infrastructure rather than starting from zero
- Regulatory confidence through transparent, auditable implementations
- Standards convergence across the industry

> **Bottom line:** There is no path to simulation-augmented commercial reactor operations without first validating the approach on research reactors. This project is that critical first step.

---

# Why This Project, Why Now

1. **Sensor technology hasn't kept pace** with computational capability—simulations can now predict faster than sensors can measure
2. **Digital twin capabilities are outpacing validation practices**—the field needs rigorous uncertainty quantification to match the promise of faster predictions
3. **University reactors need modern infrastructure**—most still rely on paper logs and spreadsheets
4. **Advanced reactor deployment is imminent**—Kairos Hermes reactor expected online 2027; industry needs validated DT infrastructure *before* commercial licensing
5. **Open-source creates leverage**—one platform can benefit dozens of facilities and multiple vendors

---

*DRAFT - For internal review before submission*

Contact: bdb3732@utexas.edu
