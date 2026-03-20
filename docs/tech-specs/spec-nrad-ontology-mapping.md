# NRAD ↔ NETL TRIGA Ontology Mapping

**Purpose:** Compare INL's NRAD Digital Twin ontology with our NETL TRIGA schema to identify alignment opportunities and gaps.

**Source:** `nrad_dt_generic_ontology_v4.txt` (Ryan via Nick & Cole, January 2026)

---

## 1. Ontology Overview

### 1.1 NRAD Classes → Neutron OS Tables

| NRAD Class | Count | Neutron OS Equivalent | Notes |
|------------|:-----:|----------------------|-------|
| `Digital Twin` | 1 | `reactors` table | Root entity |
| `Control Element` | 3 | `control_rods` table | Shim 1, Shim 2, Regulating |
| `Detector` | 25+ | `sensors` table | Most of the ontology |
| `Limits` | 12 | **NEW: `sensor_limits`** | Critical gap in our schema |
| `Data Acquisition System` | 1 | `data_sources` table | TINA system |
| `Data File` | 4 | `data_files` / Bronze layer | CSV ingestion |
| `Analysis` | 2 | `models` table | ML Operation, SM Operation |
| `Visualization` | 1 | Superset dashboards | Not in DB schema |
| `Modes of Operation` | 1 | **NEW: `operational_modes`** | Data collection, prediction |
| `Remote Monitoring` | 0* | `remote_access_logs` | Not used in ontology |

*Remote Monitoring class exists but has no records.

### 1.2 NRAD Relationships → Neutron OS Foreign Keys

| NRAD Relationship | Usage | Neutron OS Equivalent |
|-------------------|:-----:|----------------------|
| `consists_of` | 40 | `reactor_id` FK on sensors |
| `sends_data_to` | 35 | Data lineage (dbt refs) |
| `has_setting_limits` | 25 | `sensor_id` FK on limits |
| `allows` | 3 | Mode → capability mapping |

---

## 2. Sensor Mapping (Critical Path)

### 2.1 Control Elements

| NRAD Name | NRAD Properties | NETL TRIGA Equivalent | Tag Name |
|-----------|-----------------|----------------------|----------|
| Shim Rod 1 | position (in), 0-24 range | Safety Rod | `TBD` |
| Shim Rod 2 | position (in), 0-24 range | Shim Rod | `TBD` |
| Regulating Rod | position (in), 0-24 range | Regulating Rod | `TBD` |

**Key Properties to Map:**
```json
{
  "current position": 24,
  "least reactive position": 24,
  "most reactive position": 0,
  "has LCO requirements": "True",
  "magnet switch activated": "False"
}
```

### 2.2 Power Measurement

| NRAD Name | Type | NETL TRIGA Equivalent |
|-----------|------|----------------------|
| Multi-Range Linear Channel 1 | Ionization chamber, % Power | NI-1 (NP-1000) |
| Multi-Range Linear Channel 2 | Ionization chamber, % Power | NI-2 (NP-1000) |
| Multi-Range Linear Channel 3 | Ionization chamber, % Power | NI-3 (NP-1000) |
| Wide-Range Log Channel | Fission counter, % Power + period | NI-4 (Wide Range) |

### 2.3 Temperature

| NRAD Name | Units | NETL TRIGA Equivalent |
|-----------|-------|----------------------|
| Fuel Temperature Detector | °C | IFE Thermocouple |
| Heat Exchanger Inlet Temperature | °C | Pool outlet temp |
| Heat Exchanger Outlet Temperature | °C | Pool inlet temp |
| Reactor Tank Temperature | °C | Pool bulk temp |
| Demineralizer Inlet/Outlet Temperature | °C | (Not directly measured) |

### 2.4 Flow

| NRAD Name | Units | NETL TRIGA Equivalent |
|-----------|-------|----------------------|
| Primary Cooling System Flow | gpm | Primary flow |
| Secondary Cooling System Flow | gpm | Secondary flow |
| Demineralizer Flow | gpm | Demin flow |

### 2.5 Radiation Monitoring

| NRAD Name | Type | Units | NETL TRIGA Equivalent |
|-----------|------|-------|----------------------|
| Reactor Room RAM | Gamma monitor | R/h | ARM (Area Radiation Monitor) |
| Reactor Room Air Particulate Monitor | CAM | DPM/ft³ | CAM |
| Reactor Room Gross-Gaseous Monitor | CAM | DPM/ft³ | (Combined with CAM) |
| Demineralizer RAM | Gamma monitor | mR/h | Demin monitor |
| East Radiography Station Foil RAM | Radiation monitor | mR/h | N/A (no radiography) |
| North Radiography Station Foil RAM | Radiation monitor | mR/h | N/A |
| North Radiography Station Cell RAM | Radiation monitor | mR/h | N/A |

### 2.6 Other

| NRAD Name | Type | NETL TRIGA Equivalent |
|-----------|------|----------------------|
| Reactor Tank Water Level | Water level monitor, ft-in | Pool level |
| Scram Button | Boolean | SCRAM input |

---

## 3. Limits Schema (Gap Analysis)

**This is the most valuable part of the NRAD ontology for Neutron OS.**

### 3.1 Proposed `sensor_limits` Table

```sql
CREATE TABLE gold.sensor_limits (
    limit_id UUID PRIMARY KEY,
    sensor_id UUID REFERENCES sensors(sensor_id),
    
    -- Limit definition
    limit_type VARCHAR(100),           -- 'High temperature', 'Low water level', etc.
    limit_operator VARCHAR(20),        -- 'Greater than', 'Less than', 'Between', 'Boolean'
    limit_value JSONB,                 -- Flexible: number, string, array
    limit_units VARCHAR(20),
    
    -- Logic for multi-channel (e.g., "2 out of 3")
    required_logic VARCHAR(20),        -- '2 of 3', '3 of 3', NULL for single
    
    -- Regulatory classification
    safety_importance VARCHAR(50),     -- 'Safety limit', 'LCO', 'Scram function', 'Operational limit'
    reference VARCHAR(200),            -- 'TSR-406 pg. 17', 'SAR-406 pg 3-16'
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    created_by VARCHAR(100)
);
```

### 3.2 Example Data (from NRAD)

```sql
INSERT INTO gold.sensor_limits VALUES
-- Fuel Temperature Safety Limits
(gen_random_uuid(), '<fuel_temp_sensor_id>', 
 'High temperature, cladding less than 500 C', 'Greater than', '1150', '°C',
 NULL, 'Safety limit', 'TSR-406 pg 16', NOW(), NULL, 'system'),

(gen_random_uuid(), '<fuel_temp_sensor_id>',
 'High temperature, cladding greater than 500 C', 'Greater than', '950', '°C',
 NULL, 'Safety limit', 'TSR-406 pg 16', NOW(), NULL, 'system'),

-- Multi-Range Linear Channel Scram Functions
(gen_random_uuid(), '<nmp1_sensor_id>',
 'High power level', 'Greater than or equal to', '120', 'Percent Power',
 '2 of 3', 'Scram function', 'SAR-406 pg. 6-10', NOW(), NULL, 'system'),

(gen_random_uuid(), '<nmp1_sensor_id>',
 'Low voltage limit', 'Less than', '300', 'V',
 '2 of 3', 'Scram function', 'SAR-406 pg. 6-10', NOW(), NULL, 'system'),

-- Reactor Tank LCO
(gen_random_uuid(), '<tank_level_sensor_id>',
 'Low water level limit', 'Less than', '"10, 3"', 'ft, in',
 NULL, 'LCO', 'TSR-406 pg. 23', NOW(), NULL, 'system');
```

### 3.3 Limit Checking Query

```sql
-- Check all sensors against their limits
WITH current_readings AS (
    SELECT sensor_id, value, timestamp
    FROM silver.sensor_readings
    WHERE timestamp > NOW() - INTERVAL '1 minute'
),
limit_violations AS (
    SELECT 
        cr.sensor_id,
        sl.limit_type,
        sl.safety_importance,
        cr.value AS current_value,
        sl.limit_value,
        sl.limit_operator,
        CASE 
            WHEN sl.limit_operator = 'Greater than' AND cr.value::float > sl.limit_value::float THEN TRUE
            WHEN sl.limit_operator = 'Less than' AND cr.value::float < sl.limit_value::float THEN TRUE
            WHEN sl.limit_operator = 'Greater than or equal to' AND cr.value::float >= sl.limit_value::float THEN TRUE
            ELSE FALSE
        END AS is_violated
    FROM current_readings cr
    JOIN gold.sensor_limits sl ON cr.sensor_id = sl.sensor_id
)
SELECT * FROM limit_violations WHERE is_violated = TRUE;
```

---

## 4. Analysis Integration (ML/SM Models)

### 4.1 NRAD Analysis Nodes

```json
{
    "name": "ML Operation Prediction",
    "class_name": "Analysis",
    "properties": {
        "type": "LSTM",
        "feature_variables": [
            "shim_rod_1_position", 
            "shim_rod_2_position", 
            "regulating_rod_1_position", 
            "NRAD_RX_Hx_Inlet_Th"
        ],
        "target_variables": [],
        "file_type": "pickle"
    }
}
```

### 4.2 Neutron OS `models` Table Mapping

```sql
CREATE TABLE gold.models (
    model_id UUID PRIMARY KEY,
    model_name VARCHAR(100),
    model_type VARCHAR(50),            -- 'LSTM', 'Gaussian process regression', 'XGBoost'
    
    -- Feature/target mapping
    feature_variables JSONB,           -- Array of sensor names or tag names
    target_variables JSONB,            -- What the model predicts
    
    -- Model storage
    model_artifact_path VARCHAR(500),  -- S3/MinIO path to pickle/ONNX
    model_version VARCHAR(20),
    
    -- Metadata
    trained_at TIMESTAMP,
    training_data_range TSTZRANGE,     -- Time range of training data
    metrics JSONB,                     -- {'rmse': 0.05, 'r2': 0.95}
    
    -- Lineage
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Data Flow Comparison

### 5.1 NRAD Data Flow (Graph Edges)

```
Detectors → TINA DAQ → CSV File → Analysis → Results File → UI
    │                      │
    │                      └── Direct to UI (real-time display)
    │
    └── has_setting_limits → Limits
```

### 5.2 Neutron OS Data Flow (dbt Lineage)

```
Sensors → Redpanda → Bronze (raw) → Silver (typed) → Gold (curated) → Superset
    │                    │              │                │
    │                    │              │                └── ML Training
    │                    │              │
    │                    │              └── Limit checking
    │                    │
    │                    └── Anomaly detection
    │
    └── sensor_limits (static reference)
```

### 5.3 Hybrid Integration Point

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNC POINT: Asset Registry                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   DEEPLYNX                              NEUTRON OS                          │
│   ┌──────────────────┐                  ┌──────────────────┐               │
│   │  Ontology        │                  │  Iceberg Tables  │               │
│   │  ┌────────────┐  │    Sync every    │  ┌────────────┐  │               │
│   │  │ Detector   │  │◀──── 1 hour ────▶│  │  sensors   │  │               │
│   │  │ nodes      │  │                  │  │  table     │  │               │
│   │  └────────────┘  │                  │  └────────────┘  │               │
│   │  ┌────────────┐  │                  │  ┌────────────┐  │               │
│   │  │ Limits     │  │◀──── Sync ──────▶│  │sensor_limits│ │               │
│   │  │ nodes      │  │   (bi-directional)│  │  table     │  │               │
│   │  └────────────┘  │                  │  └────────────┘  │               │
│   └──────────────────┘                  └──────────────────┘               │
│                                                                             │
│   Real-time state                       Historical analysis                 │
│   Limit checking (graph)                Trend analysis (SQL)                │
│   WebSocket to UI                       Superset dashboards                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Gaps to Address in Neutron OS

| NRAD Has | Neutron OS Status | Action |
|----------|------------------|--------|
| Limits with safety importance | ❌ Missing | Add `sensor_limits` table |
| SAR/TSR reference citations | ❌ Missing | Add `reference` column |
| Required logic (2 of 3) | ❌ Missing | Add `required_logic` column |
| Modes of Operation | ❌ Missing | Add `operational_modes` table |
| ML model definitions | ⚠️ Partial | Enhance `models` table |
| Tag name mapping | ⚠️ Partial | Add `tag_name` to sensors |

---

## 7. Recommended Actions

### Immediate (This Week)
1. **Add `sensor_limits` table** to Gold schema
2. **Map NETL TRIGA sensors** to NRAD-compatible structure
3. **Add `safety_importance` and `reference`** columns

### Short-term (2-4 Weeks)
4. **Implement limit checking** dbt model
5. **Create `operational_modes` table**
6. **Define sync format** for DeepLynx ↔ Neutron OS

### Medium-term (1-2 Months)
7. **Propose unified ontology** to INL
8. **Build bi-directional sync** proof-of-concept
9. **Document in shared schema spec**

---

## Appendix: Full NRAD Measurements File Columns

From the ontology's Data File node:

```
NRAD_RX_Rx_ON          -- Reactor on/off status
NRAD_RX_NMP1_PWR       -- Multi-range channel 1 power
NRAD_RX_NMP2_PWR       -- Multi-range channel 2 power
NRAD_RX_NMP3_PWR       -- Multi-range channel 3 power
NRAD_RX_PERIOD         -- Reactor period
NRAD_RX_SHIM1_POS      -- Shim rod 1 position
NRAD_RX_SHIM2_POS      -- Shim rod 2 position
NRAD_RX_REG_POS        -- Regulating rod position
NRAD_RX_SHIM1_CV       -- Shim rod 1 control voltage
NRAD_RX_SHIM2_CV       -- Shim rod 2 control voltage
NRAD_RX_REG_CV         -- Regulating rod control voltage
NRAD_RX_Tank_Temp_T1   -- Tank temperature
NRAD_RX_Hx_Inlet_Th    -- Heat exchanger inlet temperature
NRAD_RX_Pri_Flow       -- Primary flow
```

These map directly to time-series columns in our Bronze layer.

---

*Document created: January 15, 2026*
*Based on: nrad_dt_generic_ontology_v4.txt*
