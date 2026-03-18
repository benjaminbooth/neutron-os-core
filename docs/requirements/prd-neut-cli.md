# Product Requirements Document: neut CLI

> **Implementation Status: 🟡 Partial** — Core CLI, extension discovery, and 17 builtin extensions shipped. Agents (Neut, EVE, M-O, PR-T, D-FIB) operational. Future domain commands (`log`, `sim`, `model`, `twin`, `data`, `infra`) planned.

**Module:** neut Command-Line Interface
**Status:** Active Development (v0.4.0)
**Last Updated:** 2026-03-17
**Parent:** [Executive PRD](prd-executive.md)
**Tech Spec:** [neut CLI Specification](../tech-specs/spec-neut-cli.md)

---

## Executive Summary

`neut` is the unified command-line interface for Neutron OS. It provides operators, researchers, and developers a single entry point for interacting with the platform — from querying ops logs to managing surrogate models to orchestrating simulations.

The CLI embodies the platform philosophy: **power tools for experts, sensible defaults for everyone else**.

Every capability in NeutronOS ships as an **extension**, discovered via `neut-extension.toml` manifests. The CLI is the primary interface for both humans and agents — the same commands a user types are the same commands agents invoke programmatically.

---

## Problem Statement

Nuclear facilities currently interact with data and simulations through:
- **Fragmented interfaces**: Web dashboards, ad-hoc scripts, manual file transfers
- **No automation path**: Can't script operational queries or model deployments
- **Platform lock-in**: GUI-only tools prevent integration with CI/CD pipelines
- **Tribal knowledge**: "How to run X" lives in people's heads, not in reproducible commands

---

## User Personas

| Persona | Primary Use Cases | Technical Level |
|---------|-------------------|-----------------|
| **Reactor Operator** | Query ops log, check status, export compliance reports | Basic CLI |
| **Research Engineer** | Run simulations, manage experiments, analyze data | Intermediate |
| **Data Engineer** | Orchestrate pipelines, manage schemas, debug transforms | Advanced |
| **ML Engineer** | Train/deploy surrogates, manage WASM extensions | Advanced |
| **DevOps** | Infrastructure management, CI/CD integration | Expert |

---

## The Agent Team

NeutronOS agents are named after robots from Pixar's WALL-E — a film about a world made uninhabitable by environmental neglect. The irony is intentional: NeutronOS helps build the cleanest large-scale energy source available.

| Agent | Character | CLI | Role |
|-------|-----------|-----|------|
| **Neut** | The Axiom | `neut chat` | Orchestrator — routes commands, delegates to other agents, maintains context |
| **EVE** | Probe droid | `neut signal` | Event Evaluator — signal detection and intelligence extraction |
| **M-O** | Cleaning robot | `neut mo` | Micro-Obliterator — resource stewardship and system hygiene |
| **PR-T** | Beauty bot | `neut pub` | Purty — document lifecycle, .md → polished .docx → publish |
| **D-FIB** | Medical bot | `neut doctor` | Defib — diagnostics, security health, configuration audit |
| **Mirror** | — | `neut mirror` | Public mirror gate — reviews content for sensitive data before publishing |

---

## Shipped Commands

### Core Platform

| Command | Extension | Kind | Description |
|---------|-----------|------|-------------|
| `neut config` | core | utility | Interactive onboarding wizard |
| `neut status` | status | utility | System health dashboard |
| `neut doctor` | dfib (D-FIB) | agent | Diagnose environment issues |
| `neut ext` | core | utility | Manage extensions (builtin + user) |
| `neut update` | update | utility | Dependency and migration updates |
| `neut settings` | settings | utility | View and edit neut settings |
| `neut test` | test | utility | Test orchestration |

### Agents

| Command | Extension | Description |
|---------|-----------|-------------|
| `neut chat` | neut_agent (Neut) | Interactive agent with tool calling. Alias: `neut code` |
| `neut signal` | eve_agent (EVE) | Agentic signal ingestion pipeline |
| `neut pub` | prt_agent (PR-T) | Document publishing lifecycle. Alias: `neut doc` |
| `neut mo` | mo_agent (M-O) | Resource steward — scratch, vitals, cleanup |
| `neut mirror` | mirror_agent | AI-powered sensitive data review before publishing |

### Tools & Services

| Command | Extension | Description |
|---------|-----------|-------------|
| `neut db` | db | PostgreSQL + pgvector infrastructure |
| `neut rag` | rag | RAG index management — index, search, sync the three-tier corpus |
| `neut demo` | demo | Guided demonstrations and walkthroughs |
| `neut note` | note | Quick personal notes — captured to RAG-indexed daily log |
| `neut serve` | web_api | Start the neut HTTP API server |

---

## Neut: The Orchestrator (`neut chat`)

Neut is the interactive agent — think Claude Code, but for nuclear facilities. Neut orchestrates all other agents and tools on behalf of the user.

### Interaction Modes

Neut operates in three modes that represent **levels of autonomy**, not different personalities. The default is Ask — the safest mode — and Neut escalates only with the user's consent.

| Mode | Autonomy | What Neut Does | Side Effects |
|------|----------|----------------|-------------|
| **Ask** (default) | None | Answers questions, explains, searches. Read-only. | Zero |
| **Plan** | Propose | Explores the problem, designs an approach, presents structured options. | Zero until approved |
| **Agent** | Execute | Runs multi-step tasks autonomously within scoped permissions. | Bounded writes |

### Escalation Model

Neut always starts in **Ask** mode. When a prompt implies action, Neut proposes escalation rather than assuming permission:

```
Operator: "Set up experiment UT-TRIGA-043 with the standard NAA config"

Neut (Ask): I can help set that up. This will create a new experiment
            record, reserve beam port 3, and generate the ROC
            authorization request.

            → Switch to Plan mode to walk through the steps? [y/N]
```

Power users can skip escalation with `neut chat --mode plan` or mid-conversation with `/plan`, `/ask`, `/agent`.

### Slash Commands

Slash commands are the composable action layer inside `neut chat`. Each command is registered by an extension, follows a standard four-step flow (collect context → present choices → confirm intent → dispatch + report), and always shows the underlying `neut` CLI invocation it dispatched.

This design teaches users the machine API through the conversational interface.

Full slash command design in [CLI Specification §Slash Commands](../tech-specs/spec-neut-cli.md).

### Mode Guardrails

| Guardrail | Behavior |
|-----------|----------|
| **Writes always confirm** | Even in Agent mode, Neut pauses before creating records, publishing, or sending notifications |
| **Agent scope is per-session** | Agent permissions don't persist across sessions |
| **Escalation is reversible** | `/ask` returns to read-only at any time |
| **Structured decisions** | Bounded option spaces use interactive forms, not freetext |
| **Audit trail** | All mode transitions and approved actions are logged |

---

## Planned Commands

These commands are designed but not yet implemented. Each will ship as an extension.

### Reactor Operations (`neut log`)

```bash
neut log query --last 1h
neut log query --type console_check --since 2026-01-20
neut log entry create --type general_note --content "Shift turnover complete"
neut log export --format nrc --range 2026-01-01:2026-01-31 -o january.pdf
```

See [Reactor Ops Log PRD](prd-reactor-ops-log.md).

### Simulation Orchestration (`neut sim`)

```bash
neut sim run scenario.yaml --reactor netl-triga
neut sim list
neut sim status run-12345
```

### Surrogate Model Management (`neut model`)

```bash
neut model list --type surrogate
neut model deploy triga-thermal-v2.wasm --capabilities wasi:clocks
neut model validate triga-thermal-v2.wasm --test-suite thermal-benchmarks
```

See [Model Corral PRD](prd-model-corral.md).

### Digital Twin (`neut twin`)

```bash
neut twin state netl-triga
neut twin sync netl-triga
neut twin predict netl-triga --horizon 100ms
```

See [Digital Twin Hosting PRD](prd-digital-twin-hosting.md).

### Data Platform (`neut data`)

```bash
neut data query "SELECT * FROM gold.reactor_hourly_metrics LIMIT 10"
neut data pipeline status
neut data backfill bronze.reactor_timeseries_raw --start 2026-01-01
```

See [Data Platform PRD](prd-data-platform.md).

### Infrastructure (`neut infra`)

```bash
neut infra health
neut infra logs neutron-gateway --since 1h
neut infra deploy --env staging
```

### Media Library (`neut media`)

```bash
neut media ingest photo.jpg --tag pool-clarity --link ops:2026-02-26-shift-A
neut media search "beam port schedule" --type audio
```

See [Media Library PRD](prd-media-library.md).

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Startup time** | <100ms (no network) |
| **Authentication** | OAuth2/OIDC, API keys, certificate |
| **Output formats** | Table, JSON, YAML, CSV |
| **Shell completion** | bash, zsh, fish, PowerShell |
| **Offline mode** | Graceful degradation for local operations |
| **Cross-platform** | macOS, Linux, Windows |

---

## User Experience Principles

### Progressive Disclosure

```bash
# Simple (sensible defaults)
neut log query

# Detailed (when needed)
neut log query --type console_check --facility netl-triga --since 2026-01-20T08:00:00Z --format json
```

### Helpful Errors

```bash
$ neut model deploy broken.wasm
Error: Model validation failed

  × Missing required export: predict
  │
  │ The model must implement the neutron:surrogate/model interface.
  │ Required exports: predict, validate, get-metadata
  │
  help: Run `neut model validate broken.wasm --verbose` for details
```

### Confirmation for Destructive Operations

```bash
$ neut data backfill bronze.reactor_timeseries_raw --start 2020-01-01
⚠️  This will process 2.3 TB of data (~4 hours)

Continue? [y/N]
```

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| LLM gateway | Agent intelligence (Neut, EVE, M-O, PR-T, D-FIB) |
| Authentication service | OAuth2/OIDC integration |
| PostgreSQL + pgvector | State management, RAG embeddings |
| Pandoc | Document generation (PR-T) |
| Playwright | Browser-based OneDrive/Teams integration |
| WASM runtime | Local model validation |

---

## Open Questions

1. **Distribution**: Homebrew? apt? Standalone binary?
2. **Agent mode permissions**: Per-noun granularity (e.g., "agent can write to ops log but not compliance")? Or simpler role-based scoping via OpenFGA?
3. **Escalation UX in non-interactive contexts**: How do scripts/CI handle mode transitions? Likely: `--mode agent --yes` for pre-approved pipelines with explicit scope flags.
4. **Session persistence**: Should Plan mode drafts survive across sessions? Or are they ephemeral?

---

*For the complete command hierarchy, configuration schema, and implementation details, see the [CLI Technical Specification](../tech-specs/spec-neut-cli.md).*
