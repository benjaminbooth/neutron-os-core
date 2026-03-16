Table of Contents

Data Architecture Specification

Part of: Neutron OS Master Tech Spec

Scope: This document specifies the Neutron OS data architecture, including the medallion pattern, Apache Iceberg configuration, schema definitions, data quality framework, and streaming readiness.

Table of Contents

• Overview

• Medallion Architecture

• Layer Specifications

• Gold Layer Schemas

• Data Quality Framework

• Apache Iceberg Configuration

• Platform Comparison

• Streaming Architecture

• Backup & Retention Policy

1. Overview

Neutron OS employs a medallion architecture (Bronze → Silver → Gold) built on:

• Apache Iceberg for time-travel capabilities and schema evolution

• DuckDB as the query engine

• dbt for transformations

• Dagster for orchestration

2. Medallion Architecture

Layer Characteristics

3. Layer Specifications

3.1 Bronze Layer

Raw, unprocessed data exactly as received. Append-only to preserve complete history.

Multi-Tenant: All tables partitioned by org_id and reactor_id for tenant isolation.

3.2 Silver Layer

Cleaned, validated, and deduplicated data. dbt transformations apply business rules.

3.3 Gold Layer

Business-ready, aggregated datasets optimized for analytics and dashboards.

4. Gold Layer Schemas

4.1 reactor_hourly_metrics

Note: Includes source column to distinguish measured vs modeled data.

4.2 xenon_state_hourly

Important: Cannot be measured directly; correlated with critical rod heights.

4.3 fuel_burnup_current

4.4 log_entries (Unified Log)

Single table with entry_type discriminator for all log types.

Entry Types:

• console_check — Mandatory 30-minute walkdown

• startup / shutdown / scram — Reactor state changes

• radiation_survey — HP survey reading

• experiment_log — Sample insertion/removal

• maintenance — Equipment issues

• general_note — Miscellaneous

Critical: Dashboard must flag gaps > 30 min during operating periods.

4.5 sample_tracking

Irradiation Facilities: TPNT, EPNT, RSR, CT, F3EL, 3EL_Cd, 3EL_Pb, BP1-BP5

5. Data Quality Framework

Quality Tests

6. Apache Iceberg Configuration

6.1 Catalog Configuration

6.2 Partitioning Strategy

6.3 Key Capabilities

• Time-travel queries: Query data as it existed at any point

• Schema evolution: Add/rename/drop columns without rewriting

• Partition evolution: Change partitioning without data movement

• ACID transactions: Concurrent reads and writes

7. Platform Comparison

7.1 Decision Summary

We chose open-source (Iceberg + DuckDB + dbt) over commercial platforms (Databricks, Snowflake).

7.2 Decision Rationale

• Budget sustainability: No per-compute costs

• Nuclear integration: Native Python/HDF5 for MCNP, MPACT, SAM

• On-premise flexibility: Partner facilities may require isolated deployments

• Research integrity: Open pipelines can be peer-reviewed

• Workforce development: Students learn industry-standard tools

Migration path: Open formats (Iceberg, Parquet) ensure future migration feasibility.

8. Streaming Architecture

See: ADR-007: Streaming-First Architecture

8.1 Design Principle

Build for streaming; use batch as fallback.

8.2 Event Schema

All events follow a common envelope:

{
  "event_id": "uuid",
  "event_type": "sensor_reading | prediction | log_entry",
  "timestamp": "ISO8601",
  "source": { "facility": "NETL", "reactor": "ut-triga-1" },
  "payload": { ... },
  "metadata": { "schema_version": "1.0" }
}

8.3 Latency Targets

9. Backup & Retention Policy

All data in the lakehouse must support regulatory retention requirements and disaster recovery. This section defines the backup strategy and retention tiers.

See also: Master Tech Spec § 9.2: Backup & Archive Strategy

9.1 Retention Tiers

9.2 Backup Strategy

9.3 Disaster Recovery

9.4 Regulatory Compliance

• 2-year retention minimum: Live data kept in Iceberg for NRC inspection window

• 7-year archive: Regulatory requirement for audit trails and critical records

• Immutability: All backups are append-only; no modification or deletion allowed

• Versioning: Iceberg time-travel enables recovery of any point-in-time data

• Audit trail: All backup operations logged in immutable Hyperledger blockchain

9.5 Encryption

Key Rotation: Quarterly for active encryption keys; archived keys retained indefinitely per regulatory requirement.