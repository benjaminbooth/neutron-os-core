# Technical Specifications

This folder contains technical specifications, design documents, and research for Neutron OS.

**PRDs define *what* to build. Specs define *how* to build it.**

## Document Structure

```
specs/
├── spec-executive.md    # Full technical architecture
├── spec-executive.md   # 2-page technical overview
├── design-prompts/                   # Implementation guides for AI/dev
├── diagrams/                         # Architecture diagrams
├── deeplynx-assessment.md            # External technology assessments
├── platform-comparison-databricks.md # Platform alternatives analysis
└── hyperledger-nuclear-use-cases.md  # Research: blockchain applications
```

## Core Specifications

| Document | Purpose | Audience |
|----------|---------|----------|
| [Master Tech Spec](spec-executive.md) | Complete architecture, schemas, APIs | Engineers |
| [Executive Tech Spec](spec-executive.md) | 2-page technical overview | Stakeholders, PMs |

## Design Prompts

The `design-prompts/` folder contains implementation guides:

| Prompt | Component |
|--------|-----------|
| [Bronze Layer Ingest](design-prompts/prompt-bronze-layer-ingest.md) | Dagster + Iceberg ingestion |
| [dbt Silver Models](design-prompts/prompt-dbt-silver-models.md) | Data transformation |
| [Superset Dashboards](design-prompts/prompt-superset-dashboards.md) | Analytics visualizations |
| [Dagster Orchestration](design-prompts/prompt-dagster-orchestration.md) | Pipeline scheduling |

## Research & Analysis

| Document | Topic |
|----------|-------|
| [DeepLynx Assessment](deeplynx-assessment.md) | INL DeepLynx vs Neutron OS |
| [Platform Comparison](platform-comparison-databricks.md) | Databricks/Snowflake alternatives |
| [Hyperledger Use Cases](hyperledger-nuclear-use-cases.md) | Blockchain for nuclear |

## Proposals & External Docs

| Document | Purpose |
|----------|---------|
| [CINR Pre-App](CINR_PreApp_Concept_Draft.md) | Grant pre-application |
| [LDRD Collaboration](LDRD_Collaboration_OnePager.md) | INL partnership proposal |

## Relationship to PRDs

| PRD (what) | Spec (how) |
|------------|------------|
| [Executive PRD](../prd/neutron-os-executive-prd.md) | [Master Tech Spec](spec-executive.md) |
| [Reactor Ops Log PRD](../prd/reactor-ops-log-prd.md) | Tech spec §3.4.5 (log_entries schema) |
| [Experiment Manager PRD](../prd/experiment-manager-prd.md) | Tech spec §3.4.6 (sample_tracking schema) |
| [Analytics PRD](../prd/analytics-dashboards-prd.md) | [Superset Design Prompt](design-prompts/prompt-superset-dashboards.md) |

## Word Documents

Word (.docx) versions are maintained for stakeholder review:
- `neutron-os-master-tech-spec.docx`
- `neutron-os-executive-summary.docx`
- `deeplynx-assessment.docx`
