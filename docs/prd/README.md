# Neutron OS — Product Requirements Documents

This folder contains all Product Requirements Documents (PRDs) for Neutron OS.

## Document Structure

```
prd/
├── neutron-os-executive-prd.md    # Executive summary, links to all modules
│
├── Core Infrastructure (Cross-Cutting Concerns)
│   ├── data-platform-prd.md       # Core data lakehouse platform
│   ├── scheduling-system-prd.md   # Unified scheduling across modules
│   └── compliance-tracking-prd.md # Regulatory monitoring & reporting
│
├── Application Modules
│   ├── reactor-ops-log-prd.md     # Console checks, shift handoffs
│   ├── experiment-manager-prd.md  # Sample lifecycle tracking
│   └── analytics-dashboards-prd.md # Superset visualizations
│
└── Optional Modules
    └── medical-isotope-prd.md     # Isotope production & fulfillment
```

## Reading Order

1. **Start here:** [Executive PRD](neutron-os-executive-prd.md) — Overview of all modules, user journeys, success metrics

2. **Core Infrastructure (Cross-Cutting):**
   - [Data Platform PRD](data-platform-prd.md) — Lakehouse architecture, data flow
   - [Scheduling System PRD](scheduling-system-prd.md) — Time management, resource allocation
   - [Compliance Tracking PRD](compliance-tracking-prd.md) — Regulatory monitoring, evidence

3. **Application Modules:**
   - [Reactor Ops Log PRD](reactor-ops-log-prd.md) — Console logging, maintenance tracking
   - [Experiment Manager PRD](experiment-manager-prd.md) — Sample metadata, chain of custody
   - [Analytics Dashboards PRD](analytics-dashboards-prd.md) — Superset visualizations

4. **Optional Modules:**
   - [Medical Isotope PRD](medical-isotope-prd.md) — Production & fulfillment (off by default)

## All PRDs

| Document | Scope | Type | Status |
|----------|-------|------|--------|
| [Executive PRD](neutron-os-executive-prd.md) | Platform overview | Executive | Active |
| **Core Infrastructure** | | | |
| [Data Platform PRD](data-platform-prd.md) | Lakehouse, ingestion | Cross-cutting | Draft |
| [Scheduling System PRD](scheduling-system-prd.md) | Time slots, resources | Cross-cutting | Draft |
| [Compliance Tracking PRD](compliance-tracking-prd.md) | Regulatory, evidence | Cross-cutting | Draft |
| **Application Modules** | | | |
| [Reactor Ops Log PRD](reactor-ops-log-prd.md) | Operations logging | Module | Draft |
| [Experiment Manager PRD](experiment-manager-prd.md) | Sample tracking | Module | Draft |
| [Analytics Dashboards PRD](analytics-dashboards-prd.md) | Visualizations | Module | Draft |
| **Optional Modules** | | | |
| [Medical Isotope PRD](medical-isotope-prd.md) | Production workflow | Module | Draft |

## Journey Maps

Each PRD includes **Mermaid diagrams** for:
- User journey maps (experience over time)
- State machines (entity lifecycles)
- Flow diagrams (system interactions)

These can be rendered by:
- GitHub/GitLab Markdown preview
- VS Code with Mermaid extension
- [Mermaid Live Editor](https://mermaid.live)
- AI tools (Claude, GPT) for higher-fidelity versions

## Related Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| Technical Spec | [specs/neutron-os-master-tech-spec.md](../specs/neutron-os-master-tech-spec.md) | Architecture, schemas, APIs |
| Executive Tech Summary | [specs/neutron-os-executive-summary.md](../specs/neutron-os-executive-summary.md) | 2-page technical overview |
| Design Prompts | [specs/design-prompts/](../specs/design-prompts/) | Implementation guides |
| Architecture Decisions | [adr/](../adr/) | Decision records |

## Stakeholder Input

PRDs incorporate feedback from:
- **Khiloni Shah** — Experiment workflow, sample metadata
- **Jim (TJ)** — Ops Log requirements, compliance
- **Nick Luciano** — Time-series data, security, dashboards

## Archive

Superseded documents are in `_archive/`:
- `neutron-os-master-prd.md` → Superseded by [Executive PRD](neutron-os-executive-prd.md)
- `elog-prd-*.md` → Superseded by [Reactor Ops Log PRD](reactor-ops-log-prd.md)

## Legacy Documents

The following are superseded by the new structure:
- `neutron-os-master-prd.md` → See [Executive PRD](neutron-os-executive-prd.md)
- `elog-prd-*.md` → See [Reactor Ops Log PRD](reactor-ops-log-prd.md)

Keep markdown and Word versions synchronized.
