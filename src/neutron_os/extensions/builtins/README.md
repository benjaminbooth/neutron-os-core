# `builtins/` — Domain-Agnostic Builtin Extensions

Each subdirectory is a self-contained extension that ships with Neutron OS.
These are **domain-agnostic** — they work for any nuclear facility without
customization.

## Naming Convention

**Agent extensions use the `{name}_agent` suffix.** This distinguishes
extensions with LLM autonomy from passive tools and utilities.

| Directory | Kind | Description |
|-----------|------|-------------|
| `sense_agent/` | agent | Signal ingestion, extraction, synthesis |
| `chat_agent/` | agent | Interactive LLM assistant |
| `mo_agent/` | agent | M-O resource steward |
| `doctor_agent/` | agent | AI-powered diagnostics and self-healing |
| `docflow/` | tool | Document lifecycle (md → docx → publish) |
| `db/` | tool | Database management |
| `demo/` | tool | Guided walkthroughs |
| `repo_sensing/` | tool | Multi-source repository analytics |
| `cost_estimation/` | tool | Infrastructure cost modeling |
| `status/` | utility | System health display |
| `test/` | utility | Test orchestration |
| `update/` | utility | Dependency and migration updates |

## Extension Layout

Each extension follows this structure:
```
{name}/
  neut-extension.toml   # REQUIRED — manifest
  cli.py                # CLI entry point (build_parser + main)
  tests/                # Colocated tests
  docs/                 # Extension-specific specs/docs
  infra/                # Dockerfiles, plist, deploy configs
  ...                   # Implementation files
```

## What belongs here

- New domain-agnostic extensions (useful to any facility)
- Extensions that are part of the core Neutron OS experience

## What does NOT belong here

- **Domain-specific extensions** (reactor-ops-log, medical-isotope) →
  external repos, installed to `.neut/extensions/` or `~/.neut/extensions/`
- **Platform infrastructure** → `src/neutron_os/infra/`
- **Runtime data** → `runtime/`

## AI Agent Policy

When creating a new extension:
1. Choose `kind`: `agent` (LLM autonomy), `tool` (invoked capability), `utility` (plumbing)
2. **If kind is `agent`, the directory name MUST end with `_agent`** (e.g. `my_agent/`)
3. Create `{name}/neut-extension.toml` with name, kind, module, builtin=true
4. Create `{name}/cli.py` following the `build_parser()` + `main(argv)` pattern
5. Create `{name}/tests/` for colocated tests
6. Register CLI commands via the manifest, not by editing `neut_cli.py`

Never place loose Python files directly in `builtins/`. Every piece of
functionality must live inside a named extension subdirectory.
