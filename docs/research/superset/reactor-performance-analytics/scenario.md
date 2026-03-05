# Scenario: Reactor Performance Analytics

**Status:** Draft (hypothetical scenario combining existing data sources)  
**Purpose:** Validate end-to-end data platform by combining multiple data sources

---

## User Story

As a **reactor operator or researcher**, I want to **analyze reactor performance over time by correlating power output, xenon poisoning, fuel burnup, and control rod positions** so that I can **understand operational patterns, optimize startup procedures, and predict reactivity requirements**.

---

## Questions This Dashboard Answers

1. How does xenon concentration correlate with power history over the past week?
2. What is the current excess reactivity given fuel burnup and xenon state?
3. How have control rod positions changed relative to power demand?
4. Which fuel elements have the highest burnup and may need attention?
5. What is the typical startup time from cold critical to full power?

---

## Charts

| Chart | Type | X-Axis | Y-Axis | Data Source | Notes |
|-------|------|--------|--------|-------------|-------|
| Power & Xenon Timeline | Dual-axis line | Timestamp | Power (kW), Xe-135 (atoms) | time-series + Xe_burnup | 7-day rolling window |
| Rod Position vs Power | Scatter | Linear Power | Avg Rod Height | time-series | Color by rod (Tran, Shim1, Shim2, Reg) |
| Fuel Burnup Heatmap | Heatmap | Core Position (A-H rings) | Burnup (g U-235) | core config | Hexagonal core layout |
| Excess Reactivity Trend | Line | Date | Excess ρ ($) | Calculated | Derived from burnup + Xe + temp |
| Temperature Correlation | Scatter | Fuel Temp | Water Temp | time-series | With power color gradient |
| Startup Time Distribution | Histogram | Minutes to Full Power | Count | Derived | From run analysis |
| Daily Energy Production | Bar | Date | MWh | time-series | Integrated power |

---

## Filters

| Filter | Field | Type | Default |
|--------|-------|------|---------|
| Date Range | timestamp | Date picker | Last 7 days |
| Power Threshold | linear_power | Slider | > 0 kW |
| Core Configuration | config_date | Dropdown | Latest |
| Rod Selection | rod_name | Multi-select | All |

---

## Data Requirements

### Gold Tables

| Table | Key Columns | Grain | Refresh | Source |
|-------|-------------|-------|---------|--------|
| `reactor_hourly_metrics` | hour, avg_power, max_power, avg_fuel_temp, avg_water_temp, energy_kwh | Hour | Hourly | Silver: reactor_timeseries |
| `rod_positions_hourly` | hour, rod_name, avg_position, min_position, max_position | Hour × Rod | Hourly | Silver: reactor_timeseries |
| `xenon_state_hourly` | hour, xe_concentration, i_concentration, cumulative_burnup_mwh | Hour | Hourly | Silver: xenon_dynamics |
| `fuel_burnup_current` | position, element_id, u235_burned_g, burnup_pct, config_date | Element | Daily | Silver: core_configs |
| `excess_reactivity_daily` | date, excess_rho_dollars, xe_worth, temp_worth, burnup_worth | Day | Daily | Calculated from above |
| `run_statistics` | run_id, start_time, end_time, startup_duration_min, peak_power, total_energy | Run | On completion | Derived from time-series |

### Silver Tables

| Table | Transformations | Source |
|-------|-----------------|--------|
| `reactor_timeseries_clean` | Null handling, outlier flagging, unit normalization, timestamp parsing | Bronze: serial_data CSVs |
| `xenon_dynamics_clean` | Resample to hourly, interpolate gaps | Bronze: Xe_burnup_2025.csv |
| `core_configs_clean` | Parse position codes, calculate burnup percentages | Bronze: static/core/*.csv |
| `rod_calibration_clean` | Join with temperature data, calculate worth curves | Bronze: CRH + rho_vs_T |

### Bronze Tables (Raw Ingestion)

| Table | Source Files | Ingestion Pattern |
|-------|--------------|-------------------|
| `serial_data_raw` | `TRIGA_Digital_Twin/.../serial_data/*.csv` | Daily append |
| `xenon_burnup_raw` | `static/csv/Xe_burnup_2025.csv` | Full reload (simulation output) |
| `core_config_raw` | `static/core/*.csv` | Event-driven (on new config) |
| `rod_calibration_raw` | `static/csv/CRH_*.csv`, `rho_vs_T.csv` | Event-driven |

---

## Sample Data Columns

### From `serial_data/*.csv`
```
timestamp, Tran, Shim1, Shim2, Reg, FuelTemp1, FuelTemp2, WaterTemp, NM, NPP, NP, LinearPower
```

### From `Xe_burnup_2025.csv`
```
Time, Xe, I, BU (MWh)
```

### From `static/core/2025_01_10_BOC_in_core.csv`
```
Position, Type, Element, U235 Burned (g)
```

### From `rho_vs_T.csv`
```
rho, T_fuel, keff
```

---

## Calculated Metrics

### Excess Reactivity
```python
excess_rho = (
    initial_excess_rho           # From beginning of cycle
    - burnup_reactivity_loss     # From fuel depletion
    - xenon_worth                # From Xe-135 concentration  
    - temperature_defect         # From rho_vs_T lookup
)
```

### Startup Duration
```python
# Find first timestamp where power > threshold after a gap
startup_start = first_timestamp_where(power > 1kW AND previous_power == 0)
startup_end = first_timestamp_where(power > 900kW after startup_start)
startup_duration = startup_end - startup_start
```

---

## Data Joins

```
reactor_hourly_metrics
    ├── JOIN xenon_state_hourly ON hour
    ├── JOIN rod_positions_hourly ON hour
    └── JOIN fuel_burnup_current ON config_date (latest before hour)
            └── JOIN excess_reactivity_daily ON date(hour)
```

---

## Acceptance Criteria

- [ ] All 7 charts render with real data
- [ ] Date range filter updates all charts simultaneously
- [ ] Power & Xenon timeline shows clear inverse correlation during shutdown
- [ ] Fuel burnup heatmap accurately reflects core geometry (hexagonal)
- [ ] Excess reactivity trend matches operator expectations
- [ ] Dashboard loads in <3s for 7-day view
- [ ] Dashboard loads in <10s for 30-day view

---

## dbt Tests (Write First)

```yaml
# data/dbt/models/gold/schema.yml
models:
  - name: reactor_hourly_metrics
    tests:
      - dbt_utils.recency:
          datepart: hour
          field: hour
          interval: 4  # Alert if no data in 4 hours during ops
    columns:
      - name: avg_power
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1500

  - name: xenon_state_hourly
    columns:
      - name: xe_concentration
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0

  - name: fuel_burnup_current
    tests:
      - unique:
          column_name: "position || '-' || config_date"
    columns:
      - name: u235_burned_g
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 40  # Typical TRIGA element ~38g U-235 initial
```

---

## Implementation Priority

1. **Phase 1a:** `reactor_hourly_metrics` + Power chart (validates time-series pipeline)
2. **Phase 1b:** `xenon_state_hourly` + join with power (validates multi-source join)
3. **Phase 1c:** `fuel_burnup_current` + heatmap (validates spatial visualization)
4. **Phase 2:** Calculated metrics (excess reactivity, startup duration)
5. **Phase 3:** Full dashboard with all filters

---

## Open Questions

1. What time resolution is needed? (Current: hourly aggregation, raw is per-second)
2. Should we include MPACT shadow predictions alongside measured data?
3. What alert thresholds should trigger notifications? (e.g., Xe > X, burnup > Y)
4. How far back should historical data be loaded? (All available vs. rolling window)
