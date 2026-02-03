# Product Requirements Document: neut CLI

**Module:** neut Command-Line Interface  
**Status:** Planning  
**Last Updated:** January 27, 2026  
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

An agentic assistant for working with reactor systems—think Claude Code, but for nuclear facilities.

```bash
# Start interactive session
neut chat

# Start with context
neut chat --context "investigating fuel temp anomaly from yesterday"
```

**Capabilities:**
- Natural language queries against sensor data, ops logs, experiment history
- Trend analysis and anomaly correlation
- Draft ops log entries, experiment requests, compliance reports
- Run predictions and compare against actuals
- Search procedures, tech specs, historical incidents
- Walk through experiment planning with safety checks

**Key Principle:** Human-in-the-loop for all writes. Chat can draft, analyze, and suggest—but the operator confirms before anything is committed.

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
