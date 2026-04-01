# Neutron OS: Compliance with DOE Requirements for Digital Research Data Management

**The University of Texas at Austin — Nuclear Engineering Computational Research Group**
**Date:** April 2026
**Prepared for:** UT Nuclear Engineering Program Committee
**Contact:** Benjamin Booth, bbooth@utexas.edu

---

## 1. Background and Motivation

Effective October 1, 2025, the U.S. Department of Energy requires all funded research and development awards to include an approved Data Management and Sharing Plan (DMSP). These requirements, informed by the 2022 OSTP Nelson Memo and the NSTC framework for desirable repository characteristics, mandate that federally funded research data be findable, accessible, interoperable, and reusable (FAIR) while respecting security, privacy, and intellectual property constraints.

Nuclear facility research presents unique challenges for DMSP compliance: operational data is subject to NRC retention requirements (10 CFR 50.71), significant portions of experimental data may be export-controlled or restricted under 10 CFR 810, and multi-facility collaboration requires careful management of data sharing agreements across institutional and security boundaries.

Neutron OS is a modular digital platform for nuclear facilities developed at UT Austin that unifies data management, operations tracking, experiment scheduling, and computational analytics. Built on the Axiom framework — a domain-agnostic platform providing core data infrastructure — Neutron OS addresses DOE data management requirements at both the platform level and the nuclear domain level.

## 2. DOE DMSP Requirement Coverage

The DOE DMSP framework specifies five mandatory components. The table below summarizes how Neutron OS, through its Axiom foundation and nuclear-specific extensions, addresses each.

| DOE DMSP Component | Axiom Platform Capability | Neutron OS Nuclear Extension | Status |
|---|---|---|---|
| **1. Validation & Replication** | Apache Iceberg time-travel queries enable point-in-time data recovery and reproducibility. Medallion architecture (Bronze/Silver/Gold) provides progressive data quality validation via automated test suites. Immutable audit trails with HMAC integrity verification. | Nuclear measurement data quality SLOs (temperature, flux, rod position tolerances). Physics model provenance tracking from training data through ROM deployment. Shadow model calibration datasets for measured-vs-predicted validation. | Partially implemented; provenance extensions planned |
| **2. Timely & Fair Access** | Dataset access lifecycle engine (draft → embargoed → published → archived) with configurable embargo durations and automatic transition. Persistent identifier (DOI) minting via DataCite integration at publication. Machine-readable access conditions in metadata. | Export control tier mapping to DMSP sharing limitation categories. Alternative validation documentation for restricted datasets. Over-classification detection alerting. | Planned (Axiom v0.3.x / Neutron OS v0.8.x) |
| **3. Repository Selection** | Repository registry with qualification against NSTC desirable characteristics. Automated deposit via repository APIs. | Pre-configured nuclear data repositories: NNDC, ESS-DIVE, Materials Data Facility, OSTI DOE Data Explorer. ICSBEP/IRPhEP benchmark database targeting for validation data. | Planned (Phase 3) |
| **4. Resource Allocation** | Storage and computational resource metering per facility, project, and user. Usage metrics exportable for budget reporting. | Facility-level resource tracking aligned with NEUP budget categories. DMSP resource justification auto-populated from platform metering. | Planned (Axiom v0.4.x) |
| **5. Sharing Limitations** | Data Sharing Agreement (DSA) templates with machine-enforceable terms. License metadata on all data objects (CC-0, CC-BY, proprietary, restricted). DSA acceptance gates integrated with authorization system. | Three-tier access model (public/restricted/export-controlled) mapped to DOE limitation categories. 8-layer export control defense architecture for classified and controlled data. Automatic DMSP limitation documentation with applicable authority citation (10 CFR 810, EAR, ITAR). | Access tiers implemented; DSA integration planned |

### Additional FAIR Infrastructure

Beyond the five DMSP pillars, Neutron OS provides:

- **Metadata Standards:** Core metadata schema conforming to DataCite Metadata Schema 4.x, extensible with nuclear domain fields (reactor type, core position, isotope, flux, burnup). Metadata exportable as JSON-LD with schema.org vocabulary.
- **Persistent Identifiers:** DOI minting for published datasets, community knowledge corpus entries, and validated computational models. Creator identities linkable to ORCID iDs.
- **Federal Reporting:** Automated OSTI reporting via E-Link 2.0 API for all published datasets, with submission tracking and retry logic.
- **Provenance:** W3C PROV-O compatible provenance graphs for derived datasets. Full lineage tracking for reduced-order models (ROM) from physics code through training data to deployed surrogate.
- **Preservation:** Four-tier retention (90-day hot, 2-year warm, 7-year cold, indefinite archive) exceeding both NRC and DOE minimums. Integrity verification via scheduled checksum validation.

## 3. Operational Advantages for Nuclear Research Programs

Neutron OS provides several capabilities that go beyond minimum DMSP compliance and directly benefit DOE-funded nuclear research programs:

**NEUP Proposal Support.** The `neut dmsp generate` command produces DOE-compliant DMSP drafts pre-populated with facility configuration, repository selections, retention policies, and sharing limitation profiles — reducing proposal preparation effort and ensuring consistency across submissions.

**Multi-Facility Federation.** The Axiom federation architecture enables secure, trust-managed data sharing across DOE laboratory and university sites. Federated model validation campaigns can generate shared validation reports with persistent identifiers for all contributing datasets, directly supporting multi-institutional NEUP awards.

**Offline-First Architecture.** Nuclear facilities frequently operate in network-constrained or air-gapped environments. Neutron OS queues all external operations (PID minting, OSTI reporting, repository deposit) for synchronization when connectivity is restored, ensuring DMSP compliance is never blocked by network availability.

**Compliance Dashboard.** Real-time DMSP compliance monitoring shows: datasets produced vs. shared, embargo status, PID coverage, OSTI reporting status, and repository deposit status — providing audit-ready evidence of ongoing compliance throughout the award period.

## 4. Current Status and Roadmap

The Axiom framework (v0.2.0) and Neutron OS (v0.7.0) currently implement the foundational data platform: medallion architecture, multi-tier access control, immutable audit trails, export control defense, and offline-first operation. DOE-specific FAIR data services, persistent identifiers, and DMSP lifecycle management are in active requirements definition (this assessment) with implementation planned across three phases:

- **Phase 1 (2026 Q3–Q4):** Core metadata schema, PID infrastructure, embargo engine, DMSP templates, license metadata
- **Phase 2 (2027 Q1–Q2):** OSTI reporting, DMSP compliance dashboard, provenance graphs, NEUP DMSP generator, resource metering
- **Phase 3 (2027 Q3+):** Nuclear repository deposit automation, federated FAIR catalog, cross-site validation reports

This phased approach ensures that Neutron OS deployments at UT Austin and partner institutions will be fully DOE DMSP-compliant for NEUP and LDRD proposals submitted from 2027 onward, with foundational capabilities available for 2026 submissions.

---

*This document summarizes capabilities described in the Axiom Federal Data Management PRD and the Neutron OS DOE Data Management Extensions PRD. Full requirements, technical specifications, and architecture decisions are maintained in the project documentation repositories.*
