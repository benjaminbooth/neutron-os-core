# Product Requirements Document: neut CLI

**Module:** neut Command-Line Interface  
**Status:** Planning  
**Last Updated:** February 26, 2026  
**Parent:** [Executive PRD](neutron-os-executive-prd.md)  
**Tech Spec:** [neut CLI Specification](../specs/neut-cli-spec.md)  
**Brand Reference:** [Brand Identity - CLI Section](../design/brand-identity.md#cli-identity)

---

## Executive Summary

`neut` is the unified command-line interface for Neutron OS. It provides operators, researchers, and developers a single entry point for interacting with the platform—from querying ops logs to managing surrogate models to orchestrating simulations.

The CLI embodies the platform philosophy: **power tools for experts, sensible defaults for everyone else**.

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

## Core Capabilities

### 1. Ops Log Interface (`neut log`)

```bash
# Query recent entries
neut log query --last 1h
neut log query --type console_check --since 2026-01-20

# Create entry (authenticated)
neut log entry create --type general_note --content "Shift turnover complete"

# Export for compliance
neut log export --format nrc --range 2026-01-01:2026-01-31 -o january.pdf
```

### 2. Simulation Orchestration (`neut sim`)

```bash
# Run scenario
neut sim run scenario.yaml --reactor netl-triga

# List available scenarios
neut sim list

# Check status
neut sim status run-12345
```

### 3. Surrogate Model Management (`neut model`)

```bash
# List registered models
neut model list --type surrogate

# Deploy model (WASM)
neut model deploy triga-thermal-v2.wasm --capabilities wasi:clocks

# Validate model
neut model validate triga-thermal-v2.wasm --test-suite thermal-benchmarks
```

### 4. Digital Twin State (`neut twin`)

```bash
# Get current state
neut twin state netl-triga

# Sync state from sensors
neut twin sync netl-triga

# Run prediction
neut twin predict netl-triga --horizon 100ms
```

### 5. Data Platform (`neut data`)

```bash
# Query lakehouse
neut data query "SELECT * FROM gold.reactor_hourly_metrics LIMIT 10"

# Check pipeline status
neut data pipeline status

# Trigger backfill
neut data backfill bronze.reactor_timeseries_raw --start 2026-01-01
```

### 6. Infrastructure (`neut infra`)

```bash
# Check service health
neut infra health

# View logs
neut infra logs neutron-gateway --since 1h

# Deploy (dev/staging)
neut infra deploy --env staging
```

### 7. Extension Management (`neut ext`)

```bash
# List installed extensions
neut ext list

# Install extension
neut ext install neutron-ext-xenon-tracker

# Validate WASM extension
neut ext validate ./my-extension.wasm
```

### 8. Interactive Chat Mode (`neut chat`)

An agentic assistant for working with reactor systems — think Claude Code, but for nuclear facilities. Neut is the friendly AI that powers the interactive experience; Neut Sense, Neut DocFlow, and other capabilities are tools Neut can invoke on behalf of the user.

```bash
# Start interactive session
neut chat

# Start with context
neut chat --context "investigating fuel temp anomaly from yesterday"

# Start in a specific mode
neut chat --mode plan
```

**Capabilities:**
- Natural language queries against sensor data, ops logs, experiment history
- Trend analysis and anomaly correlation
- Draft ops log entries, experiment requests, compliance reports
- Run predictions and compare against actuals
- Search procedures, tech specs, historical incidents
- Walk through experiment planning with safety checks
- Ingest and search media (`neut media` via conversation)
- Synthesize signals across sources (`neut sense` via conversation)

**Key Principle:** Human-in-the-loop for all writes. Neut can draft, analyze, and suggest — but the operator confirms before anything is committed.

#### Interaction Modes

Neut operates in three modes that represent **levels of autonomy**, not different personalities. The default is Ask — the safest mode — and Neut escalates only with the user's consent.

| Mode | Autonomy | What Neut Does | Side Effects |
|------|----------|----------------|-------------|
| **Ask** (default) | None | Answers questions, explains, searches. Read-only. | Zero |
| **Plan** | Propose | Explores the problem, designs an approach, presents structured options for approval. Interactive wizard for complex decisions (single/multi-select forms). | Zero until approved |
| **Agent** | Execute | Runs multi-step tasks autonomously within scoped permissions. Reports progress, pauses at checkpoints. | Bounded writes |

#### Escalation Model (Default Behavior)

Neut always starts in **Ask** mode. When a prompt implies action, Neut proposes escalation rather than assuming permission:

```
Operator: "Set up experiment UT-TRIGA-043 with the standard NAA config"

Neut (Ask): I can help set that up. This will create a new experiment
            record, reserve beam port 3, and generate the ROC
            authorization request.

            → Switch to Plan mode to walk through the steps? [y/N]
```

If the user confirms, Neut enters Plan mode and presents the steps as an interactive checklist. If the plan involves writes (creating records, publishing, sending notifications), Neut presents each action for explicit approval before executing.

```
Neut (Plan): Here's the setup plan for UT-TRIGA-043:

  1. Create experiment record
     - Isotope: standard NAA config (Au, Co, Fe monitors)
     - Facility: TPNT (Thermal Pneumatic Tube)
     - Duration: 1 hour
     - PI: [you]

  2. Check scheduling conflicts
     - Beam port 3 availability for requested dates

  3. Generate ROC authorization request
     - Pre-filled from experiment template

  Approve all and execute? [1/2/3/all/edit/cancel]
```

For batch operations with well-understood scope, Neut can propose Agent mode:

```
PM: "Synthesize this week's signals into PRD updates"

Neut (Ask): This is a multi-step synthesis across voice memos, Teams
            transcripts, and GitLab activity. I'll process signals,
            cluster by PRD, and draft updates for your review.

            → Run as Agent? You'll review drafts before anything
              is published. [y/N]
```

#### Power-User Shortcuts

Experienced users can skip escalation:

```bash
# Start directly in plan mode
neut chat --mode plan

# Or switch mid-conversation
/plan    # Enter plan mode
/ask     # Return to ask mode
/agent   # Enter agent mode (requires confirmation on first use per session)
```

#### Mode Guardrails

| Guardrail | Behavior |
|-----------|----------|
| **Writes always confirm** | Even in Agent mode, Neut pauses before creating records, publishing, or sending notifications |
| **Agent scope is per-session** | Agent permissions don't persist across sessions |
| **Escalation is reversible** | `/ask` returns to read-only at any time |
| **Structured decisions** | When the option space is bounded (e.g., pick a beam port, choose an isotope config), Neut presents interactive single/multi-select forms instead of freetext |
| **Audit trail** | All mode transitions and approved actions are logged to the session record |

### 9. Program Awareness (`neut sense`)

Neut Sense is the proactive sensing capability — ingesting signals from voice memos, Teams transcripts, GitLab activity, and other sources, then synthesizing them into actionable updates.

```bash
# Ingest all new signals
neut sense ingest --all

# Ingest from a specific source
neut sense ingest --source voice

# Draft weekly synthesis
neut sense synthesize --preview

# Check pipeline status
neut sense status
```

See [Neut Sense & Synthesis MVP Spec](../specs/sense-synthesis-mvp-spec.md) for full design.

### 10. Media Library (`neut media`)

Cross-cutting media management — recordings, photos, documents, and binary artifacts shared across all modules.

```bash
# Ingest a file
neut media ingest photo.jpg --tag pool-clarity --link ops:2026-02-26-shift-A

# Search recordings
neut media search "beam port schedule" --type audio

# Share with approval flow
neut media share <id> ops-team
```

See [Media Library PRD](media-library-prd.md) for full design.

### 11. Document Lifecycle (`neut doc`)

DocFlow manages document generation, publishing, and review cycles.

```bash
# Publish a document
neut doc publish docs/requirements/prd_foo.md

# Check document status
neut doc status

# Pull latest from storage
neut doc pull --all
```

See [DocFlow Specification](../specs/docflow-spec.md) for full design.

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

### 1. Progressive Disclosure

```bash
# Simple (sensible defaults)
neut log query

# Detailed (when needed)
neut log query --type console_check --facility netl-triga --since 2026-01-20T08:00:00Z --format json --include-metadata
```

### 2. Helpful Errors

```bash
$ neut model deploy broken.wasm
Error: Model validation failed

  × Missing required export: predict
  │
  │ The model must implement the neutron:surrogate/model interface.
  │ Required exports: predict, validate, get-metadata
  │
  help: Run `neut model validate broken.wasm --verbose` for details
  docs: https://docs.neutron-os.io/models/wasm-interface
```

### 3. Confirmation for Destructive Operations

```bash
$ neut data backfill bronze.reactor_timeseries_raw --start 2020-01-01
⚠️  This will process 2.3 TB of data (~4 hours)

Continue? [y/N]
```

---

## Mascot Integration

The newt mascot appears in CLI contexts:

| State | Display |
|-------|---------|
| Loading | Animated newt spinner |
| Success | `🦎 Done.` |
| Warning | `🦎 ⚠️ Completed with warnings` |
| Error | `🦎 ❌ Failed` |
| Interactive | ASCII newt in help text |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Command coverage | 80% of platform operations accessible via CLI |
| Documentation | Every command has `--help` with examples |
| Adoption | 50% of power users prefer CLI over web UI for routine tasks |
| Scriptability | All commands usable in CI/CD pipelines |

---

## Out of Scope (v1)

- GUI wrapper (terminal UI)
- Plugin system for custom commands
- Multi-language CLI (English only initially)
- Offline-first mode with full sync

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Authentication service | OAuth2/OIDC integration |
| API gateway | Backend communication |
| WASM runtime | Local model validation |

---

## Timeline

| Phase | Scope | Target |
|-------|-------|--------|
| **0.1** | Core structure, `neut log`, `neut data query` | Q2 2026 |
| **0.2** | `neut model`, `neut sim`, `neut twin` | Q3 2026 |
| **0.3** | `neut infra`, `neut ext`, shell completions | Q4 2026 |
| **1.0** | Production-ready, full documentation | Q1 2027 |

---

## Open Questions

1. **Distribution**: Homebrew? apt? Standalone binary?
2. **Config file**: TOML vs YAML for `~/.neutrc`?
3. **Plugins**: Allow third-party commands in v1 or defer?
4. **Agent mode permissions**: Per-noun granularity (e.g., "agent can write to ops log but not compliance")? Or simpler role-based scoping?
5. **Escalation UX in non-interactive contexts**: How do scripts/CI handle mode transitions? Likely: `--mode agent --yes` for pre-approved pipelines with explicit scope flags.
6. **Session persistence**: Should Plan mode drafts survive across sessions? Or are they ephemeral?
