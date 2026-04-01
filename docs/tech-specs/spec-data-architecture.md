# Data Architecture Specification

**Part of:** [Neutron OS Master Tech Spec](spec-executive.md)

---

> **Scope:** This document specifies the Neutron OS data architecture, including the medallion pattern, Apache Iceberg configuration, schema definitions, data quality framework, and streaming readiness.

| Property | Value |
|----------|-------|
| Version | 0.2 |
| Last Updated | 2026-03-17 |
| Status | Draft |
| Related | [DOE Data Management & Sharing PRD](../requirements/prd-doe-data-management.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Medallion Architecture](#2-medallion-architecture)
3. [Layer Specifications](#3-layer-specifications)
4. [Gold Layer Schemas](#4-gold-layer-schemas)
5. [Data Quality Framework](#5-data-quality-framework)
6. [Apache Iceberg Configuration](#6-apache-iceberg-configuration)
7. [Platform Comparison](#7-platform-comparison)
8. [Streaming Architecture](#8-streaming-architecture)
9. [Backup & Retention Policy](#9-backup--retention-policy)

---

## 1. Overview

Neutron OS employs a medallion architecture (Bronze → Silver → Gold) built on:

- **Apache Iceberg** for time-travel capabilities and schema evolution
- **DuckDB** as the query engine
- **dbt** for transformations
- **Dagster** for orchestration

---

## 2. Medallion Architecture

### Layer Characteristics

| Layer | Purpose | Mutability | Typical Format |
|-------|---------|------------|----------------|
| **Bronze** | Raw ingestion | Append-only | Parquet (Iceberg) |
| **Silver** | Cleaned, validated | Upsert | Parquet (Iceberg) |
| **Gold** | Aggregated, business-ready | Materialized views | Parquet (Iceberg) |

---

## 3. Layer Specifications

### 3.1 Bronze Layer

Raw, unprocessed data exactly as received. Append-only to preserve complete history.

| Table | Source | Grain | Partitioning |
|-------|--------|-------|--------------|
| `sensor_readings_raw` | Serial ingest | Per reading | `date`, `reactor_id` |
| `log_entries_raw` | Operation logs | Per entry | `date`, `reactor_id` |
| `simulation_outputs_raw` | MCNP/MPACT/SAM | Per run | `date`, `model_type` |

**Multi-Tenant:** All tables partitioned by `org_id` and `reactor_id` for tenant isolation.

### 3.2 Silver Layer

Cleaned, validated, and deduplicated data. dbt transformations apply business rules.

| Table | Source | Transformations |
|-------|--------|-----------------|
| `sensor_readings` | Bronze | Dedup, unit normalization, outlier flagging |
| `log_entries` | Bronze | Schema validation, user enrichment |
| `simulation_runs` | Bronze | Metadata extraction, status tracking |

### 3.3 Gold Layer

Business-ready, aggregated datasets optimized for analytics and dashboards.

| Table | Grain | Use Case |
|-------|-------|----------|
| `reactor_hourly_metrics` | Hour | Dashboard KPIs |
| `fuel_burnup_current` | Element | Core management |
| `xenon_state_hourly` | Hour | Startup predictions |

---

## 4. Gold Layer Schemas

### 4.1 reactor_hourly_metrics

| Column | Type | Description |
|--------|------|-------------|
| `reactor_id` | string | Reactor identifier |
| `hour` | timestamp | Hour bucket |
| `avg_power_kw` | float | Average power |
| `max_fuel_temp_c` | float | Max fuel temperature |
| `avg_pool_temp_c` | float | Average pool temperature |
| `source` | enum | `measured` \| `modeled` |

> **Note:** Includes `source` column to distinguish measured vs modeled data.

### 4.2 xenon_state_hourly

| Column | Type | Description |
|--------|------|-------------|
| `reactor_id` | string | Reactor identifier |
| `hour` | timestamp | Hour bucket |
| `xe135_atoms` | float | Xenon-135 concentration |
| `i135_atoms` | float | Iodine-135 concentration |
| `critical_rod_height_units` | float | Correlated rod height |

> **Important:** Cannot be measured directly; correlated with critical rod heights.

### 4.3 fuel_burnup_current

| Column | Type | Description |
|--------|------|-------------|
| `element_id` | string | Fuel element serial |
| `position` | string | Core position (e.g., B-01) |
| `u235_burned_g` | float | U-235 consumed |
| `mwd` | float | Megawatt-days |
| `last_updated` | timestamp | Calculation date |

### 4.4 log_entries (Unified Log)

Single table with `entry_type` discriminator for all log types.

| Column | Type | Description |
|--------|------|-------------|
| `entry_id` | uuid | Primary key |
| `reactor_id` | string | Reactor identifier |
| `timestamp` | timestamp | Entry time |
| `entry_type` | enum | See below |
| `operator_id` | string | User who created |
| `content` | jsonb | Type-specific payload |

**Entry Types:**

| Type | Description |
|------|-------------|
| `console_check` | Mandatory 30-minute walkdown |
| `startup` | Reactor startup |
| `shutdown` | Normal shutdown |
| `scram` | Emergency shutdown |
| `radiation_survey` | HP survey reading |
| `experiment_log` | Sample insertion/removal |
| `maintenance` | Equipment issues |
| `general_note` | Miscellaneous |

> **Critical:** Dashboard must flag gaps > 30 min during operating periods.

### 4.5 sample_tracking

| Column | Type | Description |
|--------|------|-------------|
| `sample_id` | uuid | Primary key |
| `facility` | enum | Irradiation facility |
| `inserted_at` | timestamp | Insertion time |
| `removed_at` | timestamp | Removal time |
| `fluence_n_cm2` | float | Calculated fluence |
| `activity_ci` | float | Measured activity |

**Irradiation Facilities:** TPNT, EPNT, RSR, CT, F3EL, 3EL_Cd, 3EL_Pb, BP1-BP5

### 4.6 Model Corral Tables

**Reference:** [Model Corral Spec](spec-model-corral.md)

| Layer | Table | Description |
|-------|-------|-------------|
| Bronze | `model_registry_raw` | Raw model.yaml JSON as submitted |
| Silver | `model_registry_validated` | Schema-validated, enriched with lineage |
| Gold | `model_catalog` | Searchable model catalog |
| Gold | `model_lineage` | Parent-child relationships (ROM → physics) |
| Gold | `model_validation_metrics` | Aggregated validation statistics |

**Key relationships:**
- `model_lineage.child_model_id` → `model_catalog.model_id`
- `model_lineage.parent_model_id` → `model_catalog.model_id`
- ROM models have `training.source_model` referencing physics model

### 4.7 Digital Twin Tables

**Reference:** [Digital Twin Hosting Spec](spec-digital-twin-architecture.md)

| Layer | Table | Description |
|-------|-------|-------------|
| Bronze | `dt_runs_raw` | Raw run submissions |
| Silver | `dt_runs` | Validated run records with provenance |
| Silver | `dt_run_states` | Time-series state snapshots per run |
| Silver | `dt_run_validations` | Prediction vs measurement comparisons |
| Gold | `dt_run_summary` | Aggregated run statistics |
| Gold | `dt_model_accuracy` | Model accuracy metrics over time |

**Key schema elements:**

`dt_runs`:
- `run_id` (PK), `model_id` (FK → model_catalog), `model_version`
- `reactor_id`, `rom_tier` (enum: ROM-1/2/3/4/Shadow)
- `started_at`, `completed_at`, `status` (pending/running/completed/failed)
- `triggered_by` (user/schedule/anomaly), `input_hash`, `config_snapshot` (JSONB)

`dt_run_states`:
- `state_id` (PK), `run_id` (FK), `sim_time`, `wall_time`
- `state_vector` (JSONB), `uncertainty` (JSONB)

`dt_run_validations`:
- `validation_id` (PK), `run_id` (FK), `validated_at`
- `measured_state`, `predicted_state`, `metrics` (JSONB), `passed` (boolean)

---

## 5. Data Quality Framework

### Quality Tests

| Test Type | Layer | Example |
|-----------|-------|---------|
| **Not null** | Bronze | `sensor_id IS NOT NULL` |
| **Unique** | Silver | `entry_id` unique per table |
| **Referential** | Silver | `reactor_id` exists in `reactors` |
| **Range** | Silver | `fuel_temp_c BETWEEN 0 AND 1200` |
| **Freshness** | Gold | Data < 1 hour old |
| **Custom** | Gold | Power + temps consistent with physics |

---

## 6. Apache Iceberg Configuration

### 6.1 Catalog Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Catalog type | REST | Standard API for multi-engine access |
| Metadata location | S3/SeaweedFS | Durable, shared storage |
| Warehouse | `s3://neutron-lakehouse/` | All Iceberg data |

### 6.2 Partitioning Strategy

| Table Pattern | Partition Columns | Rationale |
|---------------|-------------------|-----------|
| Sensor data | `date`, `reactor_id` | Query by time + tenant |
| Logs | `date`, `entry_type` | Query by time + type |
| Simulations | `date`, `model_type` | Query by time + model |

### 6.3 Key Capabilities

- **Time-travel queries:** Query data as it existed at any point
- **Schema evolution:** Add/rename/drop columns without rewriting
- **Partition evolution:** Change partitioning without data movement
- **ACID transactions:** Concurrent reads and writes

---

## 7. Platform Comparison

### 7.1 Decision Summary

We chose open-source (Iceberg + DuckDB + dbt) over commercial platforms (Databricks, Snowflake).

### 7.2 Decision Rationale

| Factor | Open Lakehouse | Commercial Platform |
|--------|----------------|---------------------|
| **Cost** | Fixed infrastructure | Per-compute pricing |
| **Data sovereignty** | Full control | Vendor access |
| **Nuclear integration** | Native Python/HDF5 | Limited |
| **On-premise** | Supported | Cloud-primary |
| **Research integrity** | Open pipelines | Proprietary |
| **Workforce dev** | Industry-standard tools | Vendor-specific |

**Migration path:** Open formats (Iceberg, Parquet) ensure future migration feasibility.

### 7.3 INL DeepLynx Partnership Opportunity

**Status:** Exploratory — non-committal technical alignment

Idaho National Laboratory's [DeepLynx Nexus](https://github.com/idaholab/DeepLynx) is an open-source (MIT) digital engineering backbone developed for nuclear projects (MARVEL, NRIC). After codebase analysis, we've identified significant technology overlap and complementary capabilities.

**Technology Overlap:**
- Both use **DuckDB** for timeseries analytics (DeepLynx stores timeseries as CSV/Parquet files, queries via DuckDB)
- Both target **nuclear digital twins** (DeepLynx powers AGN-201 TRIGA at INL)
- Both provide **MCP servers** for AI agent integration

**Complementary Strengths:**

| Capability | DeepLynx | NeutronOS |
|------------|----------|-----------|
| Ontology management | ✅ Mature (Class/Relationship model) | ⚠️ YAML schemas |
| Graph traversal | ✅ Native | ⚠️ Via JOINs |
| Real-time streaming | ⚠️ Batch webhooks | ✅ Kafka/Redpanda |
| Time-series analytics | ✅ DuckDB | ✅ DuckDB + Iceberg |
| ML/ROM workflows | ⚠️ Not focus | ✅ Native |
| AI agent tooling | ⚠️ Basic MCP | ✅ Full MCP |

**Potential Integration Approaches:**

1. **Data Exchange** (Low commitment): CSV/Parquet interchange for timeseries data
2. **MCP Interoperability** (Medium commitment): AI agents access both systems via unified tool spec
3. **Ontology Alignment** (Medium commitment): Share reactor ontology vocabulary (NRAD ↔ NETL)
4. **Plugin Architecture** (High commitment): DeepLynx as optional ConfigurationPlugin for NeutronOS

**Next Steps (if pursued):**
- Compare NRAD ontology with NETL TRIGA schema (see [spec-nrad-ontology-mapping.md](spec-nrad-ontology-mapping.md))
- Explore MCP tool specification alignment
- NEUP IRP joint proposal opportunity (deadline: June 9, 2026)

**Reference:** Full technical analysis in [docs/research/deeplynx-assessment.md](../research/deeplynx-assessment.md)

---

## 8. Streaming Architecture

> **See:** [ADR-007: Streaming-First Architecture](../requirements/adr-007-streaming-first-architecture.md)

### 8.1 Design Principle

Build for streaming; use batch as fallback.

### 8.2 Event Schema

All events follow a common envelope:

```json
{
  "event_id": "uuid",
  "event_type": "sensor_reading | prediction | log_entry",
  "timestamp": "ISO8601",
  "source": { "facility": "NETL", "reactor": "ut-triga-1" },
  "payload": { ... },
  "metadata": { "schema_version": "1.0" }
}
```

### 8.3 Latency Targets

| Data Type | Target Latency | Streaming Tech |
|-----------|----------------|----------------|
| Sensor readings | <1s | Redpanda |
| Log entries | <5s | Redpanda |
| Predictions | <100ms | Direct API |
| Aggregations | <1 min | Flink/Materialize |

---

## 9. Backup, Retention & Archive Policy

NeutronOS inherits the base operational policies from [Axiom Data Architecture Spec § 9](https://github.com/…/axiom/docs/tech-specs/spec-data-architecture.md#9-backup-retention--archive-policy). This section documents NRC-specific extensions.

> **Canonical policy definition:** [Axiom Data Architecture Spec § 9: Backup, Retention & Archive Policy](https://github.com/…/axiom/docs/tech-specs/spec-data-architecture.md#9-backup-retention--archive-policy)

### 9.1 NRC Retention Requirements

NeutronOS deploys with `[retention] policy = "regulatory"` at all NRC-licensed facilities. This activates:

| Tier | Retention | NRC Requirement |
|------|-----------|-----------------|
| **Hot** | 90 days | Operational convenience (not NRC-mandated) |
| **Warm** | 2 years | NRC inspection window for operational records |
| **Cold** | 7 years | 10 CFR 50.71 — audit trails, compliance records, training records |
| **Archive** | Indefinite | Safety basis documents, licensing records, FSAR amendments |

### 9.2 NRC-Specific Backup Extensions

In addition to the Axiom base backup strategy:

| Component | Frequency | Destination | NRC Rationale |
|-----------|-----------|-------------|---------------|
| Ops log entries | Daily | S3 + offsite + printed archive | NRC requires paper backup for ops logs |
| Training records | Weekly | S3 + offsite | 10 CFR 55 certification records |
| Compliance evidence | On generation | S3 + Glacier | NRC inspection evidence packages |
| HMAC chain verification | Daily | Logged to audit trail | Tamper detection for ops log integrity |

### 9.3 Encryption

Inherits Axiom encryption policy (AES-256 at rest, TLS 1.3 in transit, separate backup keys managed via HashiCorp Vault). Key rotation quarterly; archived keys retained for the lifetime of NRC-required records.

---

## DOE Data Management Extensions

Gold-tier datasets designated for publication under DOE DMSP requirements receive the following extensions:

- **Nuclear metadata extension columns:** `funding_source` (DOE award number), `dmsp_project_id` (links dataset to its DMSP project record), and `publication_status` (enum: `internal` | `embargoed` | `published`).
- **DataCite metadata layer:** Published Gold datasets carry a DataCite-compliant metadata record (title, creators, DOI, rights, funding references) stored alongside the Iceberg table metadata. This enables DOI minting and OSTI deposit without duplicating the underlying data.
- **DMSP project attribution:** A `dmsp_project_id` column on Bronze/Silver/Gold tables traces data lineage back to the originating DOE-funded project for audit and reporting purposes.

See [prd-doe-data-management.md](../requirements/prd-doe-data-management.md) for full requirements.

---

## Related Documents

- [Executive Spec](spec-executive.md) — Master tech spec
- [Model Corral Spec](spec-model-corral.md) — Model registry
- [Digital Twin Hosting Spec](spec-digital-twin-architecture.md) — DT execution
- [ADR-003: Lakehouse Architecture](../requirements/adr-003-lakehouse-iceberg-duckdb-superset.md) — Decision record
- [ADR-007: Streaming-First](../requirements/adr-007-streaming-first-architecture.md) — Decision record
