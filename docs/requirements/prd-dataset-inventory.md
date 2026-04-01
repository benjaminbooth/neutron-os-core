# Product Requirements Document: Research Dataset Inventory & DMSP Migration

> **Implementation Status: 🔲 Not Started** — This PRD catalogs known research datasets across UT Computational NE projects and defines the work to migrate them into the Axiom/Neutron OS data infrastructure with DOE DMSP compliance.

**Product:** Neutron OS Dataset Inventory
**Status:** Draft
**Last Updated:** 2026-04-01
**Parent:** [Executive PRD](prd-executive.md)
**Related:** [DOE Data Management](prd-doe-data-management.md), [Data Platform](prd-data-platform.md), [Model Corral](prd-model-corral.md)
**Upstream:** [Axiom Federal Data Management PRD](https://github.com/…/axiom/docs/requirements/prd-doe-data-management.md)

---

## Executive Summary

The UT Computational NE workspace contains research data across 10+ project directories. As Neutron OS data infrastructure comes online (Model Corral, lakehouse, RAG), these datasets must be inventoried, classified by DOE DMSP applicability, and migrated into the managed platform with appropriate metadata, persistent identifiers, and access controls.

This PRD defines what we have, what DOE classification applies, and what work is needed to bring each dataset into compliance.

---

## Dataset Inventory

### Tier 1: Clearly DOE DMSP-Applicable

These datasets are produced by or directly support federally funded nuclear research. When hosted on DOE-funded infrastructure or produced under NEUP/LDRD awards, full DMSP compliance is required.

| Dataset | Project | Data Type | Current Format | Current Location | Estimated Size |
|---|---|---|---|---|---|
| TRIGA reactor operational data | `TRIGA_Digital_Twin/` | Time-series (power, temperature, rod position, neutron flux) | CSV, HDF5 | Local files | TBD |
| Physics model input decks | Model Corral (planned) | MCNP, VERA/MPACT, SAM, Griffin, OpenMC input files | Text, XML, HDF5 | Scattered across project dirs | TBD |
| ROM training data | `TRIGA_Digital_Twin/`, `CoreForge/` | Simulation outputs used to train surrogate models | HDF5, NumPy, CSV | Local files | TBD |
| ROMs (trained surrogates) | Model Corral (planned) | ONNX, WASM, PyTorch model weights + metadata | Binary + YAML | Local files | TBD |
| Digital twin validation data | `TRIGA_Digital_Twin/` | Shadow model predictions vs. measured values | CSV, JSON | Local files | TBD |
| Irradiation experiment results | `TRIGA_Digital_Twin/` | Sample tracking, fluence, activity measurements | CSV, spreadsheets | Local files + paper | TBD |
| Benchmark datasets | `progression_problems/` | Computational benchmarks (ICSBEP/IRPhEP) | Text input decks + output | Local files | TBD |

### Tier 2: Conditionally DMSP-Applicable

DMSP applies if produced under a DOE-funded award. Funding source must be confirmed per project.

| Dataset | Project | Data Type | Current Format | Funding Status |
|---|---|---|---|---|
| Bubble flow loop experimental + simulation data | `Bubble_Flow_Loop_Digital_Twin/` | Two-phase flow measurements, CFD outputs | TBD | Confirm funding source |
| MIT irradiation loop data | `MIT_Irradiation_Loop_Digital_Twin/` | Irradiation experiment telemetry + simulation | TBD | Confirm funding source |
| MSR simulation outputs | `MSR_Digital_Twin_Open/` | Molten salt reactor simulation results | TBD | Confirm funding source |
| TRIGA digital twin model outputs | `TRIGA_Digital_Twin/` | Operational predictions, calibration runs | TBD | Likely NEUP-funded |
| Off-gas system experimental data | `OffGas_Digital_Twin/` | Gas composition measurements, simulation | TBD | Confirm funding source |
| MPACT validation results | `MPACTPy/` | Benchmark comparison outputs | TBD | Confirm funding source |
| CoreForge/FlowForge tool outputs | `CoreForge/`, `FlowForge/` | Generated core configurations, flow analyses | TBD | Confirm funding source |

### Tier 3: Not DOE Datasets

These are not research data in the DOE DMSP sense. No DMSP migration required, though FAIR best practices are still recommended.

| Item | Reason |
|---|---|
| Source code (all repos) | Software, not data. Covered by DOE software sharing guidance separately. |
| PRDs, tech specs, ADRs | Publications/documentation, not research data. |
| RAG community corpus | Curated reference knowledge. Exempt unless containing funded research outputs. |
| Configuration files, infrastructure code | Operational artifacts, not research output. |
| Runtime data (sessions, inbox, logs) | Ephemeral platform state, not research data. |

---

## Migration Requirements

### Per-Dataset Migration Checklist

Every Tier 1 and confirmed Tier 2 dataset must complete this checklist before it is considered DMSP-compliant:

| # | Requirement | Maps To |
|---|---|---|
| 1 | **Ingest into managed storage** — dataset moved from ad-hoc local files into Axiom data platform (Iceberg Bronze tier for raw data, Model Corral for models/ROMs) | Data Platform PRD |
| 2 | **Core metadata assigned** — title, creator(s), description, date_created, license, funding_source, award_number, PI, institution | Axiom META-001, META-006 |
| 3 | **Nuclear metadata assigned** — reactor_type, facility_id, measurement_type, and domain-specific fields per dataset type | NOS NMETA-001 through NMETA-005 |
| 4 | **PID minted** — persistent identifier assigned via configured PID provider (DataCite DOI, ARK, or Handle) | Axiom PID-001, PID-002 |
| 5 | **License declared** — SPDX license identifier assigned (CC-BY-4.0 for open data, restricted for EC, etc.) | Axiom DSA-001 |
| 6 | **Access tier assigned** — public, restricted, or export_controlled with documented justification for non-public tiers | NOS EC-DMSP-001 |
| 7 | **Retention tier assigned** — operational (2yr), regulatory (7yr), or permanent, validated against NRC minimums | NOS RET-001 through RET-005 |
| 8 | **Provenance documented** — creation method, source instruments/codes, processing chain, parent datasets linked | Axiom PROV-001 through PROV-004 |
| 9 | **Data dictionary created** — field names, types, units, precision, controlled vocabulary references | Axiom META-005 |
| 10 | **Quality SLOs defined** — measurement tolerances documented (where applicable) | NOS DQ-001, DQ-002 |
| 11 | **Repository target selected** — appropriate external repository identified from registry (NNDC, ESS-DIVE, MDF, OSTI) | NOS NREPO-001 through NREPO-004 |
| 12 | **OSTI reported** (if published) — dataset registered with DOE OSTI via E-Link API | Axiom RPT-001 |

---

## Migration Work Items

### Phase 1: Inventory & Classify (aligns with M1 — Model Corral)

| # | Work Item | Depends On | Acceptance Criteria |
|---|---|---|---|
| INV-001 | Audit all Tier 1 project directories for data artifacts (file types, sizes, formats, locations) | — | Inventory table above populated with actual sizes and format details |
| INV-002 | Confirm funding source for all Tier 2 datasets | — | Each Tier 2 row has confirmed funding status |
| INV-003 | Classify each dataset by access tier (public / restricted / export_controlled) | INV-001 | Access tier column populated; EC datasets flagged for review |
| INV-004 | Identify datasets currently in ad-hoc formats needing conversion to open formats (Parquet, HDF5, CSV) | INV-001 | Conversion list with source → target format |

### Phase 2: Model & ROM Migration (aligns with M1 — Model Corral)

| # | Work Item | Depends On | Acceptance Criteria |
|---|---|---|---|
| MIG-001 | Migrate 10+ TRIGA physics models into Model Corral with model.yaml manifests | M1 complete | Models searchable via `neut model search`; manifests include license + funding_source |
| MIG-002 | Migrate existing ROMs into Model Corral with training provenance | M1 complete | ROM → physics model lineage visible via `neut model lineage` |
| MIG-003 | Migrate benchmark input decks from `progression_problems/` | M1 complete | Benchmarks searchable; linked to ICSBEP/IRPhEP references |
| MIG-004 | Assign core + nuclear metadata to all migrated models | MIG-001 | All 12 checklist items satisfied per model |

### Phase 3: Operational & Experimental Data Migration (aligns with M4 — DOE Layer)

| # | Work Item | Depends On | Acceptance Criteria |
|---|---|---|---|
| MIG-005 | Ingest TRIGA operational time-series into Iceberg Bronze tier | M0 DB + Iceberg operational | Raw data queryable via DuckDB |
| MIG-006 | Ingest digital twin validation datasets (measured vs. predicted) | M0 DB | Validation data linked to Model Corral entries by model_id |
| MIG-007 | Ingest irradiation experiment results | M0 DB | Sample tracking data with nuclear metadata |
| MIG-008 | Create dbt Silver transforms for data quality validation | MIG-005 through MIG-007 | Quality tests running; SLO violations flagged |
| MIG-009 | Assign PIDs to all published datasets | M4 PID infrastructure | DOIs minted; resolvable via configured PID provider |
| MIG-010 | Generate DMSP compliance report covering all migrated datasets | M4 DMSP dashboard | Report shows coverage: % with PIDs, % with licenses, % with metadata |

### Phase 4: Conditional Dataset Migration (as funding confirmed)

| # | Work Item | Depends On | Acceptance Criteria |
|---|---|---|---|
| MIG-011 | Migrate confirmed Tier 2 datasets through same checklist | INV-002 + M4 | Each confirmed dataset satisfies 12-point checklist |
| MIG-012 | Register published datasets with OSTI | M4 RPT infrastructure | OSTI submission accepted; DOI cross-referenced |
| MIG-013 | Deposit datasets to selected external repositories | M4 REPO infrastructure | Deposit confirmed at target repository; metadata harvested |

---

## Tracking

This PRD tracks migration progress at the dataset level. As each dataset completes the 12-point checklist, it is marked complete in the table below. This table will be populated as INV-001 and INV-002 complete.

| Dataset | Tier | Funding Confirmed | Ingested | Metadata | PID | License | Access Tier | Retention | Provenance | Dictionary | Quality SLOs | Repository | OSTI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| *(populated after INV-001)* | | | | | | | | | | | | | |

---

## Relationship to Execution Plan

| Migration Phase | Execution Plan Milestone | Timeline |
|---|---|---|
| Phase 1 (Inventory) | M1: Model Corral | Weeks 2–5 |
| Phase 2 (Models/ROMs) | M1: Model Corral | Weeks 3–6 |
| Phase 3 (Operational data) | M4: DOE Data Management | Weeks 10–14 |
| Phase 4 (Conditional) | M4: DOE Data Management | Weeks 12+ |
