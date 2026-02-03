# Analytics & Use Case Scenarios

This folder contains scenarios that drive test-first development of analytics and dashboards.

## Philosophy

**Scenarios define what users need to see before we build pipelines.**

Instead of building data pipelines first and then figuring out dashboards, we:
1. Define the questions users need answered
2. Design the charts/visualizations
3. Specify the Gold tables needed
4. Write dbt tests for those tables
5. Build pipelines to pass the tests

## Structure

```
scenarios/
├── README.md           # This file
└── superset/           # Apache Superset dashboard scenarios
    ├── README.md
    ├── Superset_Scenarios_For_Review.docx
    └── reactor-performance-analytics/
        └── scenario.md
```

## Scenario Categories

### [`superset/`](superset/) - Dashboard Scenarios

Scenarios for Apache Superset dashboards. Each scenario includes:
- User story (who needs what, why)
- Questions the dashboard answers
- Proposed charts with types and priorities
- Required filters
- Data sources and Gold tables needed

**Current Scenarios:**
| Scenario | Priority | Status |
|----------|----------|--------|
| Reactor Operations Dashboard | P0 | Designed |
| Reactor Performance Analytics | P0 | Designed |
| Ops Log Activity Summary | P1 | Placeholder |
| Experiment Tracking | P2 | Placeholder |
| Audit Readiness | P1 | Placeholder |

## Creating a New Scenario

1. Create folder: `scenarios/<tool>/<scenario-name>/`
2. Add `scenario.md` with:
   - User story
   - Questions answered
   - Chart specifications
   - Filter requirements
   - Data source mapping
3. Define Gold table schemas needed
4. Write dbt tests before building pipelines

## Stakeholder Review

Word document for non-technical stakeholder review:
- `superset/Superset_Scenarios_For_Review.docx`

Nick Luciano is the primary reviewer for Superset scenarios.
