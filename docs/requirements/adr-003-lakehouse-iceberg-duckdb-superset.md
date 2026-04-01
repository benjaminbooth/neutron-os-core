# ADR-003: Data Lakehouse with Iceberg, DuckDB, and Superset — Neutron OS Nuclear Context

> This architecture decision is made at the Axiom platform level. This document captures nuclear-specific context only.

**Upstream:** [Axiom adr-003-lakehouse-iceberg-duckdb-superset.md](https://github.com/…/axiom/docs/requirements/adr-003-lakehouse-iceberg-duckdb-superset.md)

---

## Nuclear Context

### Medallion Table Naming

NeutronOS uses reactor-specific table names in the medallion layers:

| Layer | Axiom Generic | NeutronOS Convention |
|-------|--------------|---------------------|
| **Silver** | `system_timeseries_clean` | `reactor_timeseries_clean` |
| **Gold** | `system_hourly_metrics` | `reactor_hourly_metrics` |

### Deployment Target

NeutronOS targets TACC HPC clusters (Frontera, Lonestar6) rather than generic private cloud for production-scale lakehouse workloads.
