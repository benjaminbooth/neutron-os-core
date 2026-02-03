# Superset Scenarios

This directory contains specifications for Superset dashboards that drive the data platform design.

## Workflow

1. **Scenario Definition** → Document user needs, questions, charts, filters
2. **Gold Schema Derivation** → What tables/columns support this dashboard?
3. **dbt Tests First** → Write tests that will pass when data is ready
4. **Pipeline Implementation** → Bronze → Silver → Gold transforms
5. **Dashboard Build** → Create in Superset, export JSON to Git
6. **Stakeholder Review** → Iterate until approved

## Scenario Template

Each scenario should include:

```markdown
# Scenario: {Name}

## User Story
As a {role}, I want to {action} so that {benefit}.

## Questions This Dashboard Answers
1. {Question 1}
2. {Question 2}

## Charts
| Chart | Type | X-Axis | Y-Axis | Notes |
|-------|------|--------|--------|-------|

## Filters
| Filter | Field | Type | Default |
|--------|-------|------|---------|

## Data Requirements
| Gold Table | Key Columns | Grain | Refresh |
|------------|-------------|-------|---------|

## Sample Data Source
{Where does the raw data come from?}

## Acceptance Criteria
- [ ] Dashboard loads in <2s
- [ ] Filters work as expected
- [ ] Data refreshes per schedule
```

## Current Scenarios

| # | Scenario | Status | Owner |
|---|----------|--------|-------|
| 1 | [Reactor Performance Analytics](./reactor-performance-analytics/) | Draft | Pending Nick input |
| 2 | Reactor Operations Dashboard | Pending | Nick Luciano |
| 3 | Ops Log Activity Summary | Pending | TBD |
| 4 | Experiment Tracking | Pending | TBD |
| 5 | Audit Readiness | Pending | TBD |

## Data Sources Available

From existing TRIGA repositories:

| Source | Location | Description |
|--------|----------|-------------|
| Reactor time-series | `serial_data/*.csv` | Power, temps, rod positions (daily CSVs) |
| Core configurations | `static/core/*.csv` | Fuel element burnup, positions |
| Xenon dynamics | `static/csv/Xe_burnup_2025.csv` | Xe-135, I-135 vs burnup (433K rows) |
| Rod calibration | `static/csv/CRH_2025_Jan.csv` | Critical rod height measurements |
| Reactivity tables | `static/csv/rho_vs_T.csv` | Reactivity vs temperature |
| Rod worth | `static/inference/each_rho_*.csv` | Differential/integral rod worth |
