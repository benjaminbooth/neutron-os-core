# Design Prompt: Superset Dashboards

**Component:** Visualization Layer  
**Phase:** 1a (MVP) → 2 (Core Analytics)  
**Priority:** P1 - High  
**Estimated Effort:** 2-3 days (Phase 1a); 1-2 weeks (Phase 2 migration)  
**Phase 1a Depends On:** DMSRI-web PostgreSQL access  
**Phase 2 Depends On:** [dbt Silver Models](prompt-dbt-silver-models.md)  
**Related PRD:** [Analytics Dashboards PRD](../../prd/analytics-dashboards-prd.md)

---

## Context for Implementation

This prompt guides configuring Apache Superset to query Neutron OS data and building operational dashboards.

**Dual-Phase Approach:**
- **Phase 1a (Now):** Connect Superset directly to DMSRI-web PostgreSQL—the same database that powers today's Plotly dashboards. Immediate visibility, minimal effort.
- **Phase 2+:** Migrate to proper lakehouse (DuckDB/Iceberg via dbt). Better performance, proper data contracts, scalable architecture.

**Why Superset?**
- **Open source**: No per-seat licensing (unlike Tableau, Looker)
- **SQL-native**: Direct queries on PostgreSQL, DuckDB, or Trino
- **Self-service**: Researchers can build their own charts
- **Embeddable**: Dashboards can be embedded in other apps
- **Enterprise features**: Row-level security, audit logging

**Phase 1a Pre-requisites:**
- DMSRI-web PostgreSQL credentials
- Docker or local Python environment for Superset

**Phase 2 Pre-requisites:**
- Silver/Gold dbt models materialized
- DuckDB database accessible

---

## Stakeholder Requirements (Jan 2026)

### From Nick Luciano (Reactor Engineer)

| Requirement | Design Implication |
|-------------|-------------------|
| "We'd ideally get live streaming, but currently we just upload the data after-hours due to cost" | Streaming-first architecture. Real-time is the default; batch for aggregations and fallback. See [ADR 007](../../adr/007-streaming-first-architecture.md). |
| "The public should generally not know when the reactor is at power" | **All dashboards require authentication.** No public-facing real-time power status. |
| "The calendar is used to schedule time. It is not a reflection of what actually happened" | Show actual reactor data, not scheduled data. Calendar integration is low priority. |
| "[Xenon] cannot be measured directly, but can be correlated with critical rod heights" | Xenon dashboard uses inferred values. Display methodology note. |
| "[Fuel burnup heatmap] would be great" | Priority: High. Requires model integration. |

### From Jim (Senior Reactor Operator)

| Requirement | Design Implication |
|-------------|-------------------|
| "I am not sure what insight could be achieved by counting the number of log entries" | Simple entry counts are not useful. Tag entries by "watch type" for meaningful analysis. |
| "A gap would mean that this :30 minute check was not performed when operating" | **Gap detection is critical.** Visual alert for missed mandatory checks. |
| "Export to PDF would work, but a simple text file for archive and future proof would also work" | Support PDF, plain text, CSV exports. |

---

## Objective

Deploy Superset connected to the Neutron OS lakehouse and build five core dashboards:

1. **Reactor Operations** - Real-time power, temperatures, status
2. **Operations Log Compliance** - Ops Log gaps, mandatory check tracking (NEW)
3. **Fuel Burnup Heatmap** - Per-element burnup visualization (NEW)
4. **Data Quality** - Ingestion health, validation metrics
5. **Digital Twin Performance** - Prediction vs. actual comparisons

---

## Superset Configuration

### Database Connection

**Phase 1a: Connect to DMSRI-web PostgreSQL (immediate)**

```python
# superset_config.py - Phase 1a (Data Puddle)

# DMSRI-web PostgreSQL connection
# Note: This database does minimal aggregation/scrubbing for Plotly today.
# It works but doesn't scale. Phase 2 migrates to proper lakehouse.
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://user:pass@dmsri-web-host:5432/triga_db"

# Additional settings
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
}

# Row-level security (Phase 3)
ROW_SECURITY_ENABLED = True
```

**Phase 2+: Migrate to DuckDB Lakehouse**

```python
# superset_config.py - Phase 2 (Lakehouse)

# DuckDB connection string (after dbt models are ready)
SQLALCHEMY_DATABASE_URI = "duckdb:////data/neutron_os/neutron_os.duckdb"

# Enable DuckDB-specific features
SQL_VALIDATORS_BY_ENGINE = {
    "duckdb": [],
}
```

### Semantic Layer (Datasets)

Define reusable datasets in Superset:

| Dataset Name | Source Table | Description |
|--------------|--------------|-------------|
| `reactor_readings` | `silver.reactor_readings` | Core sensor readings |
| `channel_metadata` | `silver.channel_metadata` | Channel reference data |
| `reactor_hourly_metrics` | `gold.reactor_hourly_metrics` | Hourly aggregates |
| `data_quality_log` | `silver.data_quality_log` | Quality issues |
| `prediction_validation` | `gold.prediction_validation` | DT predictions vs actuals |

### Calculated Columns

Add these calculated columns to datasets:

```sql
-- reactor_readings dataset

-- Time bucket for aggregation
CASE 
    WHEN {{ granularity }} = 'minute' THEN date_trunc('minute', reading_timestamp)
    WHEN {{ granularity }} = 'hour' THEN date_trunc('hour', reading_timestamp)
    ELSE date_trunc('day', reading_timestamp)
END AS time_bucket

-- Quality score (numeric for aggregation)
CASE validated_quality
    WHEN 'GOOD' THEN 1.0
    WHEN 'SUSPECT' THEN 0.5
    ELSE 0.0
END AS quality_score
```

---

## Dashboard 1: Reactor Operations

### Purpose
Real-time (or near-real-time) view of reactor status for operators.

### Layout
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEUTRON OS - REACTOR OPERATIONS                     [Filters] [Refresh 1m]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ CORE POWER   │  │ POOL TEMP    │  │ FUEL TEMP    │  │ FLUX         │    │
│  │   247.3 kW   │  │   28.4 °C    │  │   312.1 °C   │  │  1.23e14     │    │
│  │   ▲ +2.1%    │  │   ─ 0.0%     │  │   ▲ +0.5%    │  │   ─ 0.0%     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                     Core Power (Last 24 Hours)                         ││
│  │  kW                                                                    ││
│  │  300├────────────────────────────────────────────────────────────────┐ ││
│  │     │                                         ████████                │ ││
│  │  200│      ████████████                      █        █               │ ││
│  │     │     █            ████████████████████ █          ████████████   │ ││
│  │  100│    █                                                            │ ││
│  │     └────────────────────────────────────────────────────────────────┘ ││
│  │       00:00    04:00    08:00    12:00    16:00    20:00    24:00      ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   Temperature Trends            │  │   Recent Readings Table         │  │
│  │   [Pool / Fuel overlay chart]   │  │   [Last 100 readings, all CH]   │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Chart Specifications

#### KPI Cards (Big Number)

```sql
-- Core Power KPI
SELECT 
    reading_value as metric_value,
    'kW' as unit,
    LAG(reading_value) OVER (ORDER BY reading_timestamp) as prev_value
FROM silver.reactor_readings
WHERE channel_name = 'core_power_kw'
ORDER BY reading_timestamp DESC
LIMIT 1
```

Settings:
- Chart type: Big Number with Trendline
- Comparison: Previous period (1 hour ago)
- Conditional formatting: Red if >900 kW, Yellow if >800 kW

#### Core Power Time Series

```sql
-- Core Power over time
SELECT 
    date_trunc('{{ granularity }}', reading_timestamp) as time,
    AVG(reading_value) as avg_power,
    MAX(reading_value) as max_power,
    MIN(reading_value) as min_power
FROM silver.reactor_readings
WHERE channel_name = 'core_power_kw'
  AND reading_timestamp >= {{ start_time }}
  AND reading_timestamp <= {{ end_time }}
GROUP BY 1
ORDER BY 1
```

Settings:
- Chart type: Area Chart
- Granularity filter: minute / hour / day
- Show min/max as shaded region

#### Recent Readings Table

```sql
-- Last N readings across all channels
SELECT 
    reading_timestamp,
    channel_name,
    reading_value,
    reading_unit,
    validated_quality
FROM silver.reactor_readings
WHERE reading_timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY reading_timestamp DESC
LIMIT {{ row_limit }}
```

---

## Dashboard 2: Data Quality

### Purpose
Monitor data pipeline health for data engineers and researchers.

### Layout
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEUTRON OS - DATA QUALITY                           [Date Range] [Channel]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ INGESTED     │  │ GOOD QUALITY │  │ SUSPECT      │  │ MISSING      │    │
│  │   1.2M rows  │  │   97.3%      │  │   2.1%       │  │   0.6%       │    │
│  │   (24h)      │  │              │  │              │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                Quality Distribution Over Time                          ││
│  │  [Stacked area: GOOD / SUSPECT / BAD / MISSING by hour]               ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   Quality by Channel            │  │   Recent Quality Issues          │  │
│  │   [Heatmap: channel x hour]     │  │   [Table from quality_log]       │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │   Ingestion Latency             [Files processed / hour timeline]      ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Queries

```sql
-- Quality distribution by time
SELECT 
    date_trunc('hour', reading_timestamp) as hour,
    validated_quality,
    COUNT(*) as count
FROM silver.reactor_readings
WHERE reading_timestamp >= {{ start_time }}
GROUP BY 1, 2
ORDER BY 1, 2

-- Quality by channel (heatmap)
SELECT 
    channel_name,
    date_trunc('hour', reading_timestamp) as hour,
    AVG(CASE WHEN validated_quality = 'GOOD' THEN 1.0 ELSE 0.0 END) as good_rate
FROM silver.reactor_readings
WHERE reading_timestamp >= {{ start_time }}
GROUP BY 1, 2

-- Ingestion latency
SELECT 
    date_trunc('hour', _ingestion_ts) as ingestion_hour,
    COUNT(DISTINCT _source_file) as files_processed,
    AVG(EXTRACT(EPOCH FROM (_ingestion_ts - event_timestamp))) as avg_latency_seconds
FROM bronze.reactor_timeseries_raw
GROUP BY 1
ORDER BY 1
```

---

## Dashboard 3: Digital Twin Performance

### Purpose
Compare DT predictions against actual measurements for model validation.

### Layout
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  NEUTRON OS - DIGITAL TWIN PERFORMANCE               [Model] [Date Range] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ MAPE         │  │ RMSE         │  │ MAX ERROR    │  │ VALID PREDS  │    │
│  │   2.3%       │  │   12.4 kW    │  │   45.2 kW    │  │   98.7%      │    │
│  │   (Core Pwr) │  │   (Core Pwr) │  │   (Core Pwr) │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │   Predicted vs Actual                                                  ││
│  │   [Overlay line chart: prediction (dashed) vs actual (solid)]         ││
│  │   [Shaded region: uncertainty bounds]                                  ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   Error Distribution            │  │   Model Accuracy Over Time      │  │
│  │   [Histogram of residuals]      │  │   [Rolling MAPE / RMSE]         │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │   Large Deviation Events        [Table: when |error| > threshold]     ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Queries

```sql
-- Prediction validation metrics
SELECT 
    model_name,
    channel_name,
    AVG(ABS(predicted_value - actual_value) / NULLIF(actual_value, 0)) * 100 as mape,
    SQRT(AVG(POWER(predicted_value - actual_value, 2))) as rmse,
    MAX(ABS(predicted_value - actual_value)) as max_error,
    COUNT(*) as prediction_count
FROM gold.prediction_validation
WHERE prediction_timestamp >= {{ start_time }}
GROUP BY 1, 2

-- Predicted vs actual time series
SELECT 
    prediction_timestamp,
    predicted_value,
    actual_value,
    uncertainty_lower,
    uncertainty_upper,
    predicted_value - actual_value as error
FROM gold.prediction_validation
WHERE channel_name = '{{ channel }}'
  AND model_name = '{{ model }}'
  AND prediction_timestamp >= {{ start_time }}
ORDER BY prediction_timestamp

-- Error histogram
SELECT 
    FLOOR((predicted_value - actual_value) / {{ bin_width }}) * {{ bin_width }} as error_bin,
    COUNT(*) as count
FROM gold.prediction_validation
WHERE channel_name = '{{ channel }}'
GROUP BY 1
ORDER BY 1
```

---

## Filters and Interactivity

### Native Filters

Configure these filters available on all dashboards:

| Filter | Type | Scope |
|--------|------|-------|
| Date Range | Time Range | Global |
| Channel | Multi-select | Dashboard |
| Quality Flag | Multi-select | Data Quality |
| Model Name | Single-select | DT Performance |
| Time Granularity | Dropdown | Charts with time axis |

### Cross-Filtering

Enable cross-filtering so clicking a chart element filters others:
- Click a channel in heatmap → filter time series to that channel
- Click a time period → zoom other charts to that period

---

## Deployment

### Docker Compose

```yaml
# docker-compose.superset.yml

version: "3.8"

services:
  superset:
    image: apache/superset:3.0.0
    container_name: neutron_superset
    ports:
      - "8088:8088"
    volumes:
      - ./superset_config.py:/app/pythonpath/superset_config.py
      - ./warehouse:/data/warehouse:ro
    environment:
      - SUPERSET_SECRET_KEY=${SUPERSET_SECRET_KEY}
      - SUPERSET_LOAD_EXAMPLES=false
    command: >
      sh -c "
        superset db upgrade &&
        superset fab create-admin --username admin --firstname Admin --lastname User --email admin@neutron.os --password admin &&
        superset init &&
        superset run -h 0.0.0.0 -p 8088
      "

  # Optional: Redis for caching
  redis:
    image: redis:7-alpine
    container_name: neutron_redis
```

### Helm Chart (K8s)

```yaml
# values-superset.yaml

superset:
  image:
    repository: apache/superset
    tag: 3.0.0
  
  configOverrides:
    secret: |
      SECRET_KEY = '{{ .Values.secretKey }}'
    
    # Phase 1a: DMSRI-web PostgreSQL (immediate)
    database_connections: |
      SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://{{ .Values.dmsriWeb.user }}:{{ .Values.dmsriWeb.password }}@{{ .Values.dmsriWeb.host }}:5432/{{ .Values.dmsriWeb.database }}"
    
    # Phase 2+: Uncomment for lakehouse migration
    # database_connections: |
    #   SQLALCHEMY_DATABASE_URI = "duckdb:////data/neutron_os.duckdb"
  
  # Phase 2+ only: Mount DuckDB volume
  # extraVolumes:
  #   - name: neutron-data
  #     persistentVolumeClaim:
  #       claimName: neutron-pvc
  # extraVolumeMounts:
  #   - name: neutron-data
  #     mountPath: /data
  #     readOnly: true
```

---

## Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| **Dashboard Load Time** | <3 seconds for 24-hour view |
| **Query Performance** | 95th percentile <500ms |
| **Self-Service** | Researchers can create charts without help |
| **Mobile Responsive** | Dashboards usable on tablet |
| **Documentation** | All charts have descriptions |

---

## Follow-Up Components

After Superset dashboards are complete:

1. **Alerting** - Configure Superset alerts for threshold breaches
2. **Embedding** - Embed dashboards in external Flask/React apps
3. **Row-Level Security** - Restrict data access by user role

---

*This design prompt is part of the Neutron OS documentation. See [Executive Summary](../neutron-os-executive-summary.md) for project context.*
